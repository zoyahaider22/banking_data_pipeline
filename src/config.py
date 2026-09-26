from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

CUSTOMERS_FILE = DATA_DIR / "customers.csv"
BRANCHES_FILE = DATA_DIR / "branches.csv"
ACCOUNTS_FILE = DATA_DIR / "accounts.csv"
VALID_TRANSACTIONS_FILE = DATA_DIR / "valid_transactions.csv"

DATABASE_FILE = BASE_DIR / "banking.db"