-- =============================================================
-- Init script for Support/Operations Issue Tracker
-- Phase 2.4 schema + curated seed data
-- Split into two independent sections:
--   SECTION 1: SCHEMA  (all CREATE TABLE / function / trigger statements)
--   SECTION 2: SEED DATA (all INSERT statements)
-- =============================================================


-- =============================================================
-- SECTION 1: SCHEMA
-- =============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp"; -- for uuid generation if needed

-- ------------------------------------------------------------
-- Table: customers
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- ------------------------------------------------------------
-- Table: customer_details
-- One-to-one extension of customers: profile/CRM-style fields used
-- to answer "tell me about customer X" questions.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customer_details (
    customer_id INT PRIMARY KEY REFERENCES customers(id) ON DELETE CASCADE,
    industry TEXT,
    account_tier TEXT,
    headquarters TEXT,
    employee_count INT,
    relationship_since DATE,
    account_manager TEXT,       -- internal (acme) sales owner
    support_lead TEXT,          -- internal (acme) support owner
    operations_lead TEXT,       -- internal (acme) operations owner
    executive_sponsor TEXT,     -- internal (acme) admin/exec owner
    primary_contact_name TEXT,  -- customer-side primary contact
    primary_contact_title TEXT,
    primary_contact_email TEXT,
    contract_value_arr NUMERIC(12,2),
    renewal_date DATE,
    products_services TEXT,
    payment_terms TEXT,
    sentiment TEXT,
    risk_level TEXT CHECK (risk_level IN ('low', 'medium', 'high')),
    notes TEXT
);

-- ------------------------------------------------------------
-- Table: statuses
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS statuses (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- ------------------------------------------------------------
-- Table: roles
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- ------------------------------------------------------------
-- Table: users
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT,
    keycloak_id UUID NULL -- nullable, will be populated later when wiring auth to DB
);

