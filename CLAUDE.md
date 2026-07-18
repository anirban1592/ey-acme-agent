# CLAUDE.md

> This file is updated continuously as the project evolves. Treat it as the source of truth over any stale summary in `project.md`. The user maintains this file directly and will keep appending to it — Claude should propose additions here whenever a new architectural decision, convention, or gotcha is established.

## Project Summary

An AI assistant for tracking customer issues and account management. Users log in via Keycloak, chat with an assistant (React frontend) that talks to a FastAPI backend, which will eventually orchestrate an agentic layer to query/update issue data. Full context: `project.md`. Current phase/subphase status: `progress-tracker.md`.

## Repo Layout

_(Update this section as the repo grows — keep it accurate, not aspirational.)_

```
stage2-project/
├── backend/              # FastAPI app
├── frontend/              # React chat interface
├── keycloak/               # realm-export.json and related Keycloak bootstrap config
├── docker-compose.yml      # brings up the full local stack
├── .env.example             # documents required environment variables
├── README.md                 # setup & run instructions
├── project.md                 # stable project brief
├── CLAUDE.md                   # this file
└── progress-tracker.md          # phase/subphase tracker
```

## Conventions

_(Fill in as decisions are made — placeholders below.)_

- **Backend code style**: TBD (e.g., black/ruff formatting, type hints required).
- **API conventions**: TBD (e.g., REST resource naming, error response shape, versioning).
- **Frontend code style**: TBD (e.g., ESLint/Prettier config, component structure).
- **Commit conventions**: TBD (e.g., Conventional Commits).
- **Environment variables**: always add new ones to `.env.example` with a comment, never commit real secrets.

## Key Architectural Decisions Log

