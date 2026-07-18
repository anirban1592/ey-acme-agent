# Keycloak Service (Phase 1.2)

This directory contains everything needed to run the Keycloak identity provider used by the project.

## What is provided
- **`realm-export.json`** – a declarative realm definition that includes:
  - The **assistant** realm.
  - Two OIDC clients: `frontend-spa` (public) and `backend-service` (confidential).
  - Two sample users (`alice` and `bob`) with the roles `agent` and `admin`.
- **Docker‑Compose integration** – the service is defined in the root `docker-compose.yml` with the flag `--import-realm` so the realm is automatically imported on startup.

## Quick test
1. From the repository root run:
   ```bash
   docker compose up --build keycloak
   ```
2. Open a browser at **http://localhost:8080** and click **Administration Console**.
3. Log in with the admin credentials defined in `.env.example` (default `admin / admin`).
4. Verify that the *assistant* realm, its clients, and the sample users appear under the UI.

## Notes
- The embedded H2 database is used for this sandbox; the realm will be persisted inside the container. When you `docker compose down` and bring the stack up again, the same data is re‑imported from `realm‑export.json`.
- In later phases we will switch Keycloak to use an external PostgreSQL instance when we need a shared, production‑grade store.
