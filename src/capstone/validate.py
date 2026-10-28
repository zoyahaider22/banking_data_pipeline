"""
validate.py (capstone) - the "validate" step: Bronze -> Silver and Exceptions.

Rules reuse the single-value checks from src/ingestion/validate.py (Week 3).
New rules here: unknown account (reference table) and duplicate transaction_id.

Duplicate policy A: a row is a duplicate if its transaction_id was already
accepted - in an earlier run (already in Silver) or earlier in this run.
Rows are processed in the order: file_date, branch_id, filename, source row
number, so the first accepted row wins. Rejected rows keep ALL their reasons.

The whole step runs in ONE transaction: if anything fails (including a
reconciliation mismatch), nothing is written.
"""

import csv

from src.capstone.db import BASE_DIR
from src.ingestion import validate as rules

ACCOUNTS_PATH = BASE_DIR / "data" / "reference" / "accounts.csv"


def load_accounts(path=ACCOUNTS_PATH):
    """Set of account_ids from the accounts reference table."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {row["account_id"].strip() for row in csv.DictReader(f)}


def row_reasons(values, accounts, accepted_ids):
    """All rejection reasons for one row (empty list = row is accepted)."""
    tid, acc, date, ttype, amount, currency = values
    reasons = []
    if rules.is_missing_value(tid):
        reasons.append("transaction_id is missing")
    if rules.is_missing_value(acc):
        reasons.append("account_id is missing")
    if not rules.is_valid_date(date):
        reasons.append("transaction_date must be a valid date in YYYY-MM-DD format")
    if not rules.is_valid_transaction_type(ttype):
        reasons.append("transaction_type must be CREDIT or DEBIT")
    if not rules.is_valid_amount(amount):
        reasons.append("amount must be present, numeric, and greater than 0")
    if not rules.is_valid_currency(currency):
        reasons.append("currency must be USD")
    if not rules.is_missing_value(acc) and acc not in accounts:
        reasons.append("account_id not found in accounts reference")
    if not rules.is_missing_value(tid) and tid in accepted_ids:
        reasons.append("duplicate transaction_id already accepted (first accepted record wins)")
    return reasons


def validate(con, run_id, accounts=None):
    """Validate every file loaded in this run. Returns one summary dict per file."""
    if accounts is None:
        accounts = load_accounts()
    results = []
    with con:
        accepted_ids = {r[0] for r in con.execute("SELECT transaction_id FROM silver_transactions")}
        files = con.execute(
            "SELECT source_filename, file_date, branch_id, source_rows FROM file_audit "
            "WHERE run_id = ? AND file_status = 'LOADED'",
            (run_id,),
        ).fetchall()
        files.sort(key=lambda f: (f[1], f[2], f[0]))

        for filename, file_date, branch_id, source_rows in files:
            bronze = con.execute(
                "SELECT bronze_id, source_row_number, transaction_id, account_id, "
                "transaction_date, transaction_type, amount, currency "
                "FROM bronze_transactions WHERE run_id = ? AND source_filename = ? "
                "ORDER BY source_row_number",
                (run_id, filename),
            ).fetchall()
            accepted = 0
            rejected = 0
            for bronze_id, row_number, *values in bronze:
                reasons = row_reasons(values, accounts, accepted_ids)
                if reasons:
                    con.execute(
                        "INSERT INTO exceptions (run_id, source_filename, branch_id, "
                        "source_row_number, bronze_id, transaction_id, account_id, "
                        "transaction_date, transaction_type, amount, currency, rejection_reasons) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (run_id, filename, branch_id, row_number, bronze_id, *values, "; ".join(reasons)),
                    )
                    rejected += 1
                else:
                    tid, acc, date, ttype, amount, currency = values
                    con.execute(
                        "INSERT INTO silver_transactions (transaction_id, account_id, branch_id, "
                        "transaction_date, transaction_type, amount, currency, source_filename, "
                        "source_row_number, bronze_id, run_id) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (tid, acc, branch_id, date, ttype, float(amount), currency,
                         filename, row_number, bronze_id, run_id),
                    )
                    accepted_ids.add(tid)
                    accepted += 1

            if len(bronze) != source_rows or accepted + rejected != source_rows:
                raise ValueError(
                    filename + ": reconciliation failed - source_rows=" + str(source_rows)
                    + ", bronze=" + str(len(bronze)) + ", accepted=" + str(accepted)
                    + ", rejected=" + str(rejected)
                )
            con.execute(
                "UPDATE file_audit SET accepted_rows = ?, rejected_rows = ?, "
                "file_status = 'PROCESSED' WHERE run_id = ? AND source_filename = ?",
                (accepted, rejected, run_id, filename),
            )
            results.append({"filename": filename, "source_rows": source_rows,
                            "accepted_rows": accepted, "rejected_rows": rejected})
    return results
