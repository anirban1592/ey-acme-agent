# MCP Server (Phase 3)

A Python [`fastmcp`](https://gofastmcp.com) server that exposes the application's issue data as MCP tools for the future agentic layer (Phase 4). It talks to Postgres directly through its own `asyncpg` connection pool — there is no separate backend service-layer module; `db.py`'s query functions are the service layer for now.

## Startup behavior

A single `asyncpg` connection pool is created once, at server startup, via FastMCP's `lifespan` hook (`server.py`), and is reused by every tool call for the life of the process. This avoids opening a new database connection per request.

## Tools

### `retrieve_customer_profile(customer_name, role)`

Returns the issues for a given customer, scoped by the caller's role.

- Filters issues where `issues.domain` matches `role` (case-insensitive).
- Exception: if `role` is `"admin"`, the domain filter is omitted entirely — all of that customer's issues are returned regardless of domain.
- Unknown `customer_name` naturally returns `[]`.

Each returned issue includes: `id`, `customer_name`, `title`, `description`, `status`, `domain`, `persona`, `reporter`, `last_updated_by`, `created_at`, `updated_at`.

Example:

```python
from fastmcp import Client

async with Client("http://localhost:9000/mcp") as client:
    result = await client.call_tool(
        "retrieve_customer_profile",
        {"customer_name": "Google", "role": "agent"},
    )
    print(result.data)
```

## Environment variables

Reuses the same `POSTGRES_*` variables as the `postgres` compose service (see root `.env.example`), plus:

| Variable | Default | Purpose |
|---|---|---|
| `MCP_HOST` | `0.0.0.0` | Host the MCP server binds to |
| `MCP_PORT` | `9000` | Port the MCP server listens on |
| `DB_POOL_MIN_SIZE` | `1` | Minimum size of the `asyncpg` connection pool |
| `DB_POOL_MAX_SIZE` | `5` | Maximum size of the `asyncpg` connection pool |

## Running standalone

```bash
cd mcp
pip install -r requirements.txt
POSTGRES_HOST=localhost python server.py
```

The server listens on `http://localhost:9000/mcp` (streamable-HTTP transport).

## Running via docker-compose

```bash
docker compose up postgres mcp
```

The `mcp` service waits for `postgres`'s healthcheck before starting, and is reachable on `http://localhost:9000/mcp` from the host, or `http://mcp:9000/mcp` from other containers on the compose network.

## Troubleshooting

- **Connection refused on startup** — the `postgres` service isn't up yet or `POSTGRES_HOST`/`POSTGRES_PORT` don't match; when running standalone against the compose Postgres, use `POSTGRES_HOST=localhost`, not `postgres` (that hostname only resolves inside the compose network).
- **Tool returns `[]` unexpectedly** — check that `issues.domain` actually matches the `role` string being passed (case-insensitive `ILIKE`); seed data currently sets `domain='agent'` on both sample rows (see `postgres/init.sql`).
- **Healthcheck failing** — `docker compose logs mcp`; the healthcheck just probes `http://localhost:9000/mcp` for any HTTP response (a `406` from a plain GET is expected and considered healthy — MCP's streamable-HTTP transport requires proper client headers for real calls).
