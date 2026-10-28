"""
publish.py - the "publish" step: replace the published Gold output.

Called only after validate and transform succeeded (the runner enforces this).
- Gold CSV: written to a temporary file, then replaced into place at the end.
- Gold table: old rows deleted and new rows inserted in ONE transaction, so a
  failed insert rolls back and the previous Gold rows stay.
The database and the CSV are two files and are not replaced as one unit.
"""

import csv
import os
from pathlib import Path

from src.capstone.db import BASE_DIR

GOLD_CSV = BASE_DIR / "output" / "capstone" / "gold_branch_daily_summary.csv"
HEADER = ["branch_id", "transaction_date", "transaction_type",
          "transaction_count", "total_amount"]


def publish(con, run_id, gold_rows, csv_path=GOLD_CSV):
    """Replace Gold table and Gold CSV with gold_rows. Returns the row count."""
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = csv_path.with_name(csv_path.name + ".tmp")
    try:
        with open(tmp_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(HEADER)
            writer.writerows(gold_rows)
        with con:
            con.execute("DELETE FROM gold_branch_daily_summary")
            con.executemany(
                "INSERT INTO gold_branch_daily_summary (branch_id, transaction_date, "
                "transaction_type, transaction_count, total_amount, published_run_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [(*row, run_id) for row in gold_rows],
            )
        os.replace(tmp_path, csv_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    return len(gold_rows)
