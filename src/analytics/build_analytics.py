"""Build database/analytics.db (a star schema) from database/banking.db."""

import sqlite3
from datetime import datetime

from src.operational.config import DATABASE_FILE, ANALYTICS_DATABASE_FILE


def date_to_key(date_text):
    """'2026-09-07' -> 20260907. Raises ValueError if not YYYY-MM-DD."""
    return int(datetime.strptime(date_text, "%Y-%m-%d").strftime("%Y%m%d"))


def create_analytics_schema(analytics):
    analytics.executescript(
        """
        CREATE TABLE dim_customer (
            customer_id TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            email TEXT NOT NULL,
            customer_segment TEXT NOT NULL
        );

        CREATE TABLE dim_account (
            account_id TEXT PRIMARY KEY,
            account_type TEXT NOT NULL,
            account_status TEXT NOT NULL
        );

        CREATE TABLE dim_branch (
            branch_id TEXT PRIMARY KEY,
            branch_name TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL
        );

        CREATE TABLE dim_date (
            date_key INTEGER PRIMARY KEY,
            full_date TEXT NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            day INTEGER NOT NULL,
            day_name TEXT NOT NULL
        );

        -- Grain: one row = one banking transaction
        CREATE TABLE fact_transaction (
            transaction_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            branch_id TEXT NOT NULL,
            date_key INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,

            FOREIGN KEY (account_id) REFERENCES dim_account(account_id),
            FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id),
            FOREIGN KEY (branch_id) REFERENCES dim_branch(branch_id),
            FOREIGN KEY (date_key) REFERENCES dim_date(date_key)
        );
        """
    )


def load_dimensions(banking, analytics):
    customers = banking.execute(
        "SELECT customer_id, customer_name, email, customer_segment FROM customer"
    ).fetchall()
    analytics.executemany("INSERT INTO dim_customer VALUES (?, ?, ?, ?)", customers)

    accounts = banking.execute(
        "SELECT account_id, account_type, account_status FROM account"
    ).fetchall()
    analytics.executemany("INSERT INTO dim_account VALUES (?, ?, ?)", accounts)

    branches = banking.execute(
        "SELECT branch_id, branch_name, city, state FROM branch"
    ).fetchall()
    analytics.executemany("INSERT INTO dim_branch VALUES (?, ?, ?, ?)", branches)

    dates = banking.execute(
        "SELECT DISTINCT transaction_date FROM bank_transaction"
    ).fetchall()
    date_rows = []
    for (text,) in dates:
        d = datetime.strptime(text, "%Y-%m-%d")
        date_rows.append(
            (date_to_key(text), text, d.year, d.month, d.day, d.strftime("%A"))
        )
    analytics.executemany("INSERT INTO dim_date VALUES (?, ?, ?, ?, ?, ?)", date_rows)


def load_fact(banking, analytics):
    rows = banking.execute(
        """
        SELECT t.transaction_id, t.account_id, a.customer_id, a.branch_id,
               t.transaction_date, t.transaction_type, t.amount, t.currency
        FROM bank_transaction AS t
        JOIN account AS a ON a.account_id = t.account_id
        """
    ).fetchall()
    fact_rows = [
        (tid, acc, cust, br, date_to_key(d), ttype, amount, cur)
        for (tid, acc, cust, br, d, ttype, amount, cur) in rows
    ]
    analytics.executemany(
        "INSERT INTO fact_transaction VALUES (?, ?, ?, ?, ?, ?, ?, ?)", fact_rows
    )


def build_analytics(banking_path=DATABASE_FILE, analytics_path=ANALYTICS_DATABASE_FILE):
    if not banking_path.exists():
        raise FileNotFoundError(f"banking.db not found at {banking_path}")

    # Rebuild from scratch on every run so the result is always repeatable.
    if analytics_path.exists():
        analytics_path.unlink()

    banking = sqlite3.connect(banking_path)
    analytics = sqlite3.connect(analytics_path)
    analytics.execute("PRAGMA foreign_keys = ON")

    try:
        create_analytics_schema(analytics)
        load_dimensions(banking, analytics)
        load_fact(banking, analytics)
        analytics.commit()

        for table in ("dim_customer", "dim_account", "dim_branch",
                      "dim_date", "fact_transaction"):
            count = analytics.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table}: {count} rows")
    finally:
        banking.close()
        analytics.close()


if __name__ == "__main__":
    build_analytics()