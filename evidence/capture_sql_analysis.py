from pathlib import Path

from src.analysis import run_query
from src.database import get_connection


def capture_sql_analysis():
    """Run all SQL analysis queries and save their results as evidence."""

    base_dir = Path(__file__).resolve().parent.parent
    sql_file = base_dir / "sql" / "analysis_queries.sql"
    evidence_file = base_dir / "evidence" / "sql_analysis_results.txt"

    connection = get_connection()

    sql_text = sql_file.read_text(encoding="utf-8")

    queries = [
        query.strip()
        for query in sql_text.split(";")
        if query.strip()
    ]

    with evidence_file.open("w", encoding="utf-8") as file:

        file.write("WEEK 4 SQL ANALYSIS EVIDENCE\n")
        file.write("=" * 35 + "\n\n")

        for query_number, query in enumerate(queries, start=1):

            columns, rows = run_query(connection, query)

            file.write(f"QUERY {query_number:02d} RESULTS\n")
            file.write("-" * 30 + "\n")

            file.write(str(columns) + "\n")

            for row in rows:
                file.write(str(row) + "\n")

            file.write("\n")

    connection.close()

    print(f"SQL analysis evidence written to: {evidence_file}")


if __name__ == "__main__":
    capture_sql_analysis()