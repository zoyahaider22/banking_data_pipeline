import csv

from src.operational.config import (
    CUSTOMERS_FILE,
    BRANCHES_FILE,
    ACCOUNTS_FILE,
    VALID_TRANSACTIONS_FILE,
)


def load_csv_to_table(connection, csv_file, table_name, columns):
    """Load CSV records into a SQLite table."""

    with open(csv_file, "r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        rows = [
            tuple(row[column] for column in columns)
            for row in reader
        ]

    placeholders = ", ".join("?" for _ in columns)
    column_names = ", ".join(columns)

    sql = f"""
        INSERT INTO {table_name} ({column_names})
        VALUES ({placeholders})
    """

    connection.executemany(sql, rows)

    return len(rows)


def load_customers(connection):
    return load_csv_to_table(
        connection,
        CUSTOMERS_FILE,
        "customer",
        [
            "customer_id",
            "customer_name",
            "email",
            "customer_segment",
        ],
    )


def load_branches(connection):
    return load_csv_to_table(
        connection,
        BRANCHES_FILE,
        "branch",
        [
            "branch_id",
            "branch_name",
            "city",
            "state",
        ],
    )


def load_accounts(connection):
    return load_csv_to_table(
        connection,
        ACCOUNTS_FILE,
        "account",
        [
            "account_id",
            "customer_id",
            "branch_id",
            "account_type",
            "account_status",
        ],
    )


def load_transactions(connection):
    return load_csv_to_table(
        connection,
        VALID_TRANSACTIONS_FILE,
        "bank_transaction",
        [
            "transaction_id",
            "account_id",
            "transaction_date",
            "transaction_type",
            "amount",
            "currency",
            "source_file",
        ],
    )


def load_all_data(connection):
    """Load all reference and transaction data in FK-safe order."""

    customer_count = load_customers(connection)
    branch_count = load_branches(connection)
    account_count = load_accounts(connection)
    transaction_count = load_transactions(connection)

    connection.commit()

    return {
        "customers": customer_count,
        "branches": branch_count,
        "accounts": account_count,
        "transactions": transaction_count,
    }