import sqlite3

from src.schema import create_schema


def run_integrity_evidence():
    """Capture SQLite constraint violations for Week 4 evidence."""

    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON;")

    create_schema(connection)

    evidence = []

    # Seed an existing customer so the duplicate primary-key
    # evidence test has a real duplicate to violate.
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
        "Existing Customer",
        "existing@example.com",
        "RETAIL",
    ),
)

    connection.commit()

    tests = [
        (
            "Foreign Key - Nonexistent Account",
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
                "EVIDENCE_FK_001",
                "A9999",
                "2026-09-06",
                "CREDIT",
                100.00,
                "USD",
                "evidence.csv",
            ),
        ),
        (
            "Foreign Key - Nonexistent Customer",
            """
            INSERT INTO account (
                account_id,
                customer_id,
                branch_id,
                account_type,
                account_status
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "EVIDENCE_CUST_001",
                "C9999",
                "BR001",
                "CHECKING",
                "ACTIVE",
            ),
        ),
        (
            "Primary Key - Duplicate Customer ID",
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
                "Duplicate Customer",
                "duplicate@example.com",
                "RETAIL",
            ),
        ),
        (
            "CHECK - Negative Transaction Amount",
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
                "EVIDENCE_AMOUNT_001",
                "A1001",
                "2026-09-06",
                "CREDIT",
                -50.00,
                "USD",
                "evidence.csv",
            ),
        ),
        (
            "NOT NULL - Missing Customer Name",
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
                "EVIDENCE_NULL_001",
                None,
                "null@example.com",
                "RETAIL",
            ),
        ),
    ]

    for name, sql, values in tests:
        try:
            connection.execute(sql, values)
            evidence.append(
                f"{name}\n"
                f"Result: INSERT unexpectedly succeeded\n"
            )

        except sqlite3.IntegrityError as error:
            evidence.append(
                f"{name}\n"
                f"Result: INSERT rejected\n"
                f"SQLite error: {error}\n"
            )

    connection.close()

    evidence_file = "evidence/integrity_failures.txt"

    with open(evidence_file, "w", encoding="utf-8") as file:
        file.write("WEEK 4 DATABASE INTEGRITY EVIDENCE\n")
        file.write("=" * 40 + "\n\n")

        for result in evidence:
            file.write(result)
            file.write("\n")

    print(f"Integrity evidence written to: {evidence_file}")


if __name__ == "__main__":
    run_integrity_evidence()