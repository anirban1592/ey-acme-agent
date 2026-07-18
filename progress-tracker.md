# Progress Tracker

> Update this file as work happens: check off subphases, fill in Notes, move phase status, and add new open questions/risks as they surface. This is the operational counterpart to `project.md` (why/what) and `CLAUDE.md` (durable instructions).

## Phase Overview

| Phase | Description | Status |
|---|---|---|
| Phase 1 | Project skeleton + Keycloak-based authentication | Done |
| Phase 2 | App data store: Postgres schema + seed data, docker-compose integration | Not started |
| Phase 3 | MCP server (`mcp/`, fastmcp) with its own DB connection pool, wrapping Postgres directly | Done |
| Phase 4 | Agentic chat layer (LLM + tool-calling + MCP server against Phase 3 service layer) | Not started |
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

- The `role` argument is currently trusted as a plain string from the caller (no JWT/auth validation inside the MCP server itself) — acceptable for now since Phase 4's agentic layer is expected to be the trusted caller, but worth revisiting once the MCP server has external-facing exposure.
- `issues.domain` only has two meaningful values in practice today (`agent`/`admin`, mirroring the `roles` table) — if new roles are introduced later, seed data and this tool's filter logic need to stay in sync with the `roles` table.

## Phase 4: Agentic Chat Layer

Not started. Scope: LLM integration with tool-calling against the Phase 3 MCP server's tools; Agent interface. (Previously also scoped the MCP server itself — that work moved to Phase 3, see above.)

## Phase 5: Escalation Workflow, Chat UI Integration, RBAC Refinement

Not started. Scope: prompt-based escalation skill, WebSocket-based chat UI wired to the FastAPI backend, role-based permission refinement.

## Phase 6: Evaluation, Observability, Hardening, Deployment

Not started. Scope: evaluation via deepeval, logging/tracing, CI/CD, GitHub setup, README/architecture diagram finalization.
