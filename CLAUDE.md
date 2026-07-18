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

## How to Run Locally

_(Placeholder — populate once `README.md` and `docker-compose.yml` exist. Target: a single `docker compose up` brings up Keycloak (pre-loaded realm/users), the backend, and the frontend.)_

## Notes for Future Claude Sessions

- Always check `progress-tracker.md` before starting work to see which subphase is active and what's already done.
- When a new architectural decision is made mid-implementation, add it to the decisions log above with the date, and update the Repo Layout section if the file/directory structure changed.
- Keep this file itself lightweight — deep rationale belongs in `project.md`, moment-to-moment task state belongs in `progress-tracker.md`. This file is for durable, project-specific instructions Claude needs every session.
