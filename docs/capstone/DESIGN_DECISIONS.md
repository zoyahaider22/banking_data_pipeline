# Design decisions - Week 8 integrated banking capstone

Input files other than the three original branch files (`data\raw\BR00X_20260906_TRANSACTION.csv`) are synthetic and labeled as such (`data\capstone\landing` and `data\capstone\scenario_inputs`). No real customer data is used.

## 1. Branch ID, file date and row date

- Branch ID and file date are read from the filename with the pattern `BR<digits>_<YYYYMMDD>_TRANSACTION.csv` (`src\capstone\discover.py`). A name that does not match, or whose date is not a real calendar date, is listed as unrecognized with a reason and is not loaded.
- The row date (`transaction_date`) is the business date. Gold is grouped by the row date. The filename date is lineage only (when the file was delivered).
- A disagreement between the two dates is not a rejection reason. Example: `T7104` arrives in `BR002_20260909_TRANSACTION.csv` with row date 2026-09-07, is accepted, and is counted under 2026-09-07.
- The pipeline does not count these disagreements in the run summary. They can be listed with the SQL query in RUNBOOK.md.

## 2. Duplicate policy: first accepted record wins

- Business key: `transaction_id`.
- A row is a duplicate when its `transaction_id` was already accepted, either in an earlier run (already in Silver) or earlier in the same run. Rows are processed in this order: file date, branch ID, filename, source row number. The earliest delivery wins.
- A duplicate is rejected to Exceptions with the reason "duplicate transaction_id already accepted (first accepted record wins)", together with its source filename, source row number and Bronze ID. This is the audit trail.
- A repeated ID that was never accepted is not a duplicate. Example: `T1005` appears in two files with an unknown account; both rows are rejected for the unknown account only.
- Silver has `transaction_id` as its primary key, so the database also refuses a second accepted copy. This is a safety net behind the check in the code.
- A duplicate counts as a rejected row in the reconciliation.

## 3. Correction policy (late or corrected file)

- A re-delivery of an accepted ID with a different amount is treated as a duplicate. The earlier accepted record stays, Silver and Gold are intentionally unchanged, and the correction is kept in Exceptions. Example: `T1001` is 500.00 in `BR001_20260906_TRANSACTION.csv`; the 550.00 row in `BR001_20260908_TRANSACTION.csv` is rejected as a duplicate.
- Consequence: the pipeline cannot apply a correction to a transaction that was already accepted. An upsert (update Silver when the same `transaction_id` arrives with new values) is not implemented.
- A late file (an older business date arriving later) is accepted normally and lands in its row date.
- Follows from the rules (not demonstrated on the real database): a corrected row for an ID that was only ever rejected would be accepted, because that ID was never accepted before.

## 4. Idempotency strategy

1. File level: each file gets a SHA-256 hash. If an earlier file with the same hash reached `PROCESSED`, the file is skipped and recorded as `SKIPPED_IDENTICAL` with a note pointing to the earlier run. A skipped file shows 0 source rows.
2. Row level: the duplicate rule above.
3. Gold: rebuilt from all of Silver on every run and replaced in one transaction.

- Same inputs twice: Silver, Exceptions, Gold and the Gold CSV stay unchanged. Run IDs, `run_audit` and `file_audit` rows and the Gold `published_run_id` differ on every run. The business result is identical.
- A file with the same name but different content has a different hash and is processed.
- A file loaded in a run that failed never reached `PROCESSED`, so it is loaded again on the next run. Bronze keeps a copy from each run, so Bronze can hold more rows than distinct source rows after a failed run. Silver does not.

## 5. Failure handling and publish protection

- `src\capstone\pipeline.py` runs discover, ingest, validate, transform, publish in that order. An error stops the run before the later steps, and the run is recorded as FAILED with the failing step and the error.
- A rejected row is not a failure. Structural problems are failures: wrong header or field count, empty file, reconciliation mismatch, PySpark and SQL results that differ, missing landing folder.
- Publish writes the Gold CSV to a temporary file and replaces the old CSV at the end. The Gold table is replaced (delete and insert) in one transaction.
- Limitation: the database and the CSV are two files and are not replaced as one unit.
- Ingest commits one file at a time, so an earlier good file stays loaded if a later file is bad.
- Demonstrated on the real database: a failure at ingest (wrong header) with the previous Gold left unchanged, then recovery by fixing the file and rerunning. A reconciliation mismatch and a PySpark/SQL mismatch are tested only in pytest (the latter with a stand-in function), not on the real database.

## 6. SQL vs PySpark (Gold)

Gold has one row per `branch_id`, `transaction_date`, `transaction_type`, with the count and the sum of the amount, built from Silver only.

SQL:

```sql
SELECT branch_id, transaction_date, transaction_type,
       COUNT(*) AS transaction_count,
       ROUND(SUM(amount), 2) AS total_amount
FROM silver_transactions
GROUP BY branch_id, transaction_date, transaction_type
```

PySpark equivalent: `silver.groupBy("branch_id", "transaction_date", "transaction_type").agg(F.count("*"), F.round(F.sum("amount"), 2))`.

- Both are computed on every run and compared after rounding to 2 decimals. If they differ, the step raises an error and nothing is published.
- Spark reads Silver through the Week 7 helper `load_table`, which loads the SQLite rows into memory and builds a DataFrame. At this data size Spark gives no speed benefit. Spark steps took between 14 and 47 seconds per run on this machine; the cause is undetermined.
- If Silver is empty, Spark is skipped as a precaution, because the helper builds the DataFrame from fetched rows and was not tested on an empty table.

## 7. Rules and allowed values

- Required values: `transaction_id`, `account_id`. Types: `CREDIT`, `DEBIT`. Currency: `USD`. Date: exactly `YYYY-MM-DD` and a real calendar date. Amount: a plain number greater than 0.
- Unknown account means not found in `data\reference\accounts.csv` (the existing accounts reference from earlier assignments, 10 accounts). Account status is not checked.
- The single-value checks from Week 3 (`src\ingestion\validate.py`) are reused by import and were not changed. All rejection reasons for a row are kept.
- Reconciliation per file: source rows = accepted rows + rejected rows. It is checked in the code, and a mismatch raises an error.