| Date | Decision |
|---|---|
| 2026-07-16 | Backend will be Python + FastAPI (chosen for future agentic/AI orchestration fit). |
| 2026-07-16 | Keycloak realm/clients/sample users are bootstrapped via a mounted realm-import JSON (`--import-realm`) — fully declarative, no manual admin-console setup. |
| 2026-07-16 | Postgres and the app data model are explicitly deferred to Phase 2 — Phase 1 backend has no database dependency; Keycloak runs in dev mode with its embedded store. |
| 2026-07-16 | Repo uses plain folders (`backend/`, `frontend/`) with independent dependency manifests — no monorepo workspace tooling (npm/pnpm workspaces, Nx, Turborepo) until there's shared code that justifies it. |
| 2026-07-18 | Phase 3 redefined: no standalone backend service-layer module. Instead, a new top-level `mcp/` directory (independent dependency manifest, `fastmcp` package) talks to Postgres directly via its own `asyncpg` connection pool, created once at startup through FastMCP's `lifespan` hook and reused across tool calls. `mcp/db.py`'s query functions are the service layer for now. The MCP-server work originally filed under Phase 4 (wrapping a Phase 3 service layer) moves to Phase 3 itself — see `progress-tracker.md`. |
| 2026-07-18 | `issues.domain` (added nullable/unused in Phase 2.4) is repurposed to encode which role can see an issue, for the MCP server's `retrieve_customer_profile` tool: filtered as `issues.domain = role` unless `role == 'admin'`, in which case the filter is omitted entirely. |
| 2026-07-18 | Phase 4.1 (backend DB connection + user-validation gate): `users.keycloak_id` will be populated deterministically by pinning explicit `"id"` UUIDs for the seed users in `keycloak/realm-export.json` and mirroring them in `postgres/init.sql`'s seed data — not via JIT/runtime provisioning — since Keycloak otherwise assigns a random UUID per user on every realm import, leaving nothing static in Postgres to match a JWT's `sub` claim against. |
| 2026-07-18 | Backend DB access uses raw `asyncpg` (a pool created once at startup via FastAPI's `lifespan`), mirroring `mcp/db.py`'s pattern rather than introducing an ORM — keeps `backend/` and `mcp/` consistent; query functions remain the service layer for now, same convention as Phase 3. |
| 2026-07-18 | The DB-backed user-validation gate (`get_current_valid_user`, Phase 4.1) is additive alongside the existing JWT-only `get_current_user`/`/me` — not a replacement — so future agent/chat endpoints opt into the stricter check without changing existing Phase 1 behavior. |
| 2026-07-18 | For automated testing (password grant), Keycloak's `frontend-spa` client is updated with `directAccessGrantsEnabled=true`, and realm requiredActions are explicitly imported with `defaultAction=false` to prevent Keycloak from blocking login requests with required setup gates. |
| 2026-07-18 | Fixed a bug in `backend/auth.py` where `jwt.construct_rsa_key` was called, which does not exist in `python-jose`; replaced with `jwk.construct(key_dict)` to correctly decode RSA signatures. |
| 2026-07-18 | JWT verification is updated to bypass audience check (`options={"verify_aud": False}`) because standard direct access tokens issued by Keycloak do not populate the `aud` claim by default, and `KEYCLOAK_ISSUER` is set to `http://localhost:8080/realms/assistant` in the backend service configuration. |
| 2026-07-18 | Phase 4.2 (agent over WebSocket): a new `backend/agent/` directory is the home for the agent construct going forward (tools, workflows, sub-agents attach here in later subphases) — kept separate from `backend/main.py`'s routing/auth concerns. |
| 2026-07-18 | Phase 4.2: the agent is built with LangChain v1's unified `create_agent(model, tools, system_prompt)` (`langchain.agents`, backed by LangGraph), not a hand-rolled `ChatOpenAI` chain or the older `AgentExecutor`/`create_react_agent` style — chosen specifically because `create_agent` takes tools/system_prompt/sub-agent-composition as first-class constructor args, matching the project's need to attach MCP tools (4.3) and prompt design (later) without restructuring the agent later. Requires `langchain>=1.0`. |
| 2026-07-18 | Phase 4.2: the `/ws/chat` WebSocket endpoint authenticates via a `token` query param at connect time (not an `Authorization` header, which WebSocket handshakes can't carry), reusing 4.1's `verify_jwt` + `UserService.validate_user` checks; the socket is rejected with close code `1008` if either check fails. Wire protocol is a JSON envelope (`{"message": ...}` in, `{"reply": ...}` out) rather than plain text, so later subphases can add metadata without changing the message shape. |
| 2026-07-18 | Sourced `OPENAI_API_KEY` in `docker-compose.yml` backend service environment, and implemented fallback key `"mock-key"` in `backend/agent/core.py` to prevent import-time crashes and allow container health checks to succeed when no real key is set. |
| 2026-07-18 | Updated `verify_jwt` in `backend/auth.py` to dynamically whitelist both `localhost:8080` (host-to-container) and `keycloak:8080` (container-to-container) token issuer claims to support testing inside docker and runtime chat outside docker. |
| 2026-07-18 | Phase 4's scope now explicitly includes end-to-end UI integration through the auth layer (login → JWT → WebSocket → agent → response), not just backend agent work — Phase 5's originally-listed "WebSocket-based chat UI integration" moved into Phase 4.3, so Phase 5 is now escalation workflow + RBAC refinement only. |
| 2026-07-18 | Phase 4.3's chat UI reuses the existing Keycloak JS adapter's `onLoad: 'login-required'` gate (`frontend/src/App.tsx`, Phase 1.4) as the protected-page mechanism — no router or new page added, since the app stays a single page and unauthenticated visits already redirect to Keycloak login before anything renders. |


## How to Run Locally

_(Placeholder — populate once `README.md` and `docker-compose.yml` exist. Target: a single `docker compose up` brings up Keycloak (pre-loaded realm/users), the backend, and the frontend.)_

## Notes for Future Claude Sessions

- Always check `progress-tracker.md` before starting work to see which subphase is active and what's already done.
- When a new architectural decision is made mid-implementation, add it to the decisions log above with the date, and update the Repo Layout section if the file/directory structure changed.
- Keep this file itself lightweight — deep rationale belongs in `project.md`, moment-to-moment task state belongs in `progress-tracker.md`. This file is for durable, project-specific instructions Claude needs every session.