-- ------------------------------------------------------------
-- Table: user_roles (many-to-many)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_roles (
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    role_id INT REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

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

-- Trigger to auto-update updated_at column on row modification
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

-- ------------------------------------------------------------
-- Table: issue_updates
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS issue_updates (
    id SERIAL PRIMARY KEY,
    issue_id INT REFERENCES issues(id) ON DELETE CASCADE,
    comment TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- =============================================================
-- END SECTION 1: SCHEMA
-- =============================================================


-- =============================================================
-- SECTION 2: SEED DATA
-- =============================================================

-- ------------------------------------------------------------
-- Seed: customers
-- ------------------------------------------------------------
INSERT INTO customers (name) VALUES
    ('Deloitte'),
    ('Facebook'),
    ('Apple'),
    ('Samsung'),
    ('Google')
ON CONFLICT DO NOTHING;

-- ------------------------------------------------------------
-- Seed: customer_details
-- One row per customer; internal owners mirror the persona
-- assignments used for issues (sales=bob, support=tony,
-- operations=charlie, admin/exec=alice).
-- ------------------------------------------------------------
INSERT INTO customer_details (
    customer_id, industry, account_tier, headquarters, employee_count,
    relationship_since, account_manager, support_lead, operations_lead, executive_sponsor,
    primary_contact_name, primary_contact_title, primary_contact_email,
    contract_value_arr, renewal_date, products_services, payment_terms,
    sentiment, risk_level, notes
)
VALUES
    ((SELECT id FROM customers WHERE name = 'Deloitte'),
     'Professional Services / Consulting', 'Enterprise', 'London, United Kingdom', 450000,
     '2021-11-01', 'Bob Ramirez', 'Tony Marchetti', 'Charlie Osei', 'Alice Nguyen',
     'Sarah Whitfield', 'Engagement Director', 'sarah.whitfield@deloitte.com',
     780000.00, '2026-11-01', 'Full platform license, premium support tier', 'Net 45',
     'Positive, long-tenured account', 'low',
     'One of acme''s longest-standing enterprise relationships. Expects formal written status updates, particularly on open bugs.'),

    ((SELECT id FROM customers WHERE name = 'Facebook'),
     'Social Media / Technology', 'Enterprise', 'Menlo Park, California, USA', 65000,
     '2023-09-01', 'Bob Ramirez', 'Tony Marchetti', 'Charlie Osei', 'Alice Nguyen',
     'Marcus Bell', 'Procurement Manager', 'marcus.bell@facebook.com',
     620000.00, '2026-09-01', 'Hardware procurement channel, standard support plan', 'Net 30',
     'Positive', 'low',
     'Fast-moving, high-volume account. Procurement decisions move quickly once quotes are in; keep finance turnaround tight.'),

    ((SELECT id FROM customers WHERE name = 'Apple'),
     'Consumer Electronics / Technology', 'Strategic (Prospective)', 'Cupertino, California, USA', 160000,
     '2025-01-01', 'Bob Ramirez', 'Tony Marchetti', 'Charlie Osei', 'Alice Nguyen',
     'Kevin Alvarez', 'Account Manager (Apple-side)', 'kevin.alvarez@apple.com',
     NULL, NULL, 'Under evaluation', NULL,
     'Cautious', 'high',
     'Pre-contract account gated on compliance review. Do not treat as closed until compliance clears.'),

    ((SELECT id FROM customers WHERE name = 'Samsung'),
     'Consumer Electronics / Technology', 'Enterprise', 'Suwon, South Korea', 270000,
     '2023-06-01', 'Bob Ramirez', 'Tony Marchetti', 'Charlie Osei', 'Alice Nguyen',
     'Ji-hoon Park', 'Digital Commerce Manager', 'jihoon.park@samsung.com',
     950000.00, '2027-06-01', 'Online store platform access, flash-sale onboarding support', 'Net 30',
     'Positive, high-trust account', 'low',
     'Runs large, time-sensitive campaigns (flash sales). Responsiveness during these windows is critical to the relationship.'),

    ((SELECT id FROM customers WHERE name = 'Google'),
     'Technology / Internet Services', 'Strategic', 'Mountain View, California, USA', 180000,
     '2022-03-01', 'Bob Ramirez', 'Tony Marchetti', 'Charlie Osei', 'Alice Nguyen',
     'Priya Shah', 'VP, Vendor Partnerships', 'priya.shah@google.com',
     1400000.00, '2027-03-01', 'Enterprise support plan, custom integration package', 'Net 45',
     'Neutral, pending contract decision', 'medium',
     'Moves deliberately through procurement and compliance gates. Renewal outcome hinges on the pending technical questionnaire.')
ON CONFLICT (customer_id) DO UPDATE SET
    industry = EXCLUDED.industry,
    account_tier = EXCLUDED.account_tier,
    headquarters = EXCLUDED.headquarters,
    employee_count = EXCLUDED.employee_count,
    relationship_since = EXCLUDED.relationship_since,
    account_manager = EXCLUDED.account_manager,
    support_lead = EXCLUDED.support_lead,
    operations_lead = EXCLUDED.operations_lead,
    executive_sponsor = EXCLUDED.executive_sponsor,
    primary_contact_name = EXCLUDED.primary_contact_name,
    primary_contact_title = EXCLUDED.primary_contact_title,
    primary_contact_email = EXCLUDED.primary_contact_email,
    contract_value_arr = EXCLUDED.contract_value_arr,
    renewal_date = EXCLUDED.renewal_date,
    products_services = EXCLUDED.products_services,
    payment_terms = EXCLUDED.payment_terms,
    sentiment = EXCLUDED.sentiment,
    risk_level = EXCLUDED.risk_level,
    notes = EXCLUDED.notes;

-- ------------------------------------------------------------
-- Seed: statuses
-- ------------------------------------------------------------
INSERT INTO statuses (name) VALUES
    ('open'),
    ('in progress'),
    ('escalated'),
    ('closed')
ON CONFLICT DO NOTHING;

-- ------------------------------------------------------------
-- Seed: roles
-- ------------------------------------------------------------
INSERT INTO roles (name) VALUES
    ('agent'),
    ('admin'),
    ('sales'),
    ('operations'),
    ('support')
ON CONFLICT DO NOTHING;

-- ------------------------------------------------------------
-- Seed: users
-- ------------------------------------------------------------
INSERT INTO users (username, email, keycloak_id) VALUES
    ('alice',   'alice@example.com',   'a11ce000-0000-0000-0000-000000000000'),
    ('bob',     'bob@example.com',     'b0b00000-0000-0000-0000-000000000000'),
    ('charlie', 'charlie@example.com', 'c0000000-0000-0000-0000-000000000000'),
    ('tony',    'tony@example.com',    '99af8531-0af2-4b12-8c12-e49c46e52caf'),
    ('eve',     'eve@example.com',     NULL)
ON CONFLICT (username) DO UPDATE SET
    email = EXCLUDED.email,
    keycloak_id = EXCLUDED.keycloak_id;

-- ------------------------------------------------------------
-- Seed: user_roles
-- alice -> admin, bob -> sales, charlie -> operations, tony -> support
-- ------------------------------------------------------------
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id FROM users u, roles r
WHERE (u.username = 'alice'   AND r.name = 'admin')
   OR (u.username = 'bob'     AND r.name = 'sales')
   OR (u.username = 'charlie' AND r.name = 'operations')
   OR (u.username = 'tony'    AND r.name = 'support')
ON CONFLICT DO NOTHING;

-- ------------------------------------------------------------
-- Seed: issues (13 curated issues: 5 sales, 5 support, 3 operations)
-- Inserted via a CTE so issue_updates below can be linked to the
-- correct generated issue_id without guessing at IDs.
-- ------------------------------------------------------------
WITH new_issues AS (
    INSERT INTO issues (customer_id, title, description, status_id, persona, reporter_id, last_updated_by_id)
    VALUES
        -- Sales
        ((SELECT id FROM customers WHERE name = 'Deloitte'),
         'New feature request to manage users more effectively',
         'Deloitte is requesting a new feature to be added on acme''s website which would help them manage their users more effectively.',
         (SELECT id FROM statuses WHERE name = 'in progress'), 'sales',
         (SELECT id FROM users WHERE username = 'bob'), (SELECT id FROM users WHERE username = 'bob')),

        ((SELECT id FROM customers WHERE name = 'Facebook'),
         'Renewed quotations for 50 laptops',
         'Facebook has asked for renewed quotations on the request for 50 laptops to be delivered by end of Aug 2026.',
         (SELECT id FROM statuses WHERE name = 'in progress'), 'sales',
         (SELECT id FROM users WHERE username = 'bob'), (SELECT id FROM users WHERE username = 'bob')),

        ((SELECT id FROM customers WHERE name = 'Apple'),
         'Withholding partnership consent over compliance issues',
         'Apple has not given their consent to partner with acme due to compliance issues.',
         (SELECT id FROM statuses WHERE name = 'in progress'), 'sales',
         (SELECT id FROM users WHERE username = 'bob'), (SELECT id FROM users WHERE username = 'bob')),

        ((SELECT id FROM customers WHERE name = 'Samsung'),
         'Onboard 25k users for Sept flash sale',
         'Samsung has requested to onboard 25k users for September flash sales for Galaxy smartphones on acme''s online store.',
         (SELECT id FROM statuses WHERE name = 'closed'), 'sales',
         (SELECT id FROM users WHERE username = 'bob'), (SELECT id FROM users WHERE username = 'bob')),

        ((SELECT id FROM customers WHERE name = 'Google'),
         'Technical questionnaire pending response',
         'Google has sent out a sheet of acme technical questionnaire to be replied by end of Aug to decide if they want to proceed with the contract.',
         (SELECT id FROM statuses WHERE name = 'open'), 'sales',
         (SELECT id FROM users WHERE username = 'bob'), (SELECT id FROM users WHERE username = 'bob')),

        -- Support
        ((SELECT id FROM customers WHERE name = 'Deloitte'),
         'Cannot access order history page',
         'Deloitte reported that they are not able to access the order history page on acme''s website.',
         (SELECT id FROM statuses WHERE name = 'in progress'), 'support',
         (SELECT id FROM users WHERE username = 'tony'), (SELECT id FROM users WHERE username = 'tony')),

        ((SELECT id FROM customers WHERE name = 'Facebook'),
         'Website performance too slow this week',
         'Facebook has raised concerns on the website performance as it was too slow for many users this week.',
         (SELECT id FROM statuses WHERE name = 'closed'), 'support',
         (SELECT id FROM users WHERE username = 'tony'), (SELECT id FROM users WHERE username = 'tony')),

        ((SELECT id FROM customers WHERE name = 'Apple'),
         'April order showing incorrect quantities',
         'Apple has reported that the order which they placed in April is not showing up with correct quantities of products they ordered.',
         (SELECT id FROM statuses WHERE name = 'in progress'), 'support',
         (SELECT id FROM users WHERE username = 'tony'), (SELECT id FROM users WHERE username = 'tony')),

        ((SELECT id FROM customers WHERE name = 'Samsung'),
         'Users locked out, cannot log in',
         'Samsung phoned acme customer care to report that some of their users are locked and they cannot login to acme''s website.',
         (SELECT id FROM statuses WHERE name = 'open'), 'support',
         (SELECT id FROM users WHERE username = 'tony'), (SELECT id FROM users WHERE username = 'tony')),

        ((SELECT id FROM customers WHERE name = 'Google'),
         'Wants to reduce number of users accessing website',
         'Google wants to reduce the number of users accessing acme''s website.',
         (SELECT id FROM statuses WHERE name = 'open'), 'support',
         (SELECT id FROM users WHERE username = 'tony'), (SELECT id FROM users WHERE username = 'tony')),

        -- Operations
        ((SELECT id FROM customers WHERE name = 'Google'),
         'Create customer profile to onboard sales vertical',
         'Acme''s business needs to create a customer profile to onboard the sales vertical of Google.',
         (SELECT id FROM statuses WHERE name = 'in progress'), 'operations',
         (SELECT id FROM users WHERE username = 'charlie'), (SELECT id FROM users WHERE username = 'charlie')),

        ((SELECT id FROM customers WHERE name = 'Facebook'),
         'Identify correct addresses for users',
         'Business needs to identify the correct addresses for the users of Facebook.',
         (SELECT id FROM statuses WHERE name = 'in progress'), 'operations',
         (SELECT id FROM users WHERE username = 'charlie'), (SELECT id FROM users WHERE username = 'charlie')),

        (NULL,
         'Procure 50 laptops for the team',
         'Business is having issues to procure 50 laptops for their team which is stopping them from continuing day to day operations.',
         (SELECT id FROM statuses WHERE name = 'open'), 'operations',
         (SELECT id FROM users WHERE username = 'charlie'), (SELECT id FROM users WHERE username = 'charlie'))
    RETURNING id, title
)
-- ------------------------------------------------------------
-- Seed: issue_updates (linked to the issues just inserted above)
-- ------------------------------------------------------------
INSERT INTO issue_updates (issue_id, comment)
SELECT ni.id, u.comment
FROM new_issues ni
JOIN (VALUES
    ('New feature request to manage users more effectively', 1, 'Feature is being discussed internally within acme''s business to check for its feasibility; next update expected 1st week of Aug.'),

    ('Renewed quotations for 50 laptops', 1, 'Quotations has been prepared and is under review by the finance team.'),

    ('Withholding partnership consent over compliance issues', 1, 'Business has reached out to Kevin, who is the account manager, to discuss the issue.'),
    ('Withholding partnership consent over compliance issues', 2, 'Kevin is asking for stricter compliance to be able to proceed further.'),

    ('Onboard 25k users for Sept flash sale', 1, 'Acme has reached out to Samsung to understand more on the flash sale and the onboarding process to make the whole onboarding frictionless.'),
    ('Onboard 25k users for Sept flash sale', 2, 'Samsung has come back asking about the support for the same during customer users onboarding.'),
    ('Onboard 25k users for Sept flash sale', 3, 'Acme discussed and finalized the support plan and Samsung is happy.'),

    ('Cannot access order history page', 1, 'Acme''s IT team is looking at the incident.'),
    ('Cannot access order history page', 2, 'IT team reported that the latest release combined with a data issue has caused the order history page not to be shown.'),
    ('Cannot access order history page', 3, 'It requires a bug fix.'),

    ('Website performance too slow this week', 1, 'Website performance is being looked at by the IT team.'),
    ('Website performance too slow this week', 2, 'Performance was slow due to high volume of orders coming in this week.'),
    ('Website performance too slow this week', 3, 'No action to be taken as this is expected.'),

    ('April order showing incorrect quantities', 1, 'IT team has fixed it and it will be deployed next week.'),

    ('Create customer profile to onboard sales vertical', 1, 'Profile has already been created and is under review.'),

    ('Identify correct addresses for users', 1, 'Addresses have been requested from the client and Ashley is following up on that.')
) AS u(title, seq, comment)
  ON ni.title = u.title
ORDER BY u.title, u.seq;

-- =============================================================
-- END SECTION 2: SEED DATA
-- =============================================================