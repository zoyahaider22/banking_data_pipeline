import sqlite3

from src.config import DATABASE_FILE


def get_connection():
    """Create and configure a SQLite database connection."""

    connection = sqlite3.connect(DATABASE_FILE)

    # Enforce foreign-key constraints for this connection.
    connection.execute("PRAGMA foreign_keys = ON;")

    return connection

if __name__ == "__main__":
    connection = get_connection()

    print("Database connection successful.")
    print("Foreign keys enabled:", connection.execute(
        "PRAGMA foreign_keys;"
    ).fetchone()[0])

    connection.close()