# Week 8 integrated banking capstone

A local pipeline that takes branch transaction CSV files through Landing, Bronze, Silver and Gold, with rejected rows kept in Exceptions and every run recorded in audit tables. Steps: discover, ingest, validate, transform, publish, run in order by a plain Python runner.

Documents: [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) (policies and why) | [RUNBOOK.md](RUNBOOK.md) (run, rerun, failure, recovery, queries) | [TEST_RESULTS.md](TEST_RESULTS.md) (scenario, expected, actual, result, evidence) | [architecture.svg](architecture.svg) (data-flow diagram)

## Setup

- Environment used: Windows, VS Code, PowerShell, Python 3.11.3 in `.venv`, pandas 3.0.6, PySpark 4.2.0, pytest 9.1.1, Java 17. There is no Hadoop or winutils on this machine.
- Packages come from `requirements.txt` in the repository root. The fresh-location test below reused the existing `.venv`, so installing from `requirements.txt` was not part of that test.
- Spark runs print a winutils warning, a pandas FutureWarning and `SUCCESS: The process with PID ... has been terminated` lines. They appeared in every Spark run and are not errors.

## Commands

Run from the repository root:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
python -m src.capstone.pipeline
python -m pytest tests\capstone -q
```

- `python -m src.capstone.pipeline` processes the files in `data\capstone\landing`, prints the run summary, and exits with code 0 on success and 1 on failure.
- `python -m pytest tests\capstone -q` runs the 66 capstone tests (58.08 s in the measured run). They use temporary folders and databases only.
- If `output\capstone` does not exist (for example in a copy of the repository made without the output folder), the first run creates `output\capstone\banking_capstone.db` and `output\capstone\gold_branch_daily_summary.csv`.
- Normal run, rerun, failure diagnosis, recovery and read-only queries are in RUNBOOK.md.

## Input contract

- Files in `data\capstone\landing`, named `BR<digits>_<YYYYMMDD>_TRANSACTION.csv`. Anything else is listed as unrecognized with a reason and is not loaded. Nothing is moved or deleted in the landing folder.
- Header exactly: `transaction_id,account_id,transaction_date,transaction_type,amount,currency`.
- Branch ID and file date come from the filename. The row date is the business date; the filename date is lineage only (DESIGN_DECISIONS.md section 1).
- Allowed values: type `CREDIT` or `DEBIT`; currency `USD`; date exactly `YYYY-MM-DD` and a real date; amount a plain number greater than 0; `transaction_id` and `account_id` required.
- Account reference: `data\reference\accounts.csv` (the existing accounts table from earlier assignments, 10 accounts). Account status is not checked.
- Inputs: the three original files `data\raw\BR00X_20260906_TRANSACTION.csv` (copied into landing) plus synthetic files for other dates and for the failure scenarios (`data\capstone\landing` and `data\capstone\scenario_inputs`). No real customer data.

## What is where

| Path | Content |
|---|---|
| `src\capstone\discover.py` | lists recognized and unrecognized files, reads branch ID and file date, computes SHA-256 |
| `src\capstone\ingest.py` | loads rows into Bronze as received, skips an identical file that was already processed |
| `src\capstone\validate.py` | Bronze to Silver and Exceptions, duplicate policy, reconciliation |
| `src\capstone\transform.py` | builds Gold with SQL and with PySpark and compares them |
| `src\capstone\publish.py` | replaces the Gold table and the Gold CSV |
| `src\capstone\pipeline.py` | the runner, records SUCCESS or FAILED with a reason |
| `src\capstone\db.py` | database connection and run status helpers |
| `sql\capstone\schema.sql` | table definitions (Bronze, Silver, Exceptions, Gold, run and file audit) |
| `tests\capstone\` | pytest suite (66 tests) |
| `docs\capstone\` | the documents listed above |
| `evidence\capstone\` | screenshots cited in TEST_RESULTS.md |

Earlier-week files were not changed. The capstone imports the single-value checks from `src\ingestion\validate.py`, the constants from `src\ingestion\config.py` and the Spark helpers from `src\spark\load_data.py`.

## Results

- Six scenarios were run on the real capstone database in this order: stage A (6 files: the three original files and the three synthetic 2026-09-07 files), the same inputs again, the two synthetic stage C files (duplicate, correction, late row), a malformed file, then its corrected version. All six passed; details and evidence paths are in TEST_RESULTS.md.
- End state of that database: Silver 23 rows, Exceptions 16 rows, Gold 15 rows with total 5436.0 (equal to the Silver total).
- Fresh-location test: a copy of the repository with no `output` folder was run once with all 9 files in landing. Result: `files loaded=9, accepted=23, rejected=16; gold_rows=15`. Silver, Exceptions, Gold and the Gold CSV were identical to the real database (CSV byte-identical). Evidence: `evidence\capstone\fresh_start_pipeline_run_part1.png`, `evidence\capstone\fresh_start_pipeline_run_part2.png`, `evidence\capstone\fresh_start_comparison.png`.
- Not tested: a fresh clone from GitHub (the capstone files were not committed at the time of the test), and installing packages from `requirements.txt`.

## Assumptions

- All times are stored in UTC (run IDs and timestamps).
- Duplicate policy: first accepted `transaction_id` wins, in file-date, branch-ID, filename, row-number order. A correction to an accepted transaction is kept in Exceptions and changes nothing (DESIGN_DECISIONS.md sections 2 and 3).
- A skipped identical file shows 0 source rows. A duplicate counts as a rejected row.
- The pipeline is run by one person at a time. Concurrent runs were not considered or tested.

## Technology choices

- SQLite for Bronze, Silver, Exceptions, Gold and the audit tables, in `output\capstone\banking_capstone.db`.
- PySpark for the Gold aggregation, with the same aggregation in SQL for comparison (DESIGN_DECISIONS.md section 6). Spark reads Silver through the Week 7 helper `load_table`.
- A plain Python runner for the execution sequence, chosen so failure and rerun scenarios could be run and tested in seconds. A Dagster job was not built for the capstone; the Week 7 Dagster job is separate and unchanged.
- Python `csv` for reading source files (values stay exactly as received), `hashlib` for SHA-256, pytest for tests.

## Known limitations

- On the real database only a failure at the ingest step was demonstrated. A reconciliation mismatch and a PySpark/SQL mismatch are tested only in pytest (the latter with a stand-in function).
- No upsert: a correction to an already accepted transaction is rejected as a duplicate by design.
- The pipeline does not count rows whose row date differs from the filename date. RUNBOOK.md section 5 query E lists them.
- The Gold table and the Gold CSV are two files and are not replaced as one unit.
- Ingest commits one file at a time. After a failed run, files loaded earlier in that run stay in Bronze and are loaded again on the next run, so Bronze can hold extra copies of source rows. Silver does not.
- Account status is not checked, only whether the account exists.
- Spark steps took between about 14 and 47 seconds per run on this machine. The cause of the variation and of the earlier Week 7 slowness is undetermined.
- If Silver is empty, Spark is skipped as a precaution. The helper `load_table` was not tested on an empty table.
- The scenario runs depend on the order in which they were run, and each was run once.
