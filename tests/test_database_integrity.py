import sqlite3
import pytest

from src.schema import create_schema
from src.loader import load_all_data


@pytest.fixture
def connection():
    """Create an isolated in-memory database for each test."""

    connection = sqlite3.connect(":memory:")

    connection.execute("PRAGMA foreign_keys = ON;")

    create_schema(connection)

    yield connection

    connection.close()

def test_rejects_transaction_with_nonexistent_account(connection):
    """A transaction cannot reference an account that does not exist."""

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO bank_transaction (
                transaction_id,
                account_id,
                transaction_date,
                transaction_type,
                amount,
                currency,
                source_file
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "TEST_FK_001",
                "A9999",
                "2026-09-06",
                "CREDIT",
                100.00,
                "USD",
                "integrity_test.csv",
            ),
        )    

def test_rejects_account_with_nonexistent_customer(connection):
    """An account cannot reference a customer that does not exist."""

    # Valid branch so only the customer FK is under test
    connection.execute(
        "INSERT INTO branch (branch_id, branch_name, city, state) VALUES (?, ?, ?, ?)",
        ("BR001", "Test Branch", "Delhi", "DL"),
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO account (account_id, customer_id, branch_id, account_type, account_status) VALUES (?, ?, ?, ?, ?)",
            ("TEST_CUST_001", "C9999", "BR001", "CHECKING", "ACTIVE"),
        )

def test_rejects_duplicate_customer_id(connection):
    """A duplicate customer_id must violate the primary key."""

    connection.execute(
        """
        INSERT INTO customer (
            customer_id,
            customer_name,
            email,
            customer_segment
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            "C1001",
            "Test Customer",
            "test@example.com",
            "RETAIL",
        ),
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO customer (
                customer_id,
                customer_name,
                email,
                customer_segment
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                "C1001",
                "Another Customer",
                "another@example.com",
                "RETAIL",
            ),
        )

def test_rejects_negative_transaction_amount(connection):
    """Transaction amount must be greater than zero."""

    # Set up a valid account so only the CHECK constraint is being tested
    connection.execute(
        "INSERT INTO branch (branch_id, branch_name, city, state) VALUES (?, ?, ?, ?)",
        ("BR001", "Test Branch", "Delhi", "DL"),
    )
    connection.execute(
        "INSERT INTO customer (customer_id, customer_name, email, customer_segment) VALUES (?, ?, ?, ?)",
        ("C1001", "Test Customer", "test@example.com", "RETAIL"),
    )
    connection.execute(
        "INSERT INTO account (account_id, customer_id, branch_id, account_type, account_status) VALUES (?, ?, ?, ?, ?)",
        ("A1001", "C1001", "BR001", "CHECKING", "ACTIVE"),
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO bank_transaction (
                transaction_id, account_id, transaction_date,
                transaction_type, amount, currency, source_file
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("TEST_AMOUNT_001", "A1001", "2026-09-06", "CREDIT", -50.00, "USD", "integrity_test.csv"),
        )

def test_rejects_missing_required_customer_name(connection):
    """Customer name cannot be NULL."""

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO customer (
                customer_id,
                customer_name,
                email,
                customer_segment
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                "TEST_NULL_001",
                None,
                "nulltest@example.com",
                "RETAIL",
            ),
        )          

def test_expected_tables_exist():
    """Verify that all required banking tables are created."""
    connection = sqlite3.connect(":memory:")

    connection.execute("PRAGMA foreign_keys = ON;")
    create_schema(connection)

    tables = {
        row[0]
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()
    }

    expected_tables = {
        "customer",
        "branch",
        "account",
        "bank_transaction",
    }

    assert expected_tables.issubset(tables)

    connection.close()


def test_foreign_keys_are_enabled():
    """Verify that SQLite foreign-key enforcement is enabled."""
    connection = sqlite3.connect(":memory:")

    connection.execute("PRAGMA foreign_keys = ON;")
    create_schema(connection)

    result = connection.execute(
        "PRAGMA foreign_keys;"
    ).fetchone()[0]

    assert result == 1

    connection.close()


def test_expected_row_counts():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON;")

    create_schema(connection)

    counts = load_all_data(connection)

    assert counts["customers"] == 6
    assert counts["branches"] == 3
    assert counts["accounts"] == 10
    assert counts["transactions"] == 10

    customer_count = connection.execute(
        "SELECT COUNT(*) FROM customer"
    ).fetchone()[0]

    branch_count = connection.execute(
        "SELECT COUNT(*) FROM branch"
    ).fetchone()[0]

    account_count = connection.execute(
        "SELECT COUNT(*) FROM account"
    ).fetchone()[0]

    transaction_count = connection.execute(
        "SELECT COUNT(*) FROM bank_transaction"
    ).fetchone()[0]

    assert customer_count == 6
    assert branch_count == 3
    assert account_count == 10
    assert transaction_count == 10

    connection.close()