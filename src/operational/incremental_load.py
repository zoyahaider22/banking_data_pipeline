import csv
import sqlite3
from datetime import datetime

from src.operational.config import DAILY_DIR
from src.operational.database import get_connection


DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y"]

UPSERT_SQL = """
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
    ON CONFLICT(transaction_id) DO UPDATE SET
        account_id = excluded.account_id,
        transaction_date = excluded.transaction_date,
        transaction_type = excluded.transaction_type,
        amount = excluded.amount,
        currency = excluded.currency,
        source_file = excluded.source_file
    WHERE excluded.source_file >= bank_transaction.source_file
"""


def normalize_date(raw_date):
    """Convert supported date formats to YYYY-MM-DD."""

    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(raw_date.strip(), date_format).strftime("%Y-%m-%d")
        except ValueError:
            continue

    raise ValueError(f"Unrecognized date format: {raw_date}")


def normalize_amount(raw_amount):
    """Convert an amount string such as '120' or '90.00' to a float."""

    return round(float(raw_amount.strip()), 2)


def normalize_row(row, source_file):
    """Return a clean tuple of values in table column order."""

    transaction_type = row["transaction_type"].strip().upper()
    currency = row["currency"].strip().upper()
    amount = normalize_amount(row["amount"])

    if transaction_type not in ("CREDIT", "DEBIT"):
        raise ValueError(f"Invalid transaction type: {transaction_type}")

    if amount <= 0:
        raise ValueError(f"Amount must be positive: {amount}")

    if currency != "USD":
        raise ValueError(f"Unsupported currency: {currency}")

    return (
        row["transaction_id"].strip(),
        row["account_id"].strip(),
        normalize_date(row["transaction_date"]),
        transaction_type,
        amount,
        currency,
        source_file,
    )


def load_daily_file(connection, csv_file):
    """UPSERT one daily file and return per-row outcome counts."""

    counts = {
        "inserted": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped_stale": 0,
        "rejected": 0,
    }

    with open(csv_file, "r", newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            try:
                values = normalize_row(row, csv_file.name)

                existing = connection.execute(
                    """
                    SELECT account_id, transaction_date, transaction_type,
                           amount, currency, source_file
                    FROM bank_transaction
                    WHERE transaction_id = ?
                    """,
                    (values[0],),
                ).fetchone()

                connection.execute(UPSERT_SQL, values)

            except (ValueError, sqlite3.IntegrityError) as error:
                counts["rejected"] += 1
                print(f"  Rejected {row.get('transaction_id')}: {error}")
                continue

            if existing is None:
                counts["inserted"] += 1
            elif existing[5] > values[6]:
                counts["skipped_stale"] += 1
            elif tuple(existing) != values[1:]:
                counts["updated"] += 1
            else:
                counts["unchanged"] += 1

    connection.commit()

    return counts


def run_incremental_load():
    """Process all daily files in date order."""

    connection = get_connection()
    connection.execute("PRAGMA foreign_keys = ON;")

    try:
        for csv_file in sorted(DAILY_DIR.glob("transactions_*.csv")):
            counts = load_daily_file(connection, csv_file)

            print(
                f"{csv_file.name}: "
                f"inserted={counts['inserted']}, "
                f"updated={counts['updated']}, "
                f"unchanged={counts['unchanged']}, "
                f"skipped_stale={counts['skipped_stale']}, "
                f"rejected={counts['rejected']}"
            )

        total = connection.execute(
            "SELECT COUNT(*) FROM bank_transaction"
        ).fetchone()[0]

        print(f"\nTotal transactions in bank_transaction: {total}")

    finally:
        connection.close()


if __name__ == "__main__":
    run_incremental_load()