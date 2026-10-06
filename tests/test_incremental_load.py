import sqlite3
from pathlib import Path

import pytest

from src.operational.incremental_load import load_daily_file
from src.operational.schema import create_schema


FIXTURES = Path(__file__).resolve().parent / "fixtures"
DAY1 = FIXTURES / "daily_day1.csv"
DAY2 = FIXTURES / "daily_day2.csv"


@pytest.fixture
def connection():
    """In-memory database with one valid account for the fixture files."""

    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON;")

    create_schema(connection)

    connection.execute(
        "INSERT INTO branch (branch_id, branch_name, city, state) VALUES (?, ?, ?, ?)",
        ("BR900", "Test Branch", "Delhi", "DL"),
    )
    connection.execute(
        "INSERT INTO customer (customer_id, customer_name, email, customer_segment) VALUES (?, ?, ?, ?)",
        ("C9001", "Test Customer", "test@example.com", "RETAIL"),
    )
    connection.execute(
        "INSERT INTO account (account_id, customer_id, branch_id, account_type, account_status) VALUES (?, ?, ?, ?, ?)",
        ("A9001", "C9001", "BR900", "CHECKING", "ACTIVE"),
    )
    connection.commit()

    yield connection

    connection.close()


def count_transactions(connection):
    return connection.execute(
        "SELECT COUNT(*) FROM bank_transaction"
    ).fetchone()[0]


def get_amount(connection, transaction_id):
    return connection.execute(
        "SELECT amount FROM bank_transaction WHERE transaction_id = ?",
        (transaction_id,),
    ).fetchone()[0]


def test_new_transactions_are_inserted(connection):
    """New transaction IDs are inserted, with date and amount normalized."""

    counts = load_daily_file(connection, DAY1)

    assert counts["inserted"] == 2
    assert counts["updated"] == 0
    assert count_transactions(connection) == 2

    row = connection.execute(
        "SELECT transaction_date, amount FROM bank_transaction WHERE transaction_id = 'T9001'"
    ).fetchone()

    assert row == ("2026-09-01", 100.0)


def test_correction_updates_stored_value(connection):
    """An existing transaction ID is a correction and overwrites the stored amount."""

    load_daily_file(connection, DAY1)
    assert get_amount(connection, "T9002") == 40.0

    counts = load_daily_file(connection, DAY2)

    assert counts["inserted"] == 1
    assert counts["updated"] == 1
    assert get_amount(connection, "T9002") == 45.0
    assert count_transactions(connection) == 3


def test_rerun_does_not_increase_transaction_count(connection):
    """Reprocessing the same files in order leaves the table unchanged."""

    load_daily_file(connection, DAY1)
    load_daily_file(connection, DAY2)

    assert count_transactions(connection) == 3

    load_daily_file(connection, DAY1)
    load_daily_file(connection, DAY2)

    assert count_transactions(connection) == 3
    assert get_amount(connection, "T9002") == 45.0