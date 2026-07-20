import type { ChatMessage } from './useChatSocket';

// Client-side-only conversation history, persisted to localStorage.
// This exists because the backend has no endpoint to fetch a thread's past
// messages (Redis/LangGraph memory is server-side agent context only, never
// replayed to the client) — so the visible transcript for "past threads" has
// to be reconstructed here, independent of the WebSocket/backend.

export type StoredThread = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: ChatMessage[];
};

const THREADS_KEY_PREFIX = 'acme.chat.threads.v1';

// Threads are namespaced per logged-in user — otherwise every account sharing
// this browser would see (and be able to switch into) every other account's
// conversations, since localStorage has no concept of "current user" on its own.
function threadsStorageKey(userKey: string): string {
  return `${THREADS_KEY_PREFIX}:${userKey}`;
}

// Same cookie name/contract useChatSocket.ts owns (path `/`, 30-day max-age).
// Read/written here only via that existing contract — useChatSocket.ts itself
// is never modified; writing this cookie before forcing a remount of the
// component that calls useChatSocket is how thread switching works.
const THREAD_ID_COOKIE = 'chat_thread_id';
const MAX_THREADS = 20;
const TITLE_MAX_LENGTH = 42;

function getCookie(name: string): string | undefined {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : undefined;
}

export function setActiveThreadCookie(threadId: string): void {
  document.cookie = `${THREAD_ID_COOKIE}=${encodeURIComponent(threadId)}; path=/; max-age=${60 * 60 * 24 * 30}`;
}

export function loadThreads(userKey: string): StoredThread[] {
  try {
    const raw = localStorage.getItem(threadsStorageKey(userKey));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as StoredThread[]) : [];
  } catch {
    return [];
  }
}

export function saveThreads(userKey: string, threads: StoredThread[]): StoredThread[] {
  const capped = [...threads]
    .sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1))
    .slice(0, MAX_THREADS);
  try {
    localStorage.setItem(threadsStorageKey(userKey), JSON.stringify(capped));
  } catch (err) {
    console.warn('Failed to persist chat threads to localStorage', err);
  }
  return capped;
}

export function deriveTitle(messages: ChatMessage[], createdAt: string): string {
  const firstUserMessage = messages.find((m): m is ChatMessage & { role: 'user' } => m.role === 'user');
  if (firstUserMessage) {
    const trimmed = firstUserMessage.text.trim();
    return trimmed.length > TITLE_MAX_LENGTH ? `${trimmed.slice(0, TITLE_MAX_LENGTH)}…` : trimmed;
  }
  return `New conversation — ${new Date(createdAt).toLocaleString()}`;
}

export function createThread(greetingName: string): StoredThread {
  const id = crypto.randomUUID();
  const now = new Date().toISOString();
  const greeting: ChatMessage = {
    role: 'agent',
    response: {
      type: 'chat_message',
      message: `Hello ${greetingName}, how can I help you today?`,
      request_id: crypto.randomUUID(),
      timestamp: now,
      role_context: 'support',
    },
  };
  return {
    id,
    title: `New conversation — ${new Date(now).toLocaleString()}`,
    createdAt: now,
    updatedAt: now,
    messages: [greeting],
  };
}

export function upsertThreadMessages(
  threads: StoredThread[],
  threadId: string,
  messages: ChatMessage[],
): StoredThread[] {
  const index = threads.findIndex((t) => t.id === threadId);
  if (index === -1) return threads;
  const existing = threads[index];
  const updated: StoredThread = {
    ...existing,
    messages,
    title: deriveTitle(messages, existing.createdAt),
    updatedAt: new Date().toISOString(),
  };
  const next = [...threads];
  next[index] = updated;
  return next;
}

export function bootstrapThreads(
  userKey: string,
  greetingName: string,
): { threads: StoredThread[]; activeThreadId: string } {
  const existing = loadThreads(userKey);

  if (existing.length === 0) {
    const thread = createThread(greetingName);
    setActiveThreadCookie(thread.id);
    return { threads: saveThreads(userKey, [thread]), activeThreadId: thread.id };
  }

  const cookieThreadId = getCookie(THREAD_ID_COOKIE);
  const matching = cookieThreadId && existing.some((t) => t.id === cookieThreadId) ? cookieThreadId : undefined;

  if (matching) {
    return { threads: existing, activeThreadId: matching };
  }

  const mostRecent = [...existing].sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1))[0];
  setActiveThreadCookie(mostRecent.id);
  return { threads: existing, activeThreadId: mostRecent.id };
}
