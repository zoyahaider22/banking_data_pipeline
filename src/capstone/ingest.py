"""
ingest.py - the "ingest" step: load source rows into Bronze exactly as received.

For each recognized file:
  - if the same content (SHA-256) was already fully processed in an earlier run,
    nothing is loaded and file_audit records it as SKIPPED_IDENTICAL
  - otherwise every data row is stored in bronze_transactions as text, with
    filename, branch_id, run_id, load timestamp and source_row_number
    (1 = first data row after the header; blank lines are not counted)
Nothing is judged valid or invalid here - that is the validate step.
A wrong header or a wrong number of fields raises ValueError before
anything from that file is written.
"""

import csv
from pathlib import Path

from src.capstone.db import utc_now
from src.ingestion.config import REQUIRED_COLUMNS


def read_source_rows(path):
    """Return the data rows of a CSV file as lists of strings, unchanged."""
    name = Path(path).name
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            raise ValueError(name + ": file is empty")
        if [h.strip() for h in header] != REQUIRED_COLUMNS:
            raise ValueError(name + ": header does not match " + ",".join(REQUIRED_COLUMNS))
        rows = []
        for row in reader:
            if not row:
                continue
            if len(row) != len(REQUIRED_COLUMNS):
                raise ValueError(
                    name + ": data row " + str(len(rows) + 1) + " has "
                    + str(len(row)) + " fields, expected " + str(len(REQUIRED_COLUMNS))
                )
            rows.append(row)
    return rows


def find_processed_copy(con, sha256):
    """Return (filename, run_id) of an earlier PROCESSED file with the same hash, or None."""
    return con.execute(
        "SELECT source_filename, run_id FROM file_audit "
        "WHERE file_sha256 = ? AND file_status = 'PROCESSED' "
        "ORDER BY run_id LIMIT 1",
        (sha256,),
    ).fetchone()


def ingest(con, run_id, recognized):
    """Load the recognized files into Bronze. Returns one summary dict per file."""
    results = []
    for rec in recognized:
        prior = find_processed_copy(con, rec["sha256"])
        if prior:
            note = "identical content already processed as " + prior[0] + " in " + prior[1]
            with con:
                con.execute(
                    "INSERT INTO file_audit (run_id, source_filename, branch_id, file_date, "
                    "file_sha256, source_rows, accepted_rows, rejected_rows, file_status, note) "
                    "VALUES (?, ?, ?, ?, ?, 0, 0, 0, 'SKIPPED_IDENTICAL', ?)",
                    (run_id, rec["filename"], rec["branch_id"], rec["file_date"], rec["sha256"], note),
                )
            results.append({"filename": rec["filename"], "status": "SKIPPED_IDENTICAL", "source_rows": 0})
            continue

        rows = read_source_rows(rec["path"])
        load_ts = utc_now()
        with con:
            con.executemany(
                "INSERT INTO bronze_transactions (run_id, source_filename, branch_id, "
                "source_row_number, load_timestamp, transaction_id, account_id, "
                "transaction_date, transaction_type, amount, currency) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(run_id, rec["filename"], rec["branch_id"], n, load_ts, *row)
                 for n, row in enumerate(rows, start=1)],
            )
            con.execute(
                "INSERT INTO file_audit (run_id, source_filename, branch_id, file_date, "
                "file_sha256, source_rows, file_status) VALUES (?, ?, ?, ?, ?, ?, 'LOADED')",
                (run_id, rec["filename"], rec["branch_id"], rec["file_date"], rec["sha256"], len(rows)),
            )
        results.append({"filename": rec["filename"], "status": "LOADED", "source_rows": len(rows)})
    return results
