
"""Build the Week 8 CDP Readiness Extension Customer 360 data product.

Run from the repository root:
    python -m src.customer360.build_customer360

The script reuses the Week 8 capstone SQLite database and accepted
silver_transactions. It rebuilds only the extension-owned customers,
accounts and customer360_exceptions tables. It never edits Week 8 Silver
transactions or gold_branch_daily_summary.
"""

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src.capstone.db import BASE_DIR, DB_PATH, connect, utc_now


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

CUSTOMER_FILE = BASE_DIR / "data" / "customer360" / "customers.csv"
ACCOUNT_FILE = BASE_DIR / "data" / "customer360" / "accounts.csv"
SCHEMA_FILE = BASE_DIR / "sql" / "customer360" / "schema.sql"
OUTPUT_DIR = BASE_DIR / "output" / "customer360"
BACKUP_DIR = OUTPUT_DIR / "backups"
GOLD_FILE = OUTPUT_DIR / "customer_360.csv"
EXCEPTIONS_FILE = OUTPUT_DIR / "customer360_exceptions.csv"

CUSTOMER_COLUMNS = ("customer_id", "customer_name", "customer_segment")

ACCOUNT_COLUMNS = (
    "account_id",
    "customer_id",
    "branch_id",
    "account_type",
    "account_status",
)


# -----------------------------------------------------------------------------
# Backup and CSV utilities
# -----------------------------------------------------------------------------

def create_database_backup(connection):
    """Create a consistent SQLite backup before changing extension tables."""

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )

    backup_path = BACKUP_DIR / (
        f"banking_capstone_before_customer360_{timestamp}.db"
    )

    backup_connection = sqlite3.connect(backup_path)

    try:
        connection.backup(backup_connection)
    finally:
        backup_connection.close()

    return backup_path


def read_reference_csv(path, required_columns):
    """Read a reference CSV and retain source row numbers and row-shape errors.

    A missing required header is a file-level error. Missing/extra values in an
    individual data row are returned as row-level issues so the row can be
    written to customer360_exceptions instead of silently discarded.
    """

    path = Path(path)

    if not path.is_file():
        raise FileNotFoundError(
            f"Required input file not found: {path}"
        )

    with path.open(
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as source:

        reader = csv.reader(source)

        header = next(reader, None)

        if not header:
            raise ValueError(
                f"CSV is empty or has no header: {path.name}"
            )

        header = [item.strip() for item in header]

        if any(not item for item in header):
            raise ValueError(
                f"CSV contains an empty column name: {path.name}"
            )

        if len(header) != len(set(header)):
            raise ValueError(
                f"CSV contains duplicate column names: {path.name}"
            )

        missing_headers = sorted(
            set(required_columns) - set(header)
        )

        if missing_headers:
            raise ValueError(
                f"{path.name} is missing required columns: "
                f"{missing_headers}"
            )

        records = []

        for source_row_number, values in enumerate(reader, start=2):

            if not values or all(
                not (value or "").strip() for value in values
            ):
                continue

            row_issues = []

            if len(values) != len(header):
                row_issues.append(
                    f"row has {len(values)} values; "
                    f"expected {len(header)}"
                )

            row = {}

            for index, column in enumerate(header):
                row[column] = (
                    values[index].strip()
                    if index < len(values)
                    else ""
                )

            if len(values) > len(header):
                row["_extra_values"] = values[len(header):]

            records.append(
                (source_row_number, row, row_issues)
            )

    return records


def record_exception(
    connection,
    *,
    entity_type,
    source_filename,
    source_row_number,
    raw_record,
    rejection_reasons,
    customer_id=None,
    account_id=None,
    transaction_id=None,
):
    """Persist one rejected source record with all known rejection reasons."""

    if not rejection_reasons:
        return

    connection.execute(
        """
        INSERT INTO customer360_exceptions (
            entity_type,
            source_filename,
            source_row_number,
            customer_id,
            account_id,
            transaction_id,
            raw_record,
            rejection_reasons,
            recorded_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entity_type,
            source_filename,
            source_row_number,
            customer_id or None,
            account_id or None,
            transaction_id or None,
            json.dumps(
                raw_record,
                sort_keys=True,
                default=str
            ),
            "; ".join(rejection_reasons),
            utc_now(),
        ),
    )


# -----------------------------------------------------------------------------
# Customer reference loading
# -----------------------------------------------------------------------------

def load_customers(connection):
    """Load valid customers; the first valid occurrence of an ID wins."""

    records = read_reference_csv(
        CUSTOMER_FILE,
        CUSTOMER_COLUMNS
    )

    accepted_customer_ids = set()

    for row_number, row, row_issues in records:

        customer_id = row.get("customer_id", "")
        customer_name = row.get("customer_name", "")
        customer_segment = row.get("customer_segment", "")

        reasons = list(row_issues)

        if not customer_id:
            reasons.append("customer_id is missing")

        if not customer_name:
            reasons.append("customer_name is missing")

        if not customer_segment:
            reasons.append("customer_segment is missing")

        if (
            customer_id
            and customer_id in accepted_customer_ids
        ):
            reasons.append(
                "duplicate customer_id; first valid record wins"
            )

        if reasons:

            record_exception(
                connection,
                entity_type="CUSTOMER",
                source_filename=CUSTOMER_FILE.name,
                source_row_number=row_number,
                raw_record=row,
                rejection_reasons=reasons,
                customer_id=customer_id,
            )

            continue

        connection.execute(
            """
            INSERT INTO customers (
                customer_id,
                customer_name,
                customer_segment
            )
            VALUES (?, ?, ?)
            """,
            (
                customer_id,
                customer_name,
                customer_segment,
            ),
        )

        accepted_customer_ids.add(customer_id)

    if not accepted_customer_ids:
        raise ValueError(
            "No valid customer records were loaded"
        )

    return accepted_customer_ids


# -----------------------------------------------------------------------------
# Account reference loading
# -----------------------------------------------------------------------------

def load_accounts(connection, valid_customer_ids):
    """Load valid accounts; reject duplicate IDs and orphan customer IDs."""

    records = read_reference_csv(
        ACCOUNT_FILE,
        ACCOUNT_COLUMNS
    )

    accepted_account_ids = set()
    account_to_customer = {}

    for row_number, row, row_issues in records:

        account_id = row.get("account_id", "")
        customer_id = row.get("customer_id", "")
        branch_id = row.get("branch_id", "")
        account_type = row.get("account_type", "")
        account_status = row.get("account_status", "")

        reasons = list(row_issues)

        if not account_id:
            reasons.append("account_id is missing")

        if not customer_id:
            reasons.append("customer_id is missing")

        if not branch_id:
            reasons.append("branch_id is missing")

        if not account_type:
            reasons.append("account_type is missing")

        if not account_status:
            reasons.append("account_status is missing")

        if (
            account_id
            and account_id in accepted_account_ids
        ):
            reasons.append(
                "duplicate account_id; first valid record wins"
            )

        if (
            customer_id
            and customer_id not in valid_customer_ids
        ):
            reasons.append(
                "customer_id not found in customers reference"
            )

        if reasons:

            record_exception(
                connection,
                entity_type="ACCOUNT",
                source_filename=ACCOUNT_FILE.name,
                source_row_number=row_number,
                raw_record=row,
                rejection_reasons=reasons,
                customer_id=customer_id,
                account_id=account_id,
            )

            continue

        connection.execute(
            """
            INSERT INTO accounts (
                account_id,
                customer_id,
                branch_id,
                account_type,
                account_status
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                account_id,
                customer_id,
                branch_id,
                account_type,
                account_status,
            ),
        )

        accepted_account_ids.add(account_id)

        account_to_customer[account_id] = customer_id

    return accepted_account_ids, account_to_customer


# -----------------------------------------------------------------------------
# Import Week 8 transaction exceptions
# -----------------------------------------------------------------------------

def import_week8_exceptions(connection, account_to_customer):
    """Copy all Week 8 rejected transaction rows into extension exceptions.

    Week 8 exceptions include duplicate IDs, missing fields, bad dates,
    invalid amounts and unknown account references.
    """

    rows = connection.execute(
        """
        SELECT
            source_filename,
            source_row_number,
            transaction_id,
            account_id,
            transaction_date,
            transaction_type,
            amount,
            currency,
            rejection_reasons
        FROM exceptions
        ORDER BY source_filename, source_row_number, exception_id
        """
    ).fetchall()

    for (
        filename,
        row_number,
        transaction_id,
        account_id,
        transaction_date,
        transaction_type,
        amount,
        currency,
        rejection_reasons,
    ) in rows:

        raw_record = {
            "transaction_id": transaction_id,
            "account_id": account_id,
            "transaction_date": transaction_date,
            "transaction_type": transaction_type,
            "amount": amount,
            "currency": currency,
        }

        reasons = [
            reason.strip()
            for reason in (
                rejection_reasons
                or "Week 8 transaction rejected"
            ).split(";")
            if reason.strip()
        ]

        record_exception(
            connection,
            entity_type="TRANSACTION",
            source_filename=filename,
            source_row_number=row_number,
            raw_record=raw_record,
            rejection_reasons=reasons,
            customer_id=account_to_customer.get(account_id),
            account_id=account_id,
            transaction_id=transaction_id,
        )

    return len(rows)


# -----------------------------------------------------------------------------
# Validate accepted Silver account references
# -----------------------------------------------------------------------------

def validate_silver_account_references(
    connection,
    valid_account_ids,
    account_to_customer,
):
    """Find accepted Silver rows whose account is absent from this extension.

    Week 8 Silver already enforces transaction_id uniqueness and NOT NULL
    constraints. Duplicate transaction submissions rejected in Week 8 are
    retained through import_week8_exceptions().
    """

    rows = connection.execute(
        """
        SELECT
            transaction_id,
            account_id,
            transaction_date,
            transaction_type,
            amount,
            currency,
            source_filename,
            source_row_number
        FROM silver_transactions
        ORDER BY source_filename, source_row_number, transaction_id
        """
    ).fetchall()

    unmapped_count = 0
    seen_transaction_ids = set()

    for (
        transaction_id,
        account_id,
        transaction_date,
        transaction_type,
        amount,
        currency,
        filename,
        row_number,
    ) in rows:

        reasons = []

        if not transaction_id:
            reasons.append("transaction_id is missing")

        elif transaction_id in seen_transaction_ids:
            reasons.append(
                "duplicate transaction_id in Silver"
            )

        else:
            seen_transaction_ids.add(transaction_id)

        if not account_id:
            reasons.append("account_id is missing")

        elif account_id not in valid_account_ids:
            reasons.append(
                "account_id not found in Customer 360 accounts reference"
            )

            unmapped_count += 1

        if not transaction_date:
            reasons.append("transaction_date is missing")

        if not transaction_type:
            reasons.append("transaction_type is missing")

        if amount is None:
            reasons.append("amount is missing")

        if not currency:
            reasons.append("currency is missing")

        if reasons:

            raw_record = {
                "transaction_id": transaction_id,
                "account_id": account_id,
                "transaction_date": transaction_date,
                "transaction_type": transaction_type,
                "amount": amount,
                "currency": currency,
            }

            record_exception(
                connection,
                entity_type="TRANSACTION",
                source_filename=filename,
                source_row_number=row_number,
                raw_record=raw_record,
                rejection_reasons=reasons,
                customer_id=account_to_customer.get(account_id),
                account_id=account_id,
                transaction_id=transaction_id,
            )

    return unmapped_count


# -----------------------------------------------------------------------------
# Independent Gold reconciliation
# -----------------------------------------------------------------------------

def reconcile_customer360(connection):
    """Compare Gold transaction counts/totals with independently joined Silver."""

    expected = connection.execute(
        """
        SELECT
            COUNT(*),
            ROUND(COALESCE(SUM(t.amount), 0.0), 2)
        FROM silver_transactions AS t
        INNER JOIN accounts AS a
            ON a.account_id = t.account_id
        """
    ).fetchone()

    actual = connection.execute(
        """
        SELECT
            COALESCE(SUM(transaction_count), 0),
            ROUND(
                COALESCE(SUM(total_transaction_amount), 0.0),
                2
            )
        FROM customer_360
        """
    ).fetchone()

    expected_count = int(expected[0])
    expected_amount = float(expected[1])

    actual_count = int(actual[0])
    actual_amount = float(actual[1])

    if (
        expected_count != actual_count
        or round(expected_amount, 2) != round(actual_amount, 2)
    ):
        raise ValueError(
            "Customer 360 reconciliation failed: "
            f"mapped Silver=({expected_count}, {expected_amount:.2f}), "
            f"Gold=({actual_count}, {actual_amount:.2f})"
        )

    total_silver = connection.execute(
        "SELECT COUNT(*) FROM silver_transactions"
    ).fetchone()[0]

    unmapped_silver = int(total_silver) - expected_count

    return {
        "mapped_silver_transactions": expected_count,
        "unmapped_silver_transactions": unmapped_silver,
        "mapped_silver_amount": round(expected_amount, 2),
        "gold_transaction_count": actual_count,
        "gold_total_amount": round(actual_amount, 2),
    }


# -----------------------------------------------------------------------------
# CSV exports
# -----------------------------------------------------------------------------

def export_query(connection, query, output_path):
    """Export query results using a temporary file and atomic replacement."""

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temporary_path = output_path.with_name(
        output_path.name + ".tmp"
    )

    cursor = connection.execute(query)

    headers = [
        column[0]
        for column in cursor.description
    ]

    rows = cursor.fetchall()

    try:

        with temporary_path.open(
            "w",
            newline="",
            encoding="utf-8"
        ) as output:

            writer = csv.writer(output)

            writer.writerow(headers)
            writer.writerows(rows)

        temporary_path.replace(output_path)

    except Exception:

        if temporary_path.exists():
            temporary_path.unlink()

        raise

    return len(rows)


# -----------------------------------------------------------------------------
# Main build function
# -----------------------------------------------------------------------------

def build_customer360():
    """Build Customer 360 in the Week 8 database and export CSV snapshots."""

    if not SCHEMA_FILE.is_file():
        raise FileNotFoundError(
            f"Customer 360 schema not found: {SCHEMA_FILE}"
        )

    connection = connect(DB_PATH)

    try:

        # Preserve a recoverable copy before changing extension tables.
        backup_path = create_database_backup(connection)

        schema_sql = SCHEMA_FILE.read_text(
            encoding="utf-8"
        )

        connection.executescript(schema_sql)

        with connection:

            # Clear only tables owned by this extension.
            # Week 8 Bronze, Silver, Exceptions and branch-level Gold
            # are deliberately untouched.

            connection.execute(
                "DELETE FROM customer360_exceptions"
            )

            connection.execute(
                "DELETE FROM accounts"
            )

            connection.execute(
                "DELETE FROM customers"
            )

            # Load customers first.
            valid_customer_ids = load_customers(connection)

            # Accounts depend on valid customers.
            valid_account_ids, account_to_customer = load_accounts(
                connection,
                valid_customer_ids
            )

            # Preserve all previous Week 8 rejected transactions.
            imported_week8_exceptions = import_week8_exceptions(
                connection,
                account_to_customer
            )

            # Verify accepted Silver account references.
            unmapped_silver_exceptions = (
                validate_silver_account_references(
                    connection,
                    valid_account_ids,
                    account_to_customer
                )
            )

            # Verify one Gold row per customer.
            customer_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM customers"
                ).fetchone()[0]
            )

            account_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM accounts"
                ).fetchone()[0]
            )

            gold_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM customer_360"
                ).fetchone()[0]
            )

            if customer_count != gold_count:
                raise ValueError(
                    "Customer 360 grain check failed: "
                    f"customers={customer_count}, "
                    f"gold_rows={gold_count}"
                )

            # Compare independently calculated Silver and Gold metrics.
            reconciliation = reconcile_customer360(connection)

            if gold_count == 0:
                raise ValueError(
                    "Customer 360 produced no customer rows"
                )

        # Database changes are committed at this point.
        # CSV files are reproducible output snapshots.
        # SQLite customer_360 remains the database data product.

        OUTPUT_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        gold_exported = export_query(
            connection,
            """
            SELECT
                customer_id,
                customer_name,
                account_count,
                transaction_count,
                total_transaction_amount,
                last_transaction_date
            FROM customer_360
            ORDER BY customer_id
            """,
            GOLD_FILE
        )

        exception_exported = export_query(
            connection,
            """
            SELECT
                exception_id,
                entity_type,
                source_filename,
                source_row_number,
                customer_id,
                account_id,
                transaction_id,
                raw_record,
                rejection_reasons,
                recorded_at
            FROM customer360_exceptions
            ORDER BY exception_id
            """,
            EXCEPTIONS_FILE
        )

        silver_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM silver_transactions"
            ).fetchone()[0]
        )

        exception_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM customer360_exceptions"
            ).fetchone()[0]
        )

        exception_breakdown = {
            entity_type: count
            for entity_type, count in connection.execute(
                """
                SELECT
                    entity_type,
                    COUNT(*)
                FROM customer360_exceptions
                GROUP BY entity_type
                ORDER BY entity_type
                """
            ).fetchall()
        }

        summary = {
            "database": str(DB_PATH),
            "backup": str(backup_path),
            "customers_loaded": customer_count,
            "accounts_loaded": account_count,
            "silver_transactions_total": silver_count,
            "customer_360_rows": gold_count,
            "exceptions_total": exception_count,
            "exceptions_by_entity": exception_breakdown,
            "week8_exceptions_imported": imported_week8_exceptions,
            "unmapped_silver_transactions_found": (
                unmapped_silver_exceptions
            ),
            **reconciliation,
            "gold_csv_rows_exported": gold_exported,
            "exception_csv_rows_exported": exception_exported,
            "gold_csv": str(GOLD_FILE),
            "exceptions_csv": str(EXCEPTIONS_FILE),
        }

        print("\nCUSTOMER 360 BUILD SUCCESSFUL")
        print("=" * 32)

        for key, value in summary.items():
            print(f"{key}: {value}")

        return summary

    finally:
        connection.close()


if __name__ == "__main__":
    build_customer360()
