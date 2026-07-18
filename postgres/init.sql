-- Init script for Phase 2.1: Postgres schema and seed data
-- 7 tables: customers, statuses, roles, users, user_roles, issues, issue_updates
-- Gap‑fixes: users.keycloak_id (nullable), issues.domain CHECK, updated_at trigger, seed consistency
-- Phase 2.4: dropped customers.domain and the issues.domain CHECK constraint; added
-- issues.persona (sales/operations/support), issues.reporter_id and issues.last_updated_by_id (both FKs to users)

CREATE EXTENSION IF NOT EXISTS "uuid-ossp"; -- for uuid generation if needed

-- ------------------------------------------------------------
-- Table: customers
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

INSERT INTO customers (name) VALUES
    ('Google'),
    ('Deloitte')
ON CONFLICT DO NOTHING;

-- ------------------------------------------------------------
-- Table: statuses
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS statuses (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

INSERT INTO statuses (name) VALUES
    ('open'),
    ('in progress'),
    ('escalated'),
    ('closed')
ON CONFLICT DO NOTHING;

-- ------------------------------------------------------------
-- Table: roles
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

INSERT INTO roles (name) VALUES
    ('agent'),
    ('admin')
ON CONFLICT DO NOTHING;

-- ------------------------------------------------------------
-- Table: users
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT,
    keycloak_id UUID NULL -- nullable, will be populated later when wiring auth to DB
);

INSERT INTO users (username, email) VALUES
    ('alice', 'alice@example.com'),
    ('bob', 'bob@example.com')
ON CONFLICT DO NOTHING;

-- ------------------------------------------------------------
-- Table: user_roles (many‑to‑many)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_roles (
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    role_id INT REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

-- Assign roles (alice: agent, bob: admin)
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id FROM users u, roles r
WHERE (u.username = 'alice' AND r.name = 'agent')
   OR (u.username = 'bob'   AND r.name = 'admin')
ON CONFLICT DO NOTHING;

-- ------------------------------------------------------------
-- Table: issues
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS issues (
    id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customers(id) ON DELETE RESTRICT,
    title TEXT NOT NULL,
    description TEXT,
    status_id INT REFERENCES statuses(id) ON DELETE RESTRICT DEFAULT 1,
    domain TEXT,
    persona TEXT CHECK (persona IN ('sales', 'operations', 'support')),
    reporter_id INT REFERENCES users(id) ON DELETE SET NULL,
    last_updated_by_id INT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Trigger to auto‑update updated_at column on row modification
CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_timestamp ON issues;
CREATE TRIGGER set_timestamp BEFORE UPDATE ON issues
FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();

-- Seed issues (one per sample customer)
-- domain='agent' on both rows so Phase 3's retrieve_customer_profile MCP tool
-- (which filters issues.domain = role, bypassed for role='admin') has data to match.
INSERT INTO issues (customer_id, title, description, status_id, domain, persona, reporter_id, last_updated_by_id)
SELECT c.id, 'Sample issue for ' || c.name, 'Initial issue description', s.id,
       'agent',
       CASE c.name WHEN 'Google' THEN 'sales' WHEN 'Deloitte' THEN 'operations' ELSE 'support' END,
       (SELECT id FROM users WHERE username = 'alice'),
       (SELECT id FROM users WHERE username = 'bob')
FROM customers c, statuses s
WHERE s.name = 'open'
ON CONFLICT DO NOTHING;

-- ------------------------------------------------------------
-- Table: issue_updates
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS issue_updates (
    id SERIAL PRIMARY KEY,
    issue_id INT REFERENCES issues(id) ON DELETE CASCADE,
    comment TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Seed an update for the Deloitte issue (assuming its id = 2)
INSERT INTO issue_updates (issue_id, comment)
SELECT i.id, 'First update for Deloitte issue'
FROM issues i, customers c
WHERE i.customer_id = c.id AND c.name = 'Deloitte'
ON CONFLICT DO NOTHING;

-- ------------------------------------------------------------
-- End of init script
