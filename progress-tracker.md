# Progress Tracker

> Update this file as work happens: check off subphases, fill in Notes, move phase status, and add new open questions/risks as they surface. This is the operational counterpart to `project.md` (why/what) and `CLAUDE.md` (durable instructions).

## Phase Overview

| Phase | Description | Status |
|---|---|---|
| Phase 1 | Project skeleton + Keycloak-based authentication | Done |
| Phase 2 | App data store: Postgres schema + seed data, docker-compose integration | Not started |
| Phase 3 | MCP server (`mcp/`, fastmcp) with its own DB connection pool, wrapping Postgres directly | Done |
| Phase 4 | Agentic chat layer (LLM + tool-calling + MCP server against Phase 3 service layer) | In progress |
| Phase 5 | Escalation workflow, WebSocket chat UI integration, RBAC refinement | Not started |
| Phase 6 | Evaluation (deepeval), observability, hardening, deployment | Not started |

---

## Phase 1: Project Skeleton + Keycloak Authentication

**Goal**: A collaborator can clone the repo and run `docker compose up` to get Keycloak (pre-loaded with a realm, client, and sample users), a FastAPI backend that validates JWTs, and a React chat-shell frontend that logs in via Keycloak and proves the token round-trips to the backend correctly. No app database in this phase.

### Subphases

- [x] **1.1 Repo skeleton**
  Create `backend/`, `frontend/`, `keycloak/`, root `README.md`, `.gitignore`, `.env.example`, and a `docker-compose.yml` stub.
  **Test**: directories exist; `docker compose config` parses without error.
  **Notes**:

- [x] **1.2 Keycloak service + realm import**
  Add Keycloak to docker-compose running in dev mode (embedded store — no external Postgres needed yet). Mount a `realm-export.json` defining: a realm, a public SPA client (PKCE) for the React app, a client/audience for the backend, realm roles (e.g. `agent`, `admin`), and 1–2 sample users with passwords and role assignments.
  **Test**: `docker compose up keycloak`, log into the Keycloak admin console, confirm realm/client/users are auto-provisioned with zero manual steps.
  **Notes**:

