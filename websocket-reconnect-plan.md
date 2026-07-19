# Keycloak token refresh + WebSocket auto-reconnect (deferred implementation plan)

> Status: **not yet implemented.** This is a reviewed design to be picked up later — see `progress-tracker.md` for when it's scheduled in.

## Context

The chat feature added earlier connects to `/ws/chat` once, at mount, with whatever access token `keycloak.token` held at that instant. Two problems follow from that:

1. **Keycloak access tokens in this realm live ~300s** (refresh tokens ~1800s). Nothing currently refreshes the token, so `keycloak.token` silently goes stale after 5 minutes — this doesn't break the *currently open* socket (the backend only checks auth once, before `websocket.accept()`, never again for the life of the connection — confirmed in `backend/main.py`'s `/ws/chat` handler), but it does mean any *new* connection attempt after that point (a reload, a dropped socket, a backend restart) will be rejected.
2. **There is no reconnect logic at all.** If the socket drops for any reason (network blip, backend container restart), `useChatSocket` just flips to `'closed'` forever — the user has to manually reload the page.

Goal: keep the Keycloak token silently refreshed in the background, and have the WebSocket reconnect automatically using whatever token is currently valid — while avoiding two failure modes: (a) needlessly tearing down a healthy, already-open socket every time the token refreshes (the backend doesn't care once a socket is open, so this would be pure churn), and (b) retry-storming the backend when it's rejecting auth for a *permanent* reason (e.g. a deactivated user) rather than a transient one — which is hard to distinguish because the backend closes with the same code (`1008`) for both expired-token and invalid-user cases.

This is a frontend-only change. No existing reconnect/backoff convention exists anywhere in this repo (confirmed by search), so this establishes a new, self-contained pattern — not backend work, not an in-band re-auth protocol (the backend doesn't support one and adding one is out of scope).

## Design

### 1. `frontend/src/App.tsx` — keep the token fresh in React state

Currently `token` is captured once as a plain string (`keycloak.token!`) and never updated. Change it to state, populated both on initial auth and on every background refresh:

```tsx
const [token, setToken] = useState<string | undefined>(undefined);
// authLoading / didInit unchanged; drop the separate `authenticated` boolean —
// `token` truthiness already tells us whether auth succeeded.

useEffect(() => {
  if (didInit.current) return;
  didInit.current = true;

  // Register before init() so it's in place before keycloak-js's internal
  // expiry timer (which accounts for computed clock skew) can fire.
  keycloak.onTokenExpired = () => {
    keycloak.updateToken(30)
      .then((refreshed) => { if (refreshed) setToken(keycloak.token); })
      .catch(() => {
        // Refresh token itself is expired/invalid — no silent recovery possible.
        console.error('Session refresh failed; redirecting to login');
        void keycloak.login();
      });
  };

  keycloak.init({ onLoad: 'check-sso', pkceMethod: 'S256', silentCheckSsoRedirectUri: ..., checkLoginIframe: false })
    .then((authed) => {
      if (!authed) { void keycloak.login(); return; }
      setToken(keycloak.token);
      setAuthLoading(false);
    })
    .catch((err) => console.error('Keycloak init error', err));
}, []);

if (authLoading) return <div>Loading…</div>;
if (!token) return <div>Redirecting to login…</div>;
return <Chat token={token} />;
```

No `onAuthRefreshSuccess`/`onAuthRefreshError` callbacks needed — `updateToken()`'s own promise resolution already tells us whether a refresh happened, so state updates directly from that `.then()`.

`Chat.tsx`'s prop signature (`token: string`) does **not** need to change — `token` is only ever passed to `<Chat>` once truthy, and stays truthy for the component's whole lifetime (a total refresh failure redirects via `keycloak.login()`, which navigates away and unmounts everything, rather than setting `token` back to `undefined`).

### 2. `frontend/src/useChatSocket.ts` — decoupled refresh vs. reconnect

**Type change:**
```ts
export type ConnectionState =
  | 'connecting'    // first-ever attempt
  | 'open'          // healthy
  | 'reconnecting'  // unexpected drop (e.g. code 1006), backoff loop in progress
  | 'auth-error'    // backend rejected with 1008; wait for a *new* token, don't retry-loop
  | 'closed';       // initial value before the first connect kicks off, and post-unmount
```

**Key structural idea:** don't key the socket's lifecycle effect on `token` — if we did, every background refresh (~every 4.5 min) would tear down and recreate a perfectly healthy connection for no backend-side benefit (the backend never re-checks auth on a live socket). Instead, split into two effects:

- One effect (`deps: []`) owns the actual `WebSocket` object for the component's entire lifetime: it defines `connect()` (with backoff state closed over: `attempts`, `hasConnectedOnce`, `reconnectTimer`, `destroyed`), and its cleanup fully tears down/cancels everything.
- A second, cheap effect (`deps: [token]`) just mirrors the latest token into a ref, and **only actively kicks off a connection attempt when the hook is currently idle** (`'closed'` or `'auth-error'`) — i.e., when nothing is already open or in flight that a fresh token would need to disturb.

```ts
export function useChatSocket(token: string | undefined) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [connectionState, setConnectionState] = useState<ConnectionState>('closed');
  const socketRef = useRef<WebSocket | null>(null);
  const tokenRef = useRef<string | undefined>(token);
  const stateRef = useRef<ConnectionState>('closed');
  const connectRef = useRef<() => void>(() => {});

  useEffect(() => { stateRef.current = connectionState; }, [connectionState]);

  // Owns the socket for the component's lifetime. Does NOT call connect()
  // itself on mount — bootstrapping the first connection is the token-watcher
  // effect's job (below), so there's exactly one caller of connect() on mount,
  // not two racing to create a socket.
  useEffect(() => {
    let attempts = 0;
    let hasConnectedOnce = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let destroyed = false;

    function scheduleReconnect() {
      const base = Math.min(30000, 500 * 2 ** attempts); // cap 30s
      attempts += 1;
      reconnectTimer = setTimeout(connect, base * (0.5 + Math.random() * 0.5)); // full jitter
    }

    function connect() {
      if (destroyed) return;
      const t = tokenRef.current;
      if (!t) return;
      setConnectionState(hasConnectedOnce ? 'reconnecting' : 'connecting');
      const socket = new WebSocket(`ws://localhost:8000/ws/chat?token=${encodeURIComponent(t)}`);
      socketRef.current = socket;

      socket.onopen = () => { attempts = 0; hasConnectedOnce = true; setConnectionState('open'); };
      socket.onmessage = (event) => { /* unchanged parsing logic */ };
      socket.onclose = (ev) => {
        socketRef.current = null;
        if (destroyed) return;
        if (ev.code === 1008) {
          // Backend rejected the token we just used — expired or permanently
          // invalid, indistinguishable from the code alone. Don't loop; wait
          // for App.tsx to actually deliver a different token.
          setConnectionState('auth-error');
          return;
        }
        scheduleReconnect(); // covers 1006 (network blip / backend restart)
      };
      socket.onerror = () => { console.debug('[chat socket] error event'); }; // onclose always follows
    }

    connectRef.current = connect;

    return () => {
      destroyed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, []);

  // Mirrors the freshest token; only actively (re)connects when idle.
  useEffect(() => {
    tokenRef.current = token;
    if (!token) return;
    if (stateRef.current === 'auth-error' || stateRef.current === 'closed') {
      connectRef.current();
    }
  }, [token]);

  const sendMessage = useCallback(/* unchanged: no-op if socket isn't OPEN */, []);

  return { messages, connectionState, sendMessage };
}
```

Bootstrap correctness: `connectionState` starts at `'closed'`, and the token-watcher effect runs on mount too (like any `useEffect`), so it fires the *only* initial `connect()` call. The socket-owner effect merely wires up `connectRef.current` — it never calls `connect()` directly itself, which is what avoids a double-connect race on mount. (This fixes a subtle bug in an earlier draft of this plan, where both effects would call `connect()` independently on mount, leaking an orphaned first socket.)

**Backoff behavior:** base 500ms, ×2 per attempt, full jitter, capped at 30s, uncapped attempt count (network blips / backend restarts are assumed eventually transient — a hard ceiling would strand the user with no path back except a manual reload). Reset `attempts` to 0 on every successful `onopen`.

**Why this avoids retry storms on permanent auth rejection:** on a `1008` close, the hook goes idle (`'auth-error'`) and does nothing until `App.tsx`'s independent refresh cycle (bounded to roughly once per access-token lifetime, ~5 min) delivers an actually-different token — at which point the watcher effect fires exactly one immediate retry (edge-triggered, not a loop). A transient expired-token race self-heals within one refresh cycle; a genuinely-deactivated user just keeps failing once every ~5 min forever — a low, bounded rate, and visibly surfaced in the UI rather than silently spinning.

**StrictMode double-invoke:** safe without a manual guard (unlike `keycloak.init()`, which needs one). All mutable retry state (`attempts`, `hasConnectedOnce`, `reconnectTimer`, `destroyed`) lives inside the effect closure, not on a cross-invocation-shared ref, so the first StrictMode invocation's cleanup (`destroyed = true`, timer cleared, socket closed) fully neutralizes it before the second invocation starts fresh.

### 3. `frontend/src/Chat.tsx` — small UI polish (optional but recommended)

- Replace the raw `Connection: {connectionState}` text with a label map so the new states read as actionable rather than jargon:
  ```ts
  const label: Record<ConnectionState, string> = {
    connecting: 'Connecting…',
    open: 'Connected',
    reconnecting: 'Reconnecting…',
    'auth-error': 'Session issue — waiting for a renewed sign-in',
    closed: 'Disconnected',
  };
  ```
- The existing `disabled={connectionState !== 'open'}` guards need no change — they already correctly disable input/send for any non-`'open'` state.
- Optional nice-to-have: a manual "Log in again" button shown when `connectionState === 'auth-error'`, calling `keycloak.login()` directly — gives the permanently-invalid-user case an explicit escape hatch instead of silently waiting for the next scheduled refresh attempt. Flagging this as a small, easily-droppable addition, not core to the ask.

## Out of scope (explicitly not doing)

- No backend changes — the backend's connect-time-only auth model is treated as fixed; no in-band re-auth protocol, no JWKS refresh (that's a separate latent issue: `init_jwks()` caches keys once at startup and never rotates them — unrelated to token expiry, not touching it here).
- No message queueing/replay for messages typed while disconnected — `sendMessage` keeps its existing no-op-if-not-open behavior.
- No defensive `setInterval`-based token refresh alongside `onTokenExpired` — the latter already accounts for computed clock skew internally; doubling up adds complexity for no benefit given the 300s/1800s token/refresh-token ratio.

## Verification (once implemented)

1. **Normal path still works**: log in, send a chat message, confirm a reply comes back.
2. **Reconnect-on-drop**: with a chat session open and connected, `docker compose restart backend` (or `stop`/`up`) to force an abrupt socket close. Confirm the UI shows `Reconnecting…`, and once the backend container is back up, the socket reconnects automatically and a new message goes through — without a page reload.
3. **No reconnect storm**: while the backend is down (step 2, before restarting), watch the Network/WS panel or console to confirm retry attempts are backing off (growing gaps, not a tight loop).
4. **Auth-error path (harder to trigger cleanly, spot-check only)**: temporarily deactivate/remove the `alice` row from the `users` Postgres table, then force a reconnect (e.g. restart the backend so the currently-open socket drops and retries) — confirm the UI shows the `auth-error` state (not an infinite reconnect spinner), and restore the row afterward.
5. Skim the browser console during all of the above for unexpected errors (there will legitimately be `WebSocket connection failed` noise while the backend is down — that's expected).
