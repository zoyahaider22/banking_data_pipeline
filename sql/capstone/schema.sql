-- Week 8 capstone schema (SQLite)
-- Run audit: one row per pipeline run
CREATE TABLE IF NOT EXISTS run_audit (
    run_id        TEXT PRIMARY KEY,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    status        TEXT NOT NULL,   -- RUNNING / SUCCESS / FAILED
    status_reason TEXT
);

-- File audit: reconciliation per run and file
CREATE TABLE IF NOT EXISTS file_audit (
    run_id          TEXT NOT NULL,
    source_filename TEXT NOT NULL,
    branch_id       TEXT,
    file_date       TEXT,
    file_sha256     TEXT,
    source_rows     INTEGER,
    accepted_rows   INTEGER,
    rejected_rows   INTEGER,
    file_status     TEXT,
    note            TEXT,
    PRIMARY KEY (run_id, source_filename),
    FOREIGN KEY (run_id) REFERENCES run_audit(run_id)
);

-- Bronze: source records exactly as received (all text)
-- source_row_number: 1 = first data row after the header
CREATE TABLE IF NOT EXISTS bronze_transactions (
    bronze_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id            TEXT NOT NULL,
    source_filename   TEXT NOT NULL,
    branch_id         TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    load_timestamp    TEXT NOT NULL,
    transaction_id    TEXT,
    account_id        TEXT,
    transaction_date  TEXT,
    transaction_type  TEXT,
    amount            TEXT,
    currency          TEXT,
    FOREIGN KEY (run_id) REFERENCES run_audit(run_id)
);

-- Silver: accepted, standardized rows only
-- PRIMARY KEY on transaction_id enforces the duplicate policy
CREATE TABLE IF NOT EXISTS silver_transactions (
    transaction_id    TEXT PRIMARY KEY,
    account_id        TEXT NOT NULL,
    branch_id         TEXT NOT NULL,
    transaction_date  TEXT NOT NULL,
    transaction_type  TEXT NOT NULL,
    amount            REAL NOT NULL,
    currency          TEXT NOT NULL,
    source_filename   TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    bronze_id         INTEGER NOT NULL,
    run_id            TEXT NOT NULL,
    FOREIGN KEY (bronze_id) REFERENCES bronze_transactions(bronze_id)
);

-- Exceptions: rejected rows with source metadata and all reasons
CREATE TABLE IF NOT EXISTS exceptions (
    exception_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id            TEXT NOT NULL,
    source_filename   TEXT NOT NULL,
    branch_id         TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    bronze_id         INTEGER NOT NULL,
    transaction_id    TEXT,
    account_id        TEXT,
    transaction_date  TEXT,
    transaction_type  TEXT,
    amount            TEXT,
    currency          TEXT,
    rejection_reasons TEXT NOT NULL,
    FOREIGN KEY (bronze_id) REFERENCES bronze_transactions(bronze_id)
);

-- Gold: built from accepted Silver records only
CREATE TABLE IF NOT EXISTS gold_branch_daily_summary (
    branch_id         TEXT NOT NULL,
    transaction_date  TEXT NOT NULL,
    transaction_type  TEXT NOT NULL,
    transaction_count INTEGER NOT NULL,
    total_amount      REAL NOT NULL,
    published_run_id  TEXT NOT NULL,
    PRIMARY KEY (branch_id, transaction_date, transaction_type)
);
