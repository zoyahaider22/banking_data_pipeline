from src.operational.config import DATABASE_FILE
from src.operational.database import get_connection
from src.operational.schema import create_schema
from src.operational.loader import load_all_data


def reset_database():
    """Remove the existing database so the build starts cleanly."""

    if DATABASE_FILE.exists():
        DATABASE_FILE.unlink()
        print("Existing database removed.")


def build_database():
    """Create a fresh database and load all supplied banking data."""

    reset_database()

    connection = get_connection()

    try:
        create_schema(connection)

        counts = load_all_data(connection)

        print("\nDatabase build completed successfully.")
        print(f"Customers loaded: {counts['customers']}")
        print(f"Branches loaded: {counts['branches']}")
        print(f"Accounts loaded: {counts['accounts']}")
        print(f"Transactions loaded: {counts['transactions']}")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    build_database()