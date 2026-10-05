from src.database import get_connection


def create_schema(connection):
    """Create all banking database tables."""

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS customer (
            customer_id TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            email TEXT NOT NULL,
            customer_segment TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS branch (
            branch_id TEXT PRIMARY KEY,
            branch_name TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS account (
            account_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            branch_id TEXT NOT NULL,
            account_type TEXT NOT NULL,
            account_status TEXT NOT NULL,

            FOREIGN KEY (customer_id)
                REFERENCES customer(customer_id),

            FOREIGN KEY (branch_id)
                REFERENCES branch(branch_id)
        );

        CREATE TABLE IF NOT EXISTS bank_transaction (
            transaction_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            transaction_date TEXT NOT NULL,
            transaction_type TEXT NOT NULL
                CHECK (transaction_type IN ('CREDIT', 'DEBIT')),
            amount REAL NOT NULL
                CHECK (amount > 0),
            currency TEXT NOT NULL
                CHECK (currency = 'USD'),
            source_file TEXT NOT NULL,

            FOREIGN KEY (account_id)
                REFERENCES account(account_id)
        );
        """
    )

    connection.commit()


if __name__ == "__main__":
    connection = get_connection()
    create_schema(connection)
    print("Database schema created successfully.")
    connection.close()