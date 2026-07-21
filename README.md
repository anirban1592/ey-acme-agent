# Customer Issue & Account Assistant

An AI assistant for tracking customer issues and account management. Users log in via **Keycloak**, then chat with an agentic assistant (**React** frontend → **FastAPI** backend → LangChain/LangGraph agent) that queries and summarizes customer/issue data through a dedicated **MCP server**, backed by **Postgres** and **Redis**.

For the full architecture rationale and phase-by-phase decision log, see `project.md` and `CLAUDE.md`.

---

## 📦 Components

| Component | Tech | What it does |
|---|---|---|
| `keycloak/` | Keycloak | Identity provider — issues JWTs, pre-loaded with a realm, client, and sample users via `realm-export.json` |
| `frontend/` | React + Vite | Chat UI — Keycloak login gate, multi-thread sidebar, typed response rendering (tables/cards, not just prose) |
| `backend/` | FastAPI | Validates JWTs, hosts the `/ws/chat` WebSocket, runs the LangChain/LangGraph agent (main agent + 3 sub-agents + a guardrail) |
| `mcp/` | FastMCP | Model Context Protocol server — the agent's only path to issue data (`retrieve_customer_profile`, `retrieve_issue_updates`), enforcing role/persona-based access |
| `postgres/` | PostgreSQL | App data: customers, CRM details, issues, issue updates, users/roles. Ephemeral (`tmpfs`) — reseeds from `postgres/initv2.sql` on every start |
| `redis/` | Redis 8 | Short-term, per-thread conversation memory for the agent (LangGraph checkpointer). Also ephemeral |

---

## 📦 Prerequisites

- **Docker Desktop** (or Docker Engine) with Compose support
- **git** to clone the repository
- An **OpenAI API key** (the agent won't answer meaningfully without one, though the stack starts fine without it)
- Sufficient memory (≥ 4 GB recommended, since this now includes Keycloak + Postgres + Redis + an MCP server alongside backend/frontend) and free ports **8080**, **8000**, **3000**, **5432**, **9000**, **6379**

---

## 🚀 Quick Start

```bash
# 1️⃣ Clone the repo
git clone <repo‑url>
cd stage2-project

# 2️⃣ Copy the example env file and fill in your OpenAI key
cp .env.example .env
# edit .env — at minimum set OPENAI_API_KEY (get one at https://platform.openai.com/api-keys)

# 3️⃣ Build and run the full stack with a single command
docker compose up --build
```

Everything (Keycloak, Postgres, Redis, the MCP server, backend, frontend) starts together with health-check-gated startup ordering — no manual steps in between.

### Try it out

Once `docker compose ps` shows every service healthy, open **http://localhost:3000** in your browser — this is the app's front door.

- If you're not already logged in, you'll be redirected to the **Keycloak login page**.
- Log in with any of the seeded users below — **password `12345`** for all of them:

  | Username | Role | Sees |
  |---|---|---|
  | `alice` | `admin` | Everything, across all personas |
  | `bob` | `sales` | Sales-persona issues only |
  | `charlie` | `operations` | Operations-persona issues only |
  | `tony` | `support` | Support-persona issues only |

  (Full role mapping lives in `postgres/initv2.sql`'s `user_roles` seed data.)
- Seeded customers to ask about: **Deloitte, Facebook, Apple, Samsung, Google**.

---

## 💬 Sample Prompts

A few conversation flows to try once you're logged in:

**Customer profile (CRM data), then narrow follow-ups from the same context:**
```
Show me the customer profile for Facebook.
How many employees are there in this company?
Who are the primary contacts for this company?
```
The first question returns a structured profile card; the two follow-ups are answered directly from conversation memory (no need to re-name the company) instead of re-fetching the whole profile.

**Open issues for a company:**
```
Can you show all the open issues for this company?
```

**Issue history / summary:**
```
Can you summarize all the updates for issue number <id> (from the list above)?
```

**Drafting an escalation:**
```
Can you escalate this particular issue and send an email to the respective stakeholder?
```
This drafts a subject + body for human review — the assistant doesn't actually send email (no SMTP integration exists), so treat the reply as a draft, not a sent message.

Two more things worth knowing while testing:
- Off-topic questions (general knowledge, unrelated coding help) and prompt-injection attempts ("ignore your previous instructions...") are deliberately blocked by a guardrail with a fixed rejection message — that's expected behavior, not a bug.
- What you're allowed to see is enforced per-role server-side (not just hidden in the UI) — logging in as `bob` and asking about an operations-only issue will correctly come back empty/not-found, and asking the agent to "pretend" to have another role won't change that.

---

## 🛠️ Service Ports

| Service | Host Port | Notes |
|---|---|---|
| Frontend (React/Vite) | 3000 | Start here — `http://localhost:3000` |
| Backend (FastAPI) | 8000 | `/health`, `/me`, `/ws/chat` |
| Keycloak | 8080 | Admin console; login page opens here automatically |
| MCP server | 9000 | Internal — the backend agent's tool endpoint, not meant to be opened directly |
| PostgreSQL | 5432 | App data — ephemeral, reseeds on every start |
| Redis | 6379 | Conversation memory — ephemeral |

---

## 📂 Project Structure

```text
backend/              # FastAPI app: auth, WebSocket chat endpoint, LangChain/LangGraph agent
  agent/                 # Main agent, guardrail middleware, 3 sub-agents (customer profile, summarizer, escalation)
  evals/                 # DeepEval golden-question eval suite
  tests/                 # pytest unit tests
frontend/             # React + Vite chat UI
  src/components/        # Header, Sidebar, ChatWindow, typed response renderers
mcp/                   # FastMCP server — the agent's only path to issue data, with role/persona-based filtering
keycloak/              # realm-export.json and related Keycloak bootstrap config
postgres/              # Schema + seed data (customers, issues, users/roles), ephemeral
docker-compose.yml     # Orchestrates the full stack
.env.example           # Documents all required/optional environment variables
project.md             # Project vision and target architecture
CLAUDE.md              # Dated architectural decision log
README.md              # This file
```

---

## 🐞 Troubleshooting

- **Backend crashes with "Application startup failed" on a cold start** — this was a known race between the backend and Keycloak's readiness, fixed by gating on Keycloak's healthcheck. If you still see it, run `docker compose logs backend` and confirm you're on the current `docker-compose.yml`.
- **Container health checks failing** – Run `docker compose logs <service>` to see errors. Ensure Docker has enough memory (≥ 4 GB) and that ports 8080/8000/3000/5432/9000/6379 aren't already in use.
- **Agent replies are generic or error out** – Confirm `OPENAI_API_KEY` is set in `.env` (and rebuild/restart the `backend` service after changing it).
- **Login works but chat never connects** – Check `docker compose logs backend` for WebSocket auth failures; confirm `KEYCLOAK_ISSUER`/`KEYCLOAK_JWKS_URL` in `docker-compose.yml` match how you're accessing the app (`localhost` vs. a different host).
- **Docker compose config errors** – Run `docker compose config` to validate the YAML before starting containers.

---

## 📖 Contributing

- Architectural decisions and gotchas are logged with rationale in `CLAUDE.md` — check it before making structural changes.
- Run the backend unit tests with `pytest backend/tests` before committing backend changes.
