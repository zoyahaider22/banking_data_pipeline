from pathlib import Path

from src.database import get_connection


def get_table_counts(connection):
    """Return row counts for all core banking tables."""

    tables = [
        "customer",
        "branch",
        "account",
        "bank_transaction",
    ]

    counts = {}

    for table in tables:
        result = connection.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()

        counts[table] = result[0]

    return counts



def get_relationship_counts(connection):
    """Verify that foreign-key relationships resolve correctly."""

    queries = {
        "customer_account_links": """
            SELECT COUNT(*)
            FROM account AS a
            JOIN customer AS c
                ON a.customer_id = c.customer_id
        """,

        "branch_account_links": """
            SELECT COUNT(*)
            FROM account AS a
            JOIN branch AS b
                ON a.branch_id = b.branch_id
        """,

        "account_transaction_links": """
            SELECT COUNT(*)
            FROM bank_transaction AS t
            JOIN account AS a
                ON t.account_id = a.account_id
        """,
    }

    counts = {}

    for name, query in queries.items():
        counts[name] = connection.execute(query).fetchone()[0]

    return counts

  

def run_query(connection, query):
    """Execute a SQL query and return column names and rows."""

    cursor = connection.execute(query)

    columns = [description[0] for description in cursor.description]
    rows = cursor.fetchall()

    return columns, rows   

if __name__ == "__main__":
    connection = get_connection()

    counts = get_table_counts(connection)

    print("Database row counts:")

    for table, count in counts.items():
        print(f"{table}: {count}")

    relationship_counts = get_relationship_counts(connection)

    print("\nRelationship counts:")

    for relationship, count in relationship_counts.items():
        print(f"{relationship}: {count}")

    # ================================================
    # RUN ALL SQL ANALYSIS QUERIES
    # ================================================

    sql_file = Path(__file__).resolve().parent.parent / "sql" / "analysis_queries.sql"

    sql_text = sql_file.read_text(encoding="utf-8")

    # Split the SQL file into individual queries.
    queries = [
        query.strip()
        for query in sql_text.split(";")
        if query.strip()
    ]

    for query_number, query in enumerate(queries, start=1):

        columns, rows = run_query(connection, query)

        print(f"\nQuery {query_number:02d} Results:")
        print(columns)

        for row in rows:
            print(row)

    connection.close()