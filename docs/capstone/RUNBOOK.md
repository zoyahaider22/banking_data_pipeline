# Runbook - capstone pipeline

Run every command from the repository root with the virtual environment active.

## 0. Start a terminal

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Spark runs print a winutils warning, a pandas FutureWarning and `SUCCESS: The process with PID ... has been terminated` lines. They appeared in every Spark run and are not errors.

## 1. Normal run

1. Put the delivered files in `data\capstone\landing`, named `BR<digits>_<YYYYMMDD>_TRANSACTION.csv`.
2. Run `python -m src.capstone.pipeline`.
3. Check the result: `status : SUCCESS`, and `$LASTEXITCODE` is 0 (it is 1 for a failed run).
4. The `reason` line gives the run summary: files loaded, files skipped as identical, unrecognized files, accepted rows, rejected rows, Gold rows.
5. Outputs: `output\capstone\banking_capstone.db` (all tables) and `output\capstone\gold_branch_daily_summary.csv`.

Notes:
- A file with a name that does not match the pattern is listed as `unrecognized` with a reason and is not loaded. The run still succeeds.
- A run that reaches transform starts Spark. Runs with Spark took 14 to 47 seconds in measured tests on this machine; the cause of the variation is undetermined.
- Rejected rows do not fail a run. They go to the Exceptions table with all their reasons.

## 2. Rerun

Run the same command again.

- A file that is identical (same SHA-256) to a file already marked `PROCESSED` is skipped and shown as `SKIPPED_IDENTICAL` with 0 rows. Silver, Exceptions, Gold and the Gold CSV stay unchanged. A new run ID and new audit rows are created, and the Gold `published_run_id` changes.
- A file with the same name but different content is processed. Any `transaction_id` that was already accepted is rejected as a duplicate, so a correction to an accepted transaction is kept in Exceptions and does not change Silver or Gold.

## 3. Failed run: diagnosis

A failed run prints `status : FAILED`, and the `reason` names the failing step. The same text is stored in `run_audit`. Use query A in section 5.

| Reason starts with | Meaning | What to do | Seen on |
|---|---|---|---|
| `ingest failed: ValueError: <file>: header does not match ...` | The first line of that file is not the six expected columns | Fix the header of that file | real database |
| `ingest failed: ValueError: <file>: data row N has M fields, expected 6` | A row has the wrong number of fields | Fix that row in the file | pytest only |
| `ingest failed: ValueError: <file>: file is empty` | The file has no content | Replace the file | pytest only |
| `discover failed: FileNotFoundError` | The landing folder does not exist | Check `data\capstone\landing` | pytest only |
| `validate failed: ValueError: ... reconciliation failed` | Source rows do not equal accepted plus rejected | Stop and investigate Bronze and `file_audit` before any rerun | pytest only |
| `transform failed: ValueError: PySpark and SQL Gold results differ` | The two Gold calculations disagree | Stop and investigate Silver and both calculations | pytest only (with a stand-in) |
| `publish failed: ...` | Writing Gold failed | Read the error; the previous Gold table and CSV stay in place | pytest only |

What a failed run leaves behind:
- The previous Gold table and CSV are untouched (shown on the real database for an ingest failure).
- Files already loaded earlier in the same run stay in Bronze with status `LOADED` (not `PROCESSED`), so the next run loads them again. Bronze may then hold extra copies of those rows. Silver does not.
- The `FAILED` row stays in `run_audit` as history.

## 4. Recovery

1. Detect: the run printed `FAILED`, or query A shows it.
2. Stop downstream: automatic. Publish never ran, so the previous Gold is still the published result.
3. Diagnose: read the reason and find the file named in it.
4. Fix the isolated source: replace that file in `data\capstone\landing` with a corrected one (keep a copy of the original elsewhere). Do not delete the database, the Gold CSV or any other output.
5. Rerun safely: `python -m src.capstone.pipeline`. Files already processed are skipped.
6. Verify totals: run `SUCCESS`, files reconcile (query B), Gold total equals Silver total (query C).
7. Document the incident: note the run ID, the cause, the fix and the verification.

Demonstrated: `BR003_20260910_TRANSACTION.csv` with a wrong header failed at ingest; replacing it with the corrected file and rerunning gave `SUCCESS` and Gold went from 14 to 15 rows (evidence: `evidence\capstone\s5_failed_run_protection.png`, `s5_recovery_after_fix_part1.png`, `s5_recovery_after_fix_part2.png`).

## 5. Read-only checks

Do not open the `.db` file in the VS Code text editor (it is binary). Query it with this pattern, replacing the text in quotes with one query below:

```powershell
@'
import sqlite3
c = sqlite3.connect("file:output/capstone/banking_capstone.db?mode=ro", uri=True)
for row in c.execute("PASTE ONE QUERY HERE"):
    print(row)
c.close()
'@ | python -
```

A. Latest runs and their reasons:

```sql
SELECT run_id, status, status_reason FROM run_audit ORDER BY rowid DESC LIMIT 5
```

B. File reconciliation (skipped files show zeros):

```sql
SELECT source_filename, file_status, source_rows, accepted_rows, rejected_rows FROM file_audit ORDER BY rowid DESC LIMIT 20
```

C. Gold total against Silver total (the two numbers must be equal):

```sql
SELECT (SELECT ROUND(SUM(total_amount), 2) FROM gold_branch_daily_summary), (SELECT ROUND(SUM(amount), 2) FROM silver_transactions)
```

D. Latest rejected rows with their reasons:

```sql
SELECT source_filename, source_row_number, transaction_id, rejection_reasons FROM exceptions ORDER BY exception_id DESC LIMIT 20
```

E. Accepted rows whose row date differs from the filename date (the pipeline does not count these):

```sql
SELECT s.transaction_id, s.transaction_date, f.file_date, s.source_filename FROM silver_transactions s JOIN file_audit f ON f.run_id = s.run_id AND f.source_filename = s.source_filename WHERE s.transaction_date != f.file_date
```

## 6. Do not

- Do not delete `banking_capstone.db` or the Gold CSV to fix a run. Fix the source file and rerun.
- Do not expect an edited copy of an already accepted transaction to change Silver or Gold. It is rejected as a duplicate by design.
- Do not rerun after a reconciliation or PySpark/SQL mismatch error without finding the cause first.