- [x] **1.3 Backend skeleton (FastAPI)**
  Minimal app with a health endpoint and JWT validation middleware (fetch Keycloak's JWKS, verify signature/issuer/audience), plus a `/me` endpoint returning decoded token claims. No database dependency in this phase.
  **Test**: obtain a token via Keycloak's token endpoint (password grant, dev-only), call `/me` with it and confirm claims are echoed back; call without a token and confirm a 401.
  **Notes**:

- [x] **1.4 Frontend skeleton (React)**
  Chat-shell UI with a Keycloak JS adapter login redirect flow; calls backend `/me` after login and displays the result. Also add Dockerfile to build the react App.
  **Test**: open the app, get redirected to Keycloak login, log in as a sample user, land back on the chat shell, see the `/me` response rendered. Run the docker build command to test if Dockerfile is correct
  **Notes**:

- [x] **1.5 Full docker-compose wiring**
  Dockerize backend and frontend; wire service dependencies/health checks so `docker compose up` alone brings up the whole stack (Keycloak + backend + frontend, no DB) in the correct order.
  **Test**: fresh clone, `docker compose up`, complete the 1.4 test end-to-end with zero manual setup.
  **Notes**:

- [x] **1.6 README.md**
  Prerequisites, one-command run instructions, default sample user credentials, service ports, troubleshooting notes.
  **Test**: a teammate unfamiliar with the project follows the README from a clean clone and succeeds.
  **Notes**:

### Open Questions / Risks

- Token refresh strategy in the React SPA (silent refresh vs. re-login on expiry) — not yet decided.
- CORS configuration between frontend and backend origins — not yet decided.
- Secret management for `.env` (Keycloak admin credentials, client secrets) — needs a convention before this leaves local dev.
- When exactly to introduce Postgres and the app data model in Phase 2, and whether Keycloak should move off its embedded dev store onto Postgres at the same time (for consistency) or stay on embedded store longer.

---

## Phase 2: App Data Store

**Goal**: A Postgres database, seeded with schema + sample data sourced from the project's Obsidian `DB plan.md` note, running as a docker-compose service alongside Keycloak/backend/frontend. Every time the container starts (fresh `up`, or a `stop`/`start`/`restart` of an existing one), it re-applies schema + seed data — the database is intentionally ephemeral, not persisted across restarts. **Scope note**: schema + infra only — no backend code (SQLAlchemy/psycopg, CRUD endpoints) yet; that's Phase 3.

**Source schema** (7 tables, from `DB plan.md`): `customers`, `statuses`, `roles`, `users`, `user_roles` (join table), `issues`, `issue_updates`. Gaps found in the vault note are fixed during implementation (see decisions below), not carried forward as-is.

**Decisions made for this phase**:
- Fix schema gaps while implementing (not a literal copy of the note): add `users.keycloak_id` (nullable, links to Keycloak's JWT `sub` claim — closes the auth/DB integration gap; populated later once backend auth-to-DB wiring exists), add a `CHECK` constraint on `issues.domain`, add an `updated_at` auto-update trigger on `issues`, reconcile seed/comment mismatches (roles seed includes `admin`; statuses seed order stays `open, in progress, escalated, closed` since `issues.status_id DEFAULT 1` relies on `'open'` being first), and add symmetric seed coverage (a sample issue for the `GOOG` customer, an `issue_updates` row for the Deloitte issue).
- Keycloak stays on its embedded dev store — the new Postgres instance is exclusively for app data, not shared with Keycloak.
- Compose service name `postgres`, database `issuesdb`, matching what `.env.example` already stubs.
- Ephemeral-by-design: `/var/lib/postgresql/data` mounted as `tmpfs` so the data directory is never persisted, guaranteeing `docker-entrypoint-initdb.d/init.sql` re-runs on every container start (a bind-mounted init script alone only guarantees this on first-ever creation, not on restart of an existing container — tmpfs closes that gap).

### Subphases

- [x] **2.1 Schema + seed script**
  Create `postgres/init.sql` (mirrors the `keycloak/realm-export.json` per-service-directory convention) with the DDL for all 7 tables plus the seed data, including the gap-fixes listed above.
  **Test**: run against a scratch `postgres:16-alpine` container standalone; confirm all 7 tables exist with expected seed row counts and no SQL errors.
  **Notes**:

- [x] **2.2 Ephemeral Postgres compose service**
  Add a `postgres` service definition (image, env vars from `.env`, port 5432, bind-mounted `init.sql`, `pg_isready` healthcheck, `tmpfs` data dir) and `postgres/README.md` documenting what's seeded, how to connect, and the ephemeral-by-design behavior.
  **Test**: `docker compose up postgres`; insert a throwaway row; `docker compose restart postgres`; confirm the throwaway row is gone and original seed data is back — proves reseed-on-every-start.
  **Notes**:

- [x] **2.3 Root integration + docs**
  Wire `postgres` into the root `docker-compose.yml` alongside the existing services (no `depends_on` changes needed on backend/frontend yet — neither has DB code). Update root `README.md` (services/ports table, project structure tree, troubleshooting entry, note on ephemeral behavior) and `CLAUDE.md`'s decision log.
  **Test**: fresh `docker compose up` from repo root — Keycloak/backend/frontend behave exactly as at the end of Phase 1 (no regression), and Postgres joins with schema + seed data intact (`docker exec -it postgres psql -U postgres -d issuesdb -c '\dt'`).
  **Notes**:

- [x] **2.4 Schema revision: persona, reporter/last-updated-by, drop domain constraint**
  Updated `postgres/init.sql` (the actual implemented schema, which diverged somewhat from the original 2.1 plan — e.g. `SERIAL` ids instead of `UUID`, `roles` seeded as Keycloak-style `agent`/`admin`, no `version` column on `issue_updates` yet):
  - Dropped `customers.domain` (the short-code column, e.g. `GOOG`/`DELOITTE`) entirely — customers are now identified only by `name`.
  - Dropped the `chk_issue_domain` CHECK constraint on `issues.domain`; the column itself stays (now nullable, unconstrained) since its previous value source (`customers.domain`) no longer exists — currently left `NULL` in seed data.
  - Added `issues.persona TEXT CHECK (persona IN ('sales', 'operations', 'support'))` — a new categorical field distinct from the `roles` table (which holds Keycloak-style auth roles `agent`/`admin`). Seed data assigns `sales` to the Google issue and `operations` to the Deloitte issue.
  - Added `issues.reporter_id INT REFERENCES users(id) ON DELETE SET NULL` and `issues.last_updated_by_id INT REFERENCES users(id) ON DELETE SET NULL`. Seed data sets `reporter_id` to alice and `last_updated_by_id` to bob on both sample issues. Both columns are populated manually in seed data only — no application/trigger logic yet to auto-set `last_updated_by_id` on real updates (deferred to Phase 3's service layer, same as the existing `issue_updates.version` gap).
  - Also fixed `postgres/README.md`'s "test the ephemeral nature" example, which inserted a customer with a now-nonexistent `domain` column.
  **Test**: fresh `docker compose up postgres` (tmpfs reseed), confirm `\d issues` shows `persona`, `reporter_id`, `last_updated_by_id` and no `domain` NOT NULL/CHECK constraints, and `\d customers` no longer has a `domain` column; seed rows populate as described above with no SQL errors.
  **Notes**: Implemented directly in `postgres/init.sql` (not a migration — the whole script re-runs against an empty tmpfs-backed data dir on every start, so the CREATE TABLE statements were edited in place rather than adding `ALTER TABLE` migrations).

### Open Questions / Risks

- `users.keycloak_id` is added but left `NULL` in seed data — actually populating it (e.g. via JIT user provisioning on first login, or a manual mapping) is deferred to Phase 3 when backend DB wiring exists.
- `issue_updates.version` generation logic (e.g. `MAX(version)+1`) is application-managed and not yet implemented — deferred to Phase 3's service layer.
- Whether Keycloak eventually moves off its embedded store onto Postgres too remains open (currently decided against, for simplicity, but not permanently ruled out).
- `issues.domain` is now nullable and unconstrained after 2.4 — whether to keep it at all (now that `persona` covers categorization) or drop it entirely is an open call for a future cleanup.
- `issues.reporter_id` / `issues.last_updated_by_id` are populated manually in seed data only; auto-setting `last_updated_by_id` whenever an issue is modified needs real logic (trigger or service-layer) — deferred to Phase 3.

---

## Phase 3: MCP Server (`mcp/`)

**Redefined scope** (supersedes `project.md`'s original phasing, where the MCP server was filed under Phase 4 as a wrapper around a separate Phase 3 service layer): there is no standalone backend service-layer module. Instead, Phase 3 builds a new top-level `mcp/` directory (independent dependency manifest, peer to `backend/`/`frontend/`) containing a Python `fastmcp`-based MCP server that talks to Postgres directly through its own `asyncpg` connection pool. The pool is created once at server startup (via FastMCP's `lifespan` hook) and reused by every tool call, rather than opening a new DB connection per request. The query functions inside `mcp/db.py` serve as the service layer for now.

**First tool**: `retrieve_customer_profile(customer_name, role)` — returns the issues for the given customer, filtered by `issues.domain = role` (case-insensitive), except when `role == 'admin'`, in which case the domain filter is omitted and all of that customer's issues are returned regardless of domain. This repurposes `issues.domain` (added in Phase 2.4, left nullable/unused) to encode which role-scope can see an issue.

Done — all three subphases complete and verified end-to-end via docker-compose.

### Subphases

- [x] **3.1 MCP server scaffold (`mcp/`, connection pool + lifespan)**
  Created `mcp/` with `mcp/requirements.txt` (`fastmcp`, `asyncpg`), `mcp/db.py` (DSN assembly from the existing `POSTGRES_*` env vars, `create_pool()` via `asyncpg.create_pool` with configurable min/max size via `DB_POOL_MIN_SIZE`/`DB_POOL_MAX_SIZE`), and `mcp/server.py` (a `FastMCP("issues-mcp")` app wired to an `@lifespan`-decorated hook that creates the pool once at startup and closes it at shutdown, exposed to future tools via `ctx.lifespan_context["pool"]`). No tools registered yet — this subphase is purely the startup/pool plumbing that fixes the "new connection per call" problem. Runs on `transport="http"`, host/port from `MCP_HOST`/`MCP_PORT` env vars (default `0.0.0.0:9000`).
  **Test**: Verified locally — started `docker compose up postgres`, ran `python mcp/server.py` standalone against it (fresh venv, `pip install -r mcp/requirements.txt`). Log showed `Database connection pool created` exactly once at startup, before the HTTP transport began listening. Sent two requests to `http://localhost:9000/mcp`; log still showed the pool-created line only once, confirming no per-call connection setup.
  **Notes**: FastMCP resolved to v3.4.4. Lifespan API used: `from fastmcp.server.lifespan import lifespan`, `@lifespan async def app_lifespan(server): ... yield {"pool": pool}`, passed as `FastMCP("issues-mcp", lifespan=app_lifespan)`.

- [x] **3.2 `retrieve_customer_profile` tool + seed backfill**
  Added `fetch_customer_issues(pool, customer_name, role)` to `mcp/db.py` — joins `issues` to `customers`/`statuses`/`users` (for reporter/last-updated-by usernames), filters by `c.name ILIKE $1` and `i.domain ILIKE $2`, omitting the domain filter entirely when `role.strip().lower() == "admin"`. Registered it as the `retrieve_customer_profile(customer_name, role, ctx)` tool in `mcp/server.py` (`@mcp.tool(annotations={"readOnlyHint": True})`), pulling the pool from `ctx.lifespan_context["pool"]`. Backfilled `postgres/init.sql`'s seed `issues` INSERT to set `domain = 'agent'` on both sample rows.
  **Update (2026-07-18)**: typed the response for proper JSON output instead of raw `dict`. Added `mcp/models.py` with a Pydantic `Issue` model (`id: int`, `customer_name/title/status: str`, `description/domain/persona/reporter/last_updated_by: str | None`, `created_at/updated_at: datetime`). `fetch_customer_issues` now returns `list[Issue]` (via `Issue.model_validate(dict(row))`), and the tool's return annotation changed from `list[dict]` to `list[Issue]` — FastMCP auto-derives the tool's JSON output schema from this model (verified `created_at`/`updated_at` show as `{"type": "string", "format": "date-time"}`, nullable fields as `anyOf [string, null]`), and `structured_content` returned to clients is now genuine JSON with ISO-8601 datetime strings, with no serialization workarounds needed on the caller's side.
  **Test**: Verified locally — fresh `docker compose up postgres` (tmpfs reseed confirmed via `psql`: both seed issues now show `domain='agent'`), ran `mcp/server.py` standalone, then drove it with a real `fastmcp.Client` over HTTP (`http://localhost:9000/mcp`) for three cases: `("Google", "agent")` → 1 row; `("Google", "admin")` → same 1 row with the filter bypassed (not a coincidental match); `("Google", "support")` → `[]`, proving the filter genuinely excludes non-matching domains. Confirmed the pool-creation log still only appears once. Re-ran after the Pydantic typing change: `client.list_tools()` shows the new JSON output schema; `result.structured_content` is valid JSON with `created_at`/`updated_at` as ISO strings; filter behavior (agent/admin/support cases) unchanged.
  **Notes**:

- [x] **3.3 Docker-compose integration + docs**
  Added `mcp/Dockerfile` (mirrors `backend/Dockerfile`: `python:3.12-slim`, installs `curl` for the healthcheck, `pip install -r requirements.txt`, `CMD ["python", "server.py"]`); a new `mcp` service in `docker-compose.yml` (`build: ./mcp`, `POSTGRES_*` + `MCP_HOST`/`MCP_PORT` env vars, `depends_on: postgres: condition: service_healthy`, healthcheck `curl -s -o /dev/null http://localhost:9000/mcp` — a plain GET returns `406` from the streamable-HTTP transport, which curl treats as success since `-f` isn't used, so this just confirms the server is listening and responding); `MCP_HOST=0.0.0.0`/`MCP_PORT=9000` added to `.env.example`; `mcp/README.md` documenting the service, the `retrieve_customer_profile` tool contract, env vars, and how to run standalone vs. via compose.
  **Test**: Verified locally — `docker compose config` parses cleanly; `docker compose up -d --build postgres mcp` built and started both, `mcp` reached `healthy` only after `postgres` did; `docker compose logs mcp` showed the pool-creation line exactly once; re-ran the 3.2 `fastmcp.Client` test script from the host against the containerized service (`("Google","agent")` → 1 row, `("Google","admin")` → same row filter-bypassed, `("Google","support")` → `[]`) — all passed. Then `docker compose up -d` (full stack: keycloak, backend, frontend, postgres, mcp) came up with no regressions to Phases 1–2. Tore down with `docker compose down` after verification.
  **Notes**:

### Open Questions / Risks

- ~~The `role` argument is currently trusted as a plain string from the caller (no JWT/auth validation inside the MCP server itself)~~ — **Resolved in Phase 4.5**: the MCP server still trusts the caller's `roles` list (unchanged design decision — the backend agent remains the trusted caller), but the backend now guarantees that value is always the authenticated user's actual DB-backed roles, never something the LLM chose, via a `tool_interceptors` hook. See Phase 4.5 below.
- `issues.domain` only has two meaningful values in practice today (`agent`/`admin`, mirroring the `roles` table) — if new roles are introduced later, seed data and this tool's filter logic need to stay in sync with the `roles` table.

## Phase 4: Agentic Chat Layer

**Goal**: LLM integration (LangChain, OpenAI-backed) with tool-calling against the Phase 3 MCP server's tools, gated by a DB-backed user-validation layer in the backend — **and** end-to-end integration with a React chat UI, authenticated through the same Keycloak/JWT auth layer, so the login → chat → agent-response path works as a testable MVP, not just the backend in isolation. Broken into five subphases, discussed and implemented one at a time rather than all at once. (Previously also scoped the MCP server itself — that work moved to Phase 3, see above.)

**Decisions made for this phase**:
- `users.keycloak_id` is populated deterministically: `keycloak/realm-export.json` will pin explicit `"id"` fields for the seed users (alice/bob), and `postgres/init.sql`'s seed `INSERT` will set matching `keycloak_id` values — no JIT/runtime provisioning logic, consistent with the project's declarative-seed philosophy. Needed because Keycloak otherwise auto-generates a random UUID for each user on every realm import, leaving nothing static in Postgres to match a JWT's `sub` claim against.
- Backend DB access uses raw `asyncpg` (a pool created once at startup via FastAPI's `lifespan`), mirroring `mcp/db.py`'s pattern exactly rather than introducing an ORM — keeps `backend/` and `mcp/` consistent; query functions remain the service layer for now, same convention as Phase 3.
- The new DB-backed user-validation gate (`get_current_valid_user`) is additive, not a replacement for the existing JWT-only `get_current_user` — `/me` keeps working exactly as it does today; only new agent/chat endpoints depend on the stricter gate.
- Phase 5's originally-listed "WebSocket-based chat UI integration" scope moves into Phase 4.3 — an end-to-end login-to-chat MVP is treated as core to the agentic-layer phase, not deferred. Phase 5 keeps the escalation workflow and RBAC refinement only (see Phase 5 below).
- The 4.3 chat UI reuses the existing Keycloak JS adapter's `onLoad: 'login-required'` gate (from Phase 1.4) as the protected-page mechanism — no router/new page needed, since the app is still a single page and an unauthenticated visit already redirects to Keycloak login before any UI renders.

### Subphases

- [x] **4.1 Backend DB connection + user validation gate**
  Add a database layer to the backend so JWT-authenticated requests can be gated on whether the caller's Keycloak identity maps to a known, valid user in Postgres — the prerequisite for letting the agent (4.2+) act on behalf of a real user.
  - `keycloak/realm-export.json`: pin explicit `"id"` UUIDs for alice/bob.
  - `postgres/init.sql`: set `users.keycloak_id` for alice/bob to those same UUIDs.
  - `backend/db.py` (new): `asyncpg` pool, `_dsn()`/`create_pool()`, created once via FastAPI lifespan, stashed on `app.state.db_pool`.
  - `backend/models.py` (new): Pydantic `User` (`id`, `username`, `email`, `keycloak_id`, `roles: list[str]`).
  - `backend/user_service.py` (new): `UserService.validate_user(keycloak_id: str) -> User | None`, joins `users` → `user_roles` → `roles`.
  - `backend/main.py`: new `get_current_valid_user` dependency (JWT claims → `sub` → `validate_user` → `403 access denied` if `None`); new `GET /agent/ping` endpoint gated by it, returning the validated `User` (test hook ahead of the real agent in 4.2).
  - `backend/requirements.txt`: add `asyncpg`.
  **Test**: token for alice → `/agent/ping` → `200`, roles `["agent"]`; token for bob → `200`, roles `["admin"]`; token with unknown `sub` → `403 access denied`; `/me` unaffected.
  **Notes**: Implemented and successfully verified using a Python test script `test_auth.py` which requests direct tokens from Keycloak for `alice`, `bob`, and an unregistered user `charlie`. Verified that `/me` responds correctly with standard decoding for all, `/agent/ping` resolves database users and retrieves roles, and blocks the unregistered `charlie` with a 403 Access Denied. Fixed the `python-jose` public key construction bug (`jwt.construct_rsa_key` -> `jwk.construct`) and configured `KEYCLOAK_ISSUER` correctly on the backend inside `docker-compose.yml`.

- [x] **4.2 Core LangChain agent over WebSocket**
  Stand up a WebSocket chat endpoint in the backend, backed by a minimal LangChain agent connected to an OpenAI model. No tools, no prompt design yet — the agent just holds a conversation generically (e.g. "How are you?" → "I am fine. What can I do for you?"), via a real OpenAI call, not a hardcoded string. Prompt design and tool/sub-agent attachment are separate, later subphases (4.3+).
  - `backend/agent/` (new directory): home for the agent construct going forward — tools, workflows, and sub-agents attach here in later subphases.
    - `backend/agent/__init__.py`
    - `backend/agent/core.py`: builds the agent via LangChain v1's unified `create_agent(model, tools=[], system_prompt=...)` (from `langchain.agents`, backed by LangGraph — **not** a hand-rolled `ChatOpenAI` conversational chain, and not the older `AgentExecutor`/`create_react_agent` style). `model` is a `langchain_openai.ChatOpenAI` instance; `tools=[]` and `system_prompt` a minimal placeholder for now — both are first-class constructor args already, so 4.3 (MCP tools) and later prompt design slot in without restructuring. Exposes an async `respond(message: str) -> str` that calls `agent.ainvoke({"messages": [{"role": "user", "content": message}]})` and returns `result["messages"][-1].content`.
  - `backend/main.py`: new `@app.websocket("/ws/chat")` endpoint.
    - Auth: JWT passed as a `token` query param at connect time (`ws://.../ws/chat?token=<jwt>`) — WebSocket handshakes can't carry an `Authorization` header, so this reuses 4.1's `verify_jwt` + `UserService.validate_user` checks against the query-param token before accepting the socket; connection is rejected (WS close code `1008` policy violation) if either check fails.
    - Wire protocol: JSON envelope both directions — client sends `{"message": "..."}`, server replies `{"reply": "..."}` (extensible later for tool-call metadata, error codes, etc. without breaking the shape).
  - `backend/requirements.txt`: add `langchain>=1.0` (for `langchain.agents.create_agent`), `langchain-openai`.
  - `.env.example`: add `OPENAI_API_KEY` (documented, no real value committed).
  **Test**: connect to `/ws/chat` with a valid alice token → send `{"message": "How are you?"}` → receive a `{"reply": "..."}` generated by the real OpenAI call (not hardcoded); connect with a missing/invalid/unregistered-user token → socket is rejected/closed per the 4.1 gate semantics.
  **Notes**: Implemented the `backend/agent` directory with lazy initialization/fallback key `"mock-key"` to ensure start-dev/health checks don't crash without keys. Created the `/ws/chat` WebSocket endpoint with query-param token auth. Successfully tested connection rejection (HTTP 403) for invalid tokens and connection success for Alice's token, followed by LangChain agent execution (failed with 401 Incorrect API Key, confirming invocation of the OpenAI client).

- [ ] **4.3 React chat UI: authenticated single-page app wired to `/ws/chat`**
  Build a minimal, single-page chat UI in `frontend/` that reuses the existing Keycloak JS adapter (`onLoad: 'login-required'`, already in `App.tsx` since Phase 1.4) as the protected-page gate. On successful login, the app opens a WebSocket to the backend's `/ws/chat?token=<keycloak.token>` endpoint (Phase 4.2's auth contract — JWT as a query param, checked with the same `verify_jwt` + `UserService.validate_user` gate from 4.1) and lets the user exchange messages with the agent using 4.2's JSON envelope protocol (`{"message": ...}` in, `{"reply": ...}` out). Closes the loop: login → JWT → WebSocket → agent → response, all visible in the browser.
  - `frontend/src/App.tsx`: keep the existing Keycloak init/session-gate logic (unchanged), but render a new `<Chat>` component once authenticated instead of dumping raw claims to the screen.
  - `frontend/src/Chat.tsx` (new): message list + input box; sends on submit, appends both the user's own message and the agent's reply to the on-screen transcript.
  - `frontend/src/useChatSocket.ts` (new): a small hook that opens the WebSocket on mount (`ws://localhost:8000/ws/chat?token=<keycloak.token>`, same hardcoded-host convention `App.tsx` already uses for its `fetch('http://localhost:8000/me')` call), closes it on unmount, and exposes `sendMessage(text)` plus the running message list/connection state to `Chat.tsx`.
  **Test**: load the app with no session → redirected to Keycloak login (existing 1.4 behavior, unchanged); log in as alice → chat UI renders and the WebSocket connects; send a message → it appears in the transcript, followed by the agent's real OpenAI-backed reply (from 4.2); reload the tab → re-authenticates and reconnects cleanly.
  **Notes**:

- [x] **4.4 MCP tool attachment**
  Attach the Phase 3 `mcp/` server's tools (e.g. `retrieve_customer_profile`) to the agent via an MCP client adapter, so the agent can call them during tool-calling.
  **Test**: TBD once scoped in detail (to be discussed before implementation).
  **Notes**: Retroactively checked off — this happened in practice as part of the 4.2/4.3 `backend/agent/core.py` rewrite (`get_mcp_tools()`/`MultiServerMCPClient`, lazy `get_agent()`), documented in the 2026-07-18 decision-log entries about moving `create_agent(...)` to lazy init and the `MCP_SERVER_URL` fix, rather than as its own discussed subphase.

- [x] **4.5 RBAC-enforced MCP tool calls + dynamic, user-scoped system prompt**
  Closed the open risk noted in Phase 3 (`role` trusted as a plain LLM-supplied string). The authenticated `User` resolved in `backend/main.py`'s `/ws/chat` handler (via `UserService.validate_user`, Phase 4.1) is now the only source of truth for role-scoping on every `retrieve_customer_profile` call — the LLM can no longer influence which role(s) get used, including via prompt injection.
  - `backend/agent/context.py` (new): `AgentContext` dataclass (`username`, `roles: list[str]`) — per-invocation, non-LLM-controlled data.
  - `backend/agent/core.py`: `create_agent(..., context_schema=AgentContext, middleware=[role_aware_prompt])` — `role_aware_prompt` is a `@dynamic_prompt`-decorated function (`langchain.agents.middleware`) that builds the system prompt per call from `request.runtime.context`, replacing the old static `SYSTEM_PROMPT`. `get_mcp_tools()`'s `MultiServerMCPClient` gets `tool_interceptors=[inject_role_interceptor]` (`langchain_mcp_adapters.interceptors.MCPToolCallRequest`) — for `retrieve_customer_profile` calls specifically, it unconditionally overwrites the `roles` argument with `AgentContext.roles` via `request.override(...)` before the call reaches the MCP server, regardless of what the LLM supplied. `respond(message, user)` now takes the authenticated `User` and builds `AgentContext(username=user.username, roles=user.roles)`, passed as `context=` to `agent.ainvoke(...)`. The existing lock-guarded `_agent` singleton is unaffected — `context` is per-`ainvoke()`, not baked into agent construction, so the shared agent instance stays safe across concurrent users.
  - `backend/main.py`: `/ws/chat` now calls `respond(message_text, user)` instead of `respond(message_text)`.
  - `mcp/server.py` / `mcp/db.py`: `retrieve_customer_profile`/`fetch_customer_issues` signature changed from `role: str` to `roles: list[str]` (a user can hold multiple roles via `user_roles`) — admin bypass triggers if `"admin"` is anywhere in `roles`; non-admin filtering uses `i.domain ILIKE ANY($2::text[])`; an empty `roles` list fails closed (matches nothing).
  - `backend/requirements.txt`: pinned `langchain-mcp-adapters>=0.3.0` (confirmed installed version exposes `tool_interceptors`/`MCPToolCallRequest.override`).
  **Test**: direct MCP calls with `roles=["agent"]`/`["admin"]`/`["support"]`/`["agent","admin"]` against the Google seed issue (`domain='agent'`) confirm admin-bypass-if-any-role-is-admin and correct multi-role union filtering. End-to-end via `/ws/chat`: alice (`roles=["agent"]`) and bob (`roles=["admin"]`) each see the correct scoped result; an adversarial message from alice explicitly asking the agent to call the tool with an admin role returns alice's normal agent-scoped result unchanged, proving the interceptor — not the LLM — controls the value. Two concurrent sessions (alice, bob) each get a system prompt referencing their own username, confirming the singleton agent doesn't leak context across requests.
  **Notes**: Verified against current LangChain v1 / `langchain-mcp-adapters` docs via context7 before implementing (`context_schema`/`@dynamic_prompt`/`tool_interceptors` — not assumed from training data). MCP server's trust model is otherwise unchanged (still trusts `roles` as given — the backend remains the trusted caller per Phase 3's existing decision); this subphase only fixes *who controls the value the backend sends*.

- [x] **4.6 Customer-profile CRM lookup via a manual agent-as-tool sub-agent**
  Adds a second, distinct customer-lookup capability: CRM/account data (industry, account tier, account manager, contract value, risk level, sentiment, notes, etc.) from the `customer_details` table — separate from the existing `retrieve_customer_profile` MCP tool, which (despite its name) returns *issues*, not CRM data. Unlike issues, `customer_details` has no role/domain scoping, so no RBAC interceptor changes were needed for this tool.
  - `backend/models/models.py` / `backend/models/__init__.py`: new `CustomerProfile` pydantic model (`customer_name` + all `customer_details` columns), exported.
  - `backend/services/customer_service.py` (previously an empty stub): `CustomerService.get_customer_profile(customer_name: str) -> CustomerProfile | None`, joining `customers`+`customer_details` via `c.name ILIKE $1`, matching `mcp/db.py`'s query style. Deliberately owns its own lazily-created `asyncpg` pool (mirroring `mcp/db.py`'s independent-pool convention) rather than reusing `app.state.db_pool` — a conscious, scoped exception to the Phase 3 "MCP-only DB access" convention for this one new capability.
  - `backend/agent/customer_profile.py` (new): the first sub-agent in the codebase, built with the manual "agent-as-tool" pattern (`create_agent` wrapped in a plain `@tool` function) rather than the `deepagents` package's `SubAgentMiddleware`, to avoid adding a new dependency for a single-tool sub-agent. Contains `get_customer_profile` (tool wrapping `CustomerService`), `customer_profile_agent` (a small sub-agent scoped to that one tool, with its own `ChatOpenAI` instance to avoid a `core.py`/`customer_profile.py` circular import), and `consult_customer_profile_agent` (the wrapper tool the top-level agent calls). Both tools' docstrings explicitly cross-reference `retrieve_customer_profile` to disambiguate "CRM profile" from "issues" for the LLM.
  - `backend/agent/core.py`: `get_agent()`'s tool list becomes `(await get_mcp_tools()) + [consult_customer_profile_agent]`.
  **Test**: `CustomerService.get_customer_profile("google")` (lowercase, proving `ILIKE`) returns all seeded fields; a nonexistent name returns `None`. Direct `get_customer_profile.ainvoke({"customer_name": "Apple"})` returns valid JSON; unknown name returns the "No profile found" string. End-to-end via `/ws/chat`: a logged-in user asks "What's Google's account tier and risk level?" and the reply reflects seeded CRM data, while a separate message asking "What issues does Google have?" still correctly routes to the existing `retrieve_customer_profile` MCP tool, confirming the two same-domain tools don't get confused by the LLM.
  **Notes**:

- [x] **4.7 Issue-updates lookup tool + RBAC re-pointed from `issues.domain` to `issues.persona`**
  While building the RBAC test plan for a new tool, found that `postgres/initv2.sql`'s `issues` seed data sets `persona` on every row but never sets `domain` — so `issues.domain` was `NULL` for all seeded issues, meaning the Phase 4.5 RBAC filter (`i.domain ILIKE ANY(...)`) matched nothing for any non-admin role in practice. Since seeded users already line up 1:1 with `persona` values (`bob`→sales, `charlie`→operations, `tony`→support, `alice`→admin), RBAC for both `retrieve_customer_profile` and the new tool below now filters on `issues.persona` directly; the `domain` column is removed entirely.
  - `postgres/initv2.sql`: dropped the `domain TEXT` column from `issues`.
  - `mcp/models.py`: removed `Issue.domain`; added `IssueUpdate` (`id`, `issue_id`, `comment`, `created_at`) and `IssueWithUpdates` (`issue: Issue`, `updates: list[IssueUpdate]`).
  - `mcp/db.py`: `fetch_customer_issues`'s `_ISSUES_QUERY`/filter now use `i.persona` instead of `i.domain` (same admin-bypass/`ILIKE ANY` shape, just renamed `domain_filter`→`persona_filter`). New `fetch_issue_updates(pool, issue_id, roles)`: a single query LEFT JOINing `issues` to `issue_updates` on `issue_id` (persona-filtered in the same `WHERE` clause as the issue lookup), producing one row per update (or one all-null-update row if there are none); the Python layer builds the `Issue` from the first row and collects `IssueUpdate`s from every row where `update_id IS NOT NULL`, ordered via `ORDER BY iu.created_at DESC NULLS LAST`. Returns `None` on a role/persona mismatch or nonexistent id (indistinguishable, matching the existing no-existence-leak convention) since the `WHERE`/persona filter excludes all rows in that case.
  - `mcp/server.py`: new `retrieve_issue_updates(issue_id, roles, ctx) -> IssueWithUpdates | None` tool, same pattern as `retrieve_customer_profile`; that tool's docstring updated from "domain" to "persona" wording.
  - `mcp/README.md`: updated to describe persona-based filtering (was still documenting the old domain-based behavior, including a stale pointer to the legacy `postgres/init.sql`), and documents the new tool.
  - `backend/agent/core.py`: `inject_role_interceptor`'s tool-name check extended to `("retrieve_customer_profile", "retrieve_issue_updates")` so the new tool gets the same real RBAC enforcement (authenticated roles, not LLM-supplied) as the existing one.
  **Test**: `fetch_customer_issues(pool, "Deloitte", ["sales"])` non-empty vs. `["support"]` empty vs. `["admin"]` all of Deloitte's issues, confirming persona-based filtering now actually discriminates (unlike the prior domain-based filter against unpopulated seed data). `fetch_issue_updates` against a sales-persona issue: `["sales"]` and `["admin"]` both return the issue + updates newest-first; `["support"]` returns `None`; a nonexistent id with `["admin"]` also returns `None`. End-to-end via `/ws/chat`: bob (sales) can ask about his sales issues' history and gets it; asking about an operations-only issue returns not-found/no-access; alice (admin) sees both; a non-admin adversarial "call it with admin roles" prompt still only returns the caller's own persona-scoped result.
  **Notes**: Required recreating the Postgres volume (`docker compose down -v postgres`) since `initv2.sql` only runs via `docker-entrypoint-initdb.d` on an empty data directory — a schema change to an already-initialized volume doesn't take effect on its own.

- [x] **4.8 Summarizer sub-agent, wrapping `retrieve_issue_updates`**
  Fills in the `backend/agent/summarize_agent/agent.py` stub (previously `tools=[]`, unwired) into a second sub-agent, following 4.6's agent-as-tool pattern: a `create_agent(...)` with exactly one tool — the MCP server's `retrieve_issue_updates` (4.7), filtered out of the full MCP tool list by name — exposed to the main agent via a wrapper tool, `consult_summarizer_agent`. Given a query about an issue, it calls `retrieve_issue_updates` and produces a natural-language summary of the issue's current status and a synthesis of its update history (not a raw dump).
  - Fixed `backend/agent/summarize_agent/__init__.py`, which was an accidentally-created empty directory (not a file) — removed it and replaced with a real file exporting `consult_summarizer_agent`.
  - New `backend/agent/mcp_client.py`: extracted `inject_role_interceptor` and `get_mcp_tools()` out of `core.py` into a standalone module with no dependency on `core.py` or the summarizer, so both the main agent and the summarizer share the exact same RBAC enforcement point rather than each duplicating it (duplicating a security boundary risks drift as more RBAC'd MCP tools are added) — this also sidesteps a `core.py` ↔ summarizer circular import.
  - `backend/agent/summarize_agent/agent.py`: `_get_summarizer_tools()` calls the shared `get_mcp_tools()` and filters for the tool named `retrieve_issue_updates`; `get_summarizer_agent()` is a lock-guarded lazy singleton (mirrors `core.py`'s `_agent`/`_agent_lock`) built with `context_schema=AgentContext`; `consult_summarizer_agent` is the wrapper tool, taking `runtime: ToolRuntime[AgentContext]` and forwarding `runtime.context` into the sub-agent's own `ainvoke(..., context=...)` call. This forwarding is required, not optional: `inject_role_interceptor` reads whichever agent graph is *currently executing*'s `request.runtime.context`, so without explicitly passing the outer (main) agent's `AgentContext` down, the summarizer's own call to `retrieve_issue_updates` would have no context to enforce RBAC with (and fails loudly rather than silently bypassing it).
  - `backend/agent/core.py`: now imports `get_mcp_tools` from `.mcp_client` (not defined locally) and `consult_summarizer_agent` from `.summarize_agent`, added to `get_agent()`'s tool list alongside `consult_customer_profile_agent`. Dropped now-dead imports (`MultiServerMCPClient`, `MCPToolCallRequest`, and a pre-existing already-unused `ChatOpenAI` import, cleaned up as a drive-by since the import block was being touched anyway). `retrieve_issue_updates` remains directly available to the main agent too — the wrapper tool's docstring is what steers the LLM toward the synthesized-summary path versus raw structured data.
  **Test**: `_get_summarizer_tools()` against a running MCP server returns exactly one tool, `retrieve_issue_updates`. Concurrent `get_summarizer_agent()` calls return the same object (singleton works). Direct sub-agent invocation with `context=AgentContext(username="bob", roles=["sales"])` against one of bob's sales-persona issues produces a real synthesized summary (status + history); the same call against a support-only issue returns a clear "no access/not found" response rather than fabricated content. Regression: invoking the main agent (`get_agent()`) with the same context still correctly RBAC-scopes `retrieve_customer_profile` results after the extraction, confirming `mcp_client.py` didn't change existing behavior.
  **Notes**: All three tests were run as real end-to-end LLM calls (a live `OPENAI_API_KEY`, not a mocked model), against a live MCP server + Postgres, not just unit-level checks.

- [x] **4.9 Skill-based escalation agent (email drafting)**
  Fills in the `backend/agent/escalation_agent/agent.py` stub (previously broken — half-copied from `summarize_agent/agent.py`, referenced undefined names) into a third sub-agent, following the same agent-as-tool pattern as 4.6/4.8. Its job: draft an escalation/notification email, choosing between two "skills" (internal-team vs. external-customer) and, within the chosen skill, one of three documented tones — based purely on the situational description passed in, with no RBAC/MCP dependency (pure text synthesis, no protected-data access, unlike the summarizer).
  - Two new `SKILL.md` files (`backend/agent/escalation_agent/skills/internal_email/SKILL.md`, `.../customer_email/SKILL.md`), using a name/description-frontmatter + body convention, each documenting exactly 3 tones with concrete subject-line/opening/body/closing guidance: internal — Urgent/Direct, Collaborative/Informative, Formal/Procedural; customer — Empathetic/Reassuring, Professional/Formal, Proactive/Transparent.
  - `backend/agent/escalation_agent/agent.py`: a single `load_skill(skill_name: str) -> str` tool whose docstring lists both skill names + one-line descriptions — following LangChain's own documented skills pattern (confirmed via its docs, part of core `langchain`, no `deepagents` dependency) — so the agent's own tool-call decision *is* the "which skill to pick" step (progressive disclosure: full skill content isn't in context until chosen). `get_escalation_agent()` is a lock-guarded lazy singleton (mirrors `core.py`/`summarize_agent`'s pattern); `consult_escalation_agent` is the wrapper tool, with no `context_schema`/`ToolRuntime` needed since there's no per-user context to enforce.
  - `backend/agent/escalation_agent/__init__.py` (previously an empty stub file): now exports `consult_escalation_agent`.
  - `backend/agent/core.py`: added to `get_agent()`'s tool list alongside `consult_customer_profile_agent` and `consult_summarizer_agent`.
  **Test**: `load_skill.invoke({"skill_name": ...})` for both valid names returns each file's full content; an unknown name returns a clear error string instead of raising. Direct sub-agent invocation (real LLM call) with an internal-facing query calls `load_skill("internal_email")` and drafts a complete Subject+body email in a tone matching the situation (e.g. Urgent/Direct for a blocking issue); a customer-facing query about Deloitte calls `load_skill("customer_email")` and produces a customer-appropriate tone. End-to-end via `/ws/chat`: asking the main agent to draft an escalation email returns a drafted email framed for human review, not a claim of having actually sent it (no email infrastructure exists in the project — out of scope by design).
  **Notes**: This is the first sub-agent in the codebase with no RBAC/`AgentContext` dependency at all, since it never touches protected data — a useful contrast case showing the pattern established in 4.6/4.8 (context forwarding for RBAC'd tools) is conditional on actually needing it, not applied unconditionally to every sub-agent.

- [x] **4.10 Redis short-term conversation memory**
  Every `/ws/chat` message was previously a fully stateless, single-turn call — `respond(message, user)` invoked the agent with only the current `HumanMessage` and no `config=`, so LangGraph had nothing to key persisted state on and the agent never saw prior turns. This subphase adds a LangGraph checkpointer backed by Redis so the main agent gains real multi-turn memory, keyed by a `thread_id` generated server-side on first use, echoed back to the frontend on every reply, and sent back by the frontend on every subsequent message.
  - `backend/agent/checkpointer.py` (new): lazy, lock-guarded singleton (mirrors `core.py`'s `get_agent()`) building an `AsyncRedisSaver` over a long-lived `redis.asyncio.Redis` client (`get_checkpointer()`), plus `close_checkpointer()` for graceful shutdown. `asetup()` runs once, inside the lock, before the singleton is published.
  - `backend/agent/core.py`: `get_agent()` passes `checkpointer=await get_checkpointer()` into `create_agent(...)`; `respond()` gains a `thread_id: str` parameter and passes `config={"configurable": {"thread_id": thread_id}}` into `agent.ainvoke(...)` alongside the existing `context=`.
  - `backend/agent/__init__.py`: also exports `close_checkpointer`.
  - `backend/main.py`: `/ws/chat`'s loop generates `thread_id = data.get("thread_id") or str(uuid.uuid4())` per message and echoes it in every `{"reply": ..., "thread_id": ...}` response; `shutdown_event()` calls `close_checkpointer()`.
  - `frontend/src/useChatSocket.ts`: persists `thread_id` in a `document.cookie` (`chat_thread_id`), initialized from the cookie on mount, updated whenever a reply carries one, and sent on every outgoing message.
  - `docker-compose.yml`: new `redis` service (`redis:8` — the only image confirmed to bundle the RedisJSON/RediSearch modules the checkpointer needs; not an alpine variant), `tmpfs`-backed (ephemeral, matching Postgres's convention); `backend` gets `REDIS_HOST`/`REDIS_PORT` env vars and a `service_healthy` dependency on `redis`.
  - `.env.example`: documents `REDIS_HOST`/`REDIS_PORT`.
  - `backend/requirements.txt`: adds `redis`, `langgraph-checkpoint-redis`.
  **Test**: connect to `/ws/chat`, send a message with no `thread_id` → reply includes a generated one; send a follow-up reusing that `thread_id` referencing the prior turn → agent's reply shows it has that context (proves Redis round-trip, not just in-process state); a bogus/unknown `thread_id` starts a fresh empty history rather than erroring; restarting only the `backend` container mid-conversation and resuming with the same `thread_id` preserves history (proves persistence isn't just in-process); reloading the frontend tab and sending another message reuses the same cookie-stored `thread_id`.
  **Notes**: Verified `AsyncRedisSaver`'s instantiation/lifecycle pattern and Redis module requirements against current `langgraph-checkpoint-redis` docs via context7 before implementing, not assumed from training data.

- [x] **4.11 Typed WebSocket response contract**
  Every reply reaching the frontend was previously free-form prose (`messages[-1].content`), even when the underlying data was already structured (issue lists, CRM profiles) — the frontend could only render raw text. This subphase makes the reply itself a validated, discriminated-union Pydantic/TypeScript contract (`issue_list`, `customer_profile`, `escalation_email`, `bullet_summary`, `chat_message`, `error`), so the UI can render tables/cards/lists instead of parsing text.
  - `backend/agent/response_types.py` (new): content-only Pydantic models (no envelope) used as each agent's `response_format` target, enveloped `*Response` wire models (`request_id`/`timestamp`/`role_context` added), `WsResponse` discriminated union, `CONTENT_TO_RESPONSE` dispatch map, `resolve_role_context()`, and the shared `DUMMY_RECIPIENT_EMAIL` placeholder.
  - `backend/agent/core.py`: main agent's `create_agent(..., response_format=ToolStrategy(Union[...]))`; `respond()` rewritten to build the envelope, dispatch `result["structured_response"]` to the matching `*Response`, and catch any failure into an `ErrorResponse` — never raw text, never silently dropped.
  - `backend/agent/customer_profile.py`, `summarize_agent/agent.py`, `escalation_agent/agent.py`: each sub-agent gets its own `response_format` (`CustomerProfileContent`, `BulletSummaryContent`, `EscalationEmailDraft` respectively); each wrapper tool returns the structured JSON (`result["structured_response"].model_dump_json()`) instead of paraphrased prose.
  - `backend/main.py`: `/ws/chat` sends `{"reply": response.model_dump(mode="json"), "thread_id": ...}`; the "missing message" and outer-exception fallbacks are now typed `ErrorResponse`s too, not a separate ad hoc shape.
  - `backend/test_response_types.py` (new): one valid/invalid pair per type plus a discriminated-union dispatch test (unknown `type` rejected).
  - `frontend/src/schemas/agentResponses.ts` (new): zod schemas mirroring the Pydantic models field-for-field; `AgentResponse` type derived via `z.infer`.
  - `frontend/src/components/` (new): `ResponseRouter.tsx` (switch on `type`, `assertNever` exhaustiveness guard) plus one renderer per type (`IssueTable`, `CustomerProfileTable`, `EscalationEmailCard`, `BulletSummaryList`, `ChatMessageBubble`, `ErrorBanner`).
  - `frontend/src/useChatSocket.ts`/`Chat.tsx`: incoming replies are validated via `AgentResponseSchema.safeParse` before rendering (malformed payloads become a synthetic `error`-typed message, never silently dropped); `Chat.tsx` renders agent messages via `<ResponseRouter>`.
  - `frontend/package.json`/`tsconfig.json`: added `zod`, `typescript`, `@types/react(-dom)`; `moduleResolution` → `bundler`; `"build"` → `"tsc && vite build"` so type errors (including a missing switch case) actually fail the build — previously nothing type-checked at all.
  **Test**: `test_response_types.py` passes (6 valid+invalid pairs, union dispatch). End-to-end over a real `/ws/chat` connection: prompts covering all 6 types return the correct `type` and fields (verified live, including that `escalation_email.to` stays the fixed placeholder rather than being fabricated, and `chat_message.message` is an actual reply, not meta-commentary — both were real bugs caught and fixed during this phase, see `CLAUDE.md`). Frontend: `npm run build` passes; temporarily removing a `ResponseRouter.tsx` case makes it fail on the `never` assertion, then passes again once restored. Manual browser check (Playwright): `issue_list` renders as a real table and `escalation_email` as a card with the correct placeholder recipient, confirmed via screenshot/accessibility snapshot against the live stack.
  **Notes**: `response_format=<bare class or Union>` on `create_agent` silently falls back to plain prose for some models/call shapes instead of raising — must use `response_format=ToolStrategy(...)` explicitly; discovered when `customer_profile.py`'s sub-agent alone (not the other two, using the identical bare-class pattern) produced no `structured_response` at all.
  **Follow-up fix (2026-07-19)**: user-reported bug — asking for an issue's update history returned an untyped prose paragraph instead of `bullet_summary`. Root cause: `BASE_SYSTEM_PROMPT` never told the main agent *which* shape to use for which content, so it could legally (if unhelpfully) pick `chat_message` and write nice prose after fetching real structured data via `retrieve_issue_updates`. Fixed by adding an explicit rule to `BASE_SYSTEM_PROMPT` (`backend/agent/core.py`): tool-sourced structured data must use its matching shape (`issue_list`/`customer_profile`/`bullet_summary`), never `chat_message`. Also fixed a real, independent rendering bug found while investigating: `frontend/src/components/ChatMessageBubble.tsx` had no `white-space: pre-wrap`, so any multi-line `chat_message` — even a correctly-typed one — would visually collapse into one paragraph; added the same `pre-wrap` style already used in `EscalationEmailCard.tsx`. Re-verified live: the exact reported query now returns `bullet_summary` with the same underlying data (Facebook, closed, same 3 updates); re-ran the full 4.11 type sweep to confirm no other type got pushed the wrong way by the stronger prompt (plain "How are you?" still correctly returns `chat_message`).

### Open Questions / Risks

- 4.3 is scoped at a high level only; details (chat UI styling/UX) will be worked out when it's discussed, following the same discuss-then-implement flow used for 4.1/4.2/4.5/4.6/4.7/4.8/4.9. (4.6's sub-agent orchestration pattern was resolved during implementation — manual agent-as-tool, see its decision-log entry in `CLAUDE.md`.)
- 4.5's role-collapsing behavior (admin bypass if `"admin"` is anywhere in a user's roles; otherwise `ILIKE ANY` over the full roles list) assumes seed data stays roughly in sync with the `roles` table — same caveat already noted in Phase 3. (Phase 4.7 re-pointed the matched column from `issues.domain` to `issues.persona`, since `domain` was never actually populated in `initv2.sql`'s seed data.)
- Pinned `keycloak_id` UUIDs are dev-only fixtures tied to the current two seed users — if more seed users are added later, the same pin-both-sides convention (realm-export.json `id` + init.sql `keycloak_id`) must be followed.
- 4.3 deliberately does not solve token refresh or WebSocket reconnection-on-expiry (still an open question carried over from Phase 1) — the MVP assumes a session short enough that the Keycloak token obtained at login stays valid for the WebSocket's lifetime.

## Phase 5: Escalation Workflow, RBAC Refinement

Not started. Scope: prompt-based escalation skill, role-based permission refinement. (WebSocket-based chat UI integration moved to Phase 4.3 — see that phase's decisions log.)

## Phase 6: Evaluation, Observability, Hardening, Deployment

Not started. Scope: evaluation via deepeval, logging/tracing, CI/CD, GitHub setup, README/architecture diagram finalization.
