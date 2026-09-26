from pathlib import Path

from src.database import get_connection


def run_query_plan():
    """Capture SQLite query plan before and after adding an index."""

    base_dir = Path(__file__).resolve().parent.parent
    evidence_file = base_dir / "evidence" / "query_plan_results.txt"

    connection = get_connection()

    query = """
        SELECT
            t.transaction_id,
            t.transaction_date,
            t.transaction_type,
            t.amount,
            t.currency,
            a.account_id,
            c.customer_id,
            c.customer_name
        FROM bank_transaction AS t
        JOIN account AS a
            ON t.account_id = a.account_id
        JOIN customer AS c
            ON a.customer_id = c.customer_id
        ORDER BY
            t.transaction_date,
            t.transaction_id;
    """

    # ------------------------------------------------
    # BEFORE INDEX
    # ------------------------------------------------

    before_plan = connection.execute(
        "EXPLAIN QUERY PLAN " + query
    ).fetchall()

    # ------------------------------------------------
    # CREATE INDEX
    # ------------------------------------------------

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_bank_transaction_account_id
        ON bank_transaction(account_id)
    """)

    connection.commit()

    # ------------------------------------------------
    # AFTER INDEX
    # ------------------------------------------------

    after_plan = connection.execute(
        "EXPLAIN QUERY PLAN " + query
    ).fetchall()

    # ------------------------------------------------
    # SAVE EVIDENCE
    # ------------------------------------------------

    with open(evidence_file, "w", encoding="utf-8") as file:

        file.write("WEEK 4 QUERY PLAN / INDEX EVIDENCE\n")
        file.write("=" * 45 + "\n\n")

        file.write("QUERY USED\n")
        file.write("-" * 45 + "\n")
        file.write(query.strip() + "\n\n")

        file.write("QUERY PLAN BEFORE INDEX\n")
        file.write("-" * 45 + "\n")

        for row in before_plan:
            file.write(str(row) + "\n")

        file.write("\n")

        file.write("INDEX CREATED\n")
        file.write("-" * 45 + "\n")
        file.write(
            "idx_bank_transaction_account_id "
            "ON bank_transaction(account_id)\n\n"
        )

        file.write("QUERY PLAN AFTER INDEX\n")
        file.write("-" * 45 + "\n")

        for row in after_plan:
            file.write(str(row) + "\n")

        file.write("\n")
        file.write("NOTE\n")
        file.write("-" * 45 + "\n")
        file.write(
            "The database contains only a small number of rows, "
            "so no measurable runtime improvement is claimed. "
            "The EXPLAIN QUERY PLAN output is used to show how "
            "the index changes SQLite's access strategy.\n"
        )

    connection.close()

    print(f"Query plan evidence written to: {evidence_file}")


if __name__ == "__main__":
    run_query_plan()