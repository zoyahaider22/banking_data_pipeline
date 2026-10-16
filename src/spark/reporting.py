import csv
from pathlib import Path

from src.spark.load_data import ROOT

REPORT_DIR = ROOT / "output" / "reports"
REPORT_NAME = "branch_summary.csv"
REPORT_COLUMNS = ["branch_id", "transaction_count", "gross_amount", "net_cash_flow"]


class DataQualityError(Exception):
    pass


def raise_if_checks_failed(results):
    failed = [(name, bad) for name, bad in results if bad > 0]
    if failed:
        details = "; ".join(f"{name}: {bad}" for name, bad in failed)
        raise DataQualityError(f"{len(failed)} data quality check(s) failed - {details}")


def summary_to_rows(summary):
    return [row.asDict() for row in summary.collect()]


def write_branch_report(rows, output_dir=REPORT_DIR):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / REPORT_NAME
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(REPORT_COLUMNS)
        for row in rows:
            writer.writerow([row[c] for c in REPORT_COLUMNS])
    return {
        "path": str(path),
        "rows": len(rows),
        "transaction_count": sum(r["transaction_count"] for r in rows),
        "net_cash_flow": round(sum(r["net_cash_flow"] for r in rows), 2),
    }
