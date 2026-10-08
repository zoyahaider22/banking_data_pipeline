import csv
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BANKING_DB = ROOT / "database" / "banking.db"
OUTPUT_PATH = ROOT / "data" / "generated" / "synthetic_transactions.csv"

ROW_COUNT = 100_000
SEED = 42
START_DATE = date(2026, 1, 1)
END_DATE = date(2026, 9, 30)
FIELDS = [
    "transaction_id", "account_id", "transaction_date",
    "transaction_type", "amount", "currency",
]


def load_account_ids(db_path=BANKING_DB):
    con = sqlite3.connect(f"{Path(db_path).as_uri()}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT account_id FROM account ORDER BY account_id")
        return [r[0] for r in rows]
    finally:
        con.close()


def generate_rows(account_ids, row_count=ROW_COUNT, seed=SEED):
    rng = random.Random(seed)
    days = (END_DATE - START_DATE).days + 1
    rows = []
    for i in range(1, row_count + 1):
        amount = round(min(max(rng.lognormvariate(4.5, 1.0), 1.0), 5000.0), 2)
        rows.append({
            "transaction_id": f"G{i:06d}",
            "account_id": rng.choice(account_ids),
            "transaction_date": (START_DATE + timedelta(days=rng.randrange(days))).isoformat(),
            "transaction_type": rng.choices(["CREDIT", "DEBIT"], weights=[55, 45])[0],
            "amount": amount,
            "currency": "USD",
        })
    return rows


def write_csv(rows, path=OUTPUT_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    account_ids = load_account_ids()
    rows = generate_rows(account_ids)
    write_csv(rows)
    print("Accounts used  :", len(account_ids))
    print("Rows generated :", len(rows))
    print("Written to     :", OUTPUT_PATH)