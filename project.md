# Project Brief: Customer Issue & Account Assistant

## Vision

An AI assistant that helps a company's support and account teams track customer-related issues and manage accounts through a chat interface. A user (e.g., a support agent) logs in and asks natural-language questions like "What are the open issues for customer A?" — the assistant queries the backend/database, returns the results, and lets the user act on them (update, escalate, or close an issue) through the same conversational interface, backed by an agentic platform.

## Example Interaction

1. User logs in to the assistant system.
2. User asks: *"What are the list of open issues for customer A?"*
3. Assistant queries the database and returns the list of open issues.
4. User asks the assistant to update, escalate, or close one of the issues.
5. The agentic platform performs the action and confirms back to the user in chat.

## Architecture Overview (Target State)

```
React Chat Frontend
        |
        |  JWT access token (from Keycloak)
        v
FastAPI Backend  <-- validates JWT (issuer, audience, signature via Keycloak JWKS)
        |
        |-- Agentic / AI orchestration layer (future phase)
        |
        v
Postgres (app data: customers, statuses, roles, users, user_roles, issues, issue_updates)   [Phase 2]

Keycloak (identity provider)
  - Issues JWTs to the frontend after login
  - Backend trusts tokens issued by Keycloak
```

## Tech Stack Decisions

| Area | Decision | Rationale |
|---|---|---|
| Backend | Python + FastAPI | Good fit for the agentic/AI orchestration layer planned in later phases (LLM tool-calling, LangChain-style ecosystems), async-friendly, fast to iterate. |
| Frontend | React.js | Explicit requirement; standard SPA chat interface. |
| Identity/Auth | Keycloak | Mature, self-hostable OIDC/OAuth2 provider; supports declarative realm import for reproducible local setups; carries roles/audience claims in the JWT for backend authorization. |
| Auth bootstrap | Realm import JSON mounted into the Keycloak container (`--import-realm`) | Fully declarative — realm, clients, roles, and sample users are created automatically on `docker compose up`, no manual admin-console steps required for collaborators. |
| App data store | Postgres, schema sourced from the project's Obsidian `DB plan.md` note — **Phase 2** | 7 tables (`customers`, `statuses`, `roles`, `users`, `user_roles`, `issues`, `issue_updates`) covering customers, lookup tables for status/role, users, and issues with a versioned update history. Runs as an ephemeral (tmpfs-backed) docker-compose service that always re-applies schema + seed data on every start, so collaborators always get a known-good sample dataset. Keycloak intentionally stays on its own embedded store — this Postgres instance is exclusively for app data. |
| Repo layout | Plain folders (`backend/`, `frontend/`) with independent dependency manifests | Simplest setup for Phase 1; no shared workspace tooling needed yet since there's no shared code between frontend and backend. |
| Containerization | Docker + docker-compose | Goal: `docker compose up` brings up the entire stack with sample data, so collaborators can run the project locally with a single command. |

## Phased Roadmap

> Tentative and subject to change as the project evolves — not commitments. See `progress-tracker.md` for current, authoritative status.

- **Phase 1** — Project skeleton + Keycloak-based authentication (chat frontend logs in via Keycloak, backend validates JWTs).
- **Phase 2** — App data store: Postgres schema + seed data, integrated into docker-compose so the full stack (Keycloak, backend, frontend, Postgres) comes up with `docker compose up`. No backend/CRUD code yet — schema and infra only.
- **Phase 3** — Service layer: backend functions to read/write the Phase 2 schema (fetch issues by customer, fetch issue by id, fetch/create issue updates, create issue), then expose them as CRUD APIs.
- **Phase 4** — Agentic chat layer: LLM integration with tool-calling against the Phase 3 service layer (list/update/escalate/close issues via natural language), plus an MCP server (fastmcp) wrapping the service layer.
- **Phase 5** — Escalation workflow (prompt-based skill), WebSocket-based chat UI integration, RBAC refinement.
- **Phase 6** — Evaluation (deepeval), observability, hardening, and deployment.

## Non-Goals for Phase 1

- No app database or data model (deferred to Phase 2).
- No real AI/LLM integration yet — the chat shell exists, but it's not yet "agentic."
- No production-grade auth hardening (e.g., Keycloak runs in dev mode with an embedded store, not a production HA setup).
- No CI/CD pipeline.

## Related Documents

- `CLAUDE.md` — living, continuously-updated instructions and architectural decision log for Claude Code sessions working in this repo. Treat it as the source of truth over this file if they ever disagree.
- `progress-tracker.md` — actionable phase/subphase breakdown with status and open questions.
