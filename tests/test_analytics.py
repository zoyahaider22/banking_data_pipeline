import sqlite3

import pytest

from src.analytics.build_analytics import build_analytics
from src.operational.schema import create_schema


@pytest.fixture
def banking_path(tmp_path):
    """A small banking.db with known data, so every expected result is exact.

    BR900 (Delhi): A1 and A3.  BR901 (Mumbai): A2.
    A1 and A2 belong to C1; A3 belongs to C2.

    T1  A1  2026-09-01  CREDIT  100
    T2  A1  2026-09-01  DEBIT    40
    T3  A2  2026-09-02  CREDIT  200
    T4  A3  2026-09-02  DEBIT    50
    T5  A3  2026-09-03  CREDIT   10
    """

    path = tmp_path / "banking_test.db"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON;")
    create_schema(connection)

    connection.executemany(
        "INSERT INTO branch VALUES (?, ?, ?, ?)",
        [("BR900", "Delhi Branch", "Delhi", "DL"),
         ("BR901", "Mumbai Branch", "Mumbai", "MH")],
    )
    connection.executemany(
        "INSERT INTO customer VALUES (?, ?, ?, ?)",
        [("C1", "Customer One", "one@example.com", "RETAIL"),
         ("C2", "Customer Two", "two@example.com", "RETAIL")],
    )
    connection.executemany(
        "INSERT INTO account VALUES (?, ?, ?, ?, ?)",
        [("A1", "C1", "BR900", "CHECKING", "ACTIVE"),
         ("A2", "C1", "BR901", "SAVINGS", "ACTIVE"),
         ("A3", "C2", "BR900", "CHECKING", "ACTIVE")],
    )
    connection.executemany(
        "INSERT INTO bank_transaction VALUES (?, ?, ?, ?, ?, ?, ?)",
        [("T1", "A1", "2026-09-01", "CREDIT", 100.0, "USD", "test.csv"),
         ("T2", "A1", "2026-09-01", "DEBIT", 40.0, "USD", "test.csv"),
         ("T3", "A2", "2026-09-02", "CREDIT", 200.0, "USD", "test.csv"),
         ("T4", "A3", "2026-09-02", "DEBIT", 50.0, "USD", "test.csv"),
         ("T5", "A3", "2026-09-03", "CREDIT", 10.0, "USD", "test.csv")],
    )
    connection.commit()
    connection.close()

    return path


@pytest.fixture
def analytics(banking_path, tmp_path):
    """analytics.db built from the small banking.db above."""

    analytics_path = tmp_path / "analytics_test.db"
    build_analytics(banking_path, analytics_path)

    connection = sqlite3.connect(analytics_path)
    connection.execute("PRAGMA foreign_keys = ON;")

    yield connection

    connection.close()


def count_rows(connection, table):
    return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_fact_row_count_matches_banking(analytics, banking_path):
    """One fact row per banking transaction, nothing lost or added."""

    banking = sqlite3.connect(banking_path)
    banking_count = count_rows(banking, "bank_transaction")
    banking.close()

    assert banking_count == 5
    assert count_rows(analytics, "fact_transaction") == 5


def test_fact_has_no_duplicate_transaction_ids(analytics):
    """The grain is one row per transaction, so transaction_id must be unique."""

    distinct = analytics.execute(
        "SELECT COUNT(DISTINCT transaction_id) FROM fact_transaction"
    ).fetchone()[0]

    assert distinct == count_rows(analytics, "fact_transaction")

    with pytest.raises(sqlite3.IntegrityError):
        analytics.execute(
            "INSERT INTO fact_transaction VALUES "
            "('T1', 'A1', 'C1', 'BR900', 20260901, 'CREDIT', 1.0, 'USD')"
        )


def test_fact_rows_reference_valid_dimensions(analytics):
    """Every fact row points at an existing customer, account, branch and date."""

    assert analytics.execute("PRAGMA foreign_key_check").fetchall() == []

    orphans = analytics.execute(
        """
        SELECT COUNT(*)
        FROM fact_transaction AS f
        LEFT JOIN dim_customer AS c ON c.customer_id = f.customer_id
        LEFT JOIN dim_account  AS a ON a.account_id  = f.account_id
        LEFT JOIN dim_branch   AS b ON b.branch_id   = f.branch_id
        LEFT JOIN dim_date     AS d ON d.date_key    = f.date_key
        WHERE c.customer_id IS NULL OR a.account_id IS NULL
           OR b.branch_id IS NULL OR d.date_key IS NULL
        """
    ).fetchone()[0]

    assert orphans == 0


def test_fact_takes_customer_and_branch_from_account(analytics):
    """T3 was made on A2, so the fact must carry A2's customer and branch."""

    row = analytics.execute(
        "SELECT account_id, customer_id, branch_id, date_key "
        "FROM fact_transaction WHERE transaction_id = 'T3'"
    ).fetchone()

    assert row == ("A2", "C1", "BR901", 20260902)


def test_net_cash_flow_by_branch_known_result(analytics):
    """Net cash flow = credits minus debits, per branch, with known answers."""

    rows = analytics.execute(
        """
        SELECT b.branch_id,
               COUNT(*),
               SUM(CASE WHEN f.transaction_type = 'CREDIT'
                        THEN f.amount ELSE -f.amount END)
        FROM fact_transaction AS f
        JOIN dim_branch AS b ON b.branch_id = f.branch_id
        GROUP BY b.branch_id
        ORDER BY b.branch_id
        """
    ).fetchall()

    # BR900: +100 -40 -50 +10 = 20 (4 transactions); BR901: +200 (1 transaction)
    assert rows == [("BR900", 4, 20.0), ("BR901", 1, 200.0)]

    # A plain SUM(amount) would wrongly say 200 for BR900: it mixes money in and out.
    plain = analytics.execute(
        "SELECT SUM(amount) FROM fact_transaction WHERE branch_id = 'BR900'"
    ).fetchone()[0]
    assert plain == 200.0


def test_rebuild_is_repeatable(banking_path, tmp_path):
    """Building twice gives the same result, with no duplicates."""

    analytics_path = tmp_path / "analytics_rebuild.db"

    build_analytics(banking_path, analytics_path)
    build_analytics(banking_path, analytics_path)

    connection = sqlite3.connect(analytics_path)
    assert count_rows(connection, "fact_transaction") == 5
    assert count_rows(connection, "dim_date") == 3
    connection.close()