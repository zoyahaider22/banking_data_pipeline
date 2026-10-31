
-- ============================================================
-- WEEK 8 CDP READINESS EXTENSION
-- Customer 360 database schema
-- ============================================================

-- 1. CUSTOMER REFERENCE TABLE
-- Grain: One row per customer

CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    customer_segment TEXT NOT NULL
);

-- 2. ACCOUNT REFERENCE TABLE
-- Grain: One row per account

CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    account_type TEXT NOT NULL,
    account_status TEXT NOT NULL,

    FOREIGN KEY (customer_id)
        REFERENCES customers(customer_id)
);

-- 3. CUSTOMER 360 EXCEPTIONS
-- Stores invalid source records and all rejection reasons.
-- No foreign keys here because orphan records must be retained.

CREATE TABLE IF NOT EXISTS customer360_exceptions (
    exception_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    source_filename TEXT NOT NULL,
    source_row_number INTEGER,
    customer_id TEXT,
    account_id TEXT,
    transaction_id TEXT,
    raw_record TEXT NOT NULL,
    rejection_reasons TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);

-- 4. INDEXES
-- Improve lookups and customer-account joins.

CREATE INDEX IF NOT EXISTS idx_accounts_customer_id
ON accounts(customer_id);

CREATE INDEX IF NOT EXISTS idx_silver_account_id
ON silver_transactions(account_id);

-- 5. CUSTOMER 360 GOLD VIEW
-- Grain: Exactly one row per customer.

DROP VIEW IF EXISTS customer_360;

CREATE VIEW customer_360 AS

WITH account_counts AS (
    SELECT
        customer_id,
        COUNT(*) AS account_count
    FROM accounts
    GROUP BY customer_id
),

transaction_metrics AS (
    SELECT
        a.customer_id,
        COUNT(t.transaction_id) AS transaction_count,
        ROUND(COALESCE(SUM(t.amount), 0.0), 2)
            AS total_transaction_amount,
        MAX(t.transaction_date) AS last_transaction_date
    FROM accounts a
    LEFT JOIN silver_transactions t
        ON a.account_id = t.account_id
    GROUP BY a.customer_id
)

SELECT
    c.customer_id,
    c.customer_name,

    COALESCE(ac.account_count, 0)
        AS account_count,

    COALESCE(tm.transaction_count, 0)
        AS transaction_count,

    COALESCE(tm.total_transaction_amount, 0.0)
        AS total_transaction_amount,

    tm.last_transaction_date

FROM customers c

LEFT JOIN account_counts ac
    ON c.customer_id = ac.customer_id

LEFT JOIN transaction_metrics tm
    ON c.customer_id = tm.customer_id;
