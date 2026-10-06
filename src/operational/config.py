from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent

DATA_DIR = BASE_DIR / "data"
DAILY_DIR = DATA_DIR / "daily"

CUSTOMERS_FILE = DATA_DIR / "reference" / "customers.csv"
BRANCHES_FILE = DATA_DIR / "reference" / "branches.csv"
ACCOUNTS_FILE = DATA_DIR / "reference" / "accounts.csv"
VALID_TRANSACTIONS_FILE = DATA_DIR / "validated" / "valid_transactions.csv"

DATABASE_FILE = BASE_DIR / "database" / "banking.db"