# Banking Data Pipeline

An end-to-end banking data project, consolidated in Week 5 into one repository. Raw branch transaction files are validated, trusted data is loaded into a relational SQLite database, daily corrections are applied incrementally, and a separate star-schema database is built for analysis.

## Architecture and Data Flow

```text
data/raw  (branch CSV files, untrusted source)
   |
   v
src/ingestion  (extract, validate, DQ, logging)
   |--> data/validated        valid_transactions.csv, invalid_transactions.csv
   '--> output/dq, output/logs   DQsummary.csv, pipeline.log

data/validated + data/reference
   |
   v
src/operational/build_database.py   (initial relational load)
   |
   v
database/banking.db  <--- data/daily via src/operational/incremental_load.py (UPSERT)
   |
   v
src/analytics/build_analytics.py
   |
   v
database/analytics.db   (star schema)
   |
   v
sql/analytical_queries.sql
```

Diagrams: `docs/erd/ERD.md` (relational ERD), `docs/analytics/star_schema.md` (star schema), `docs/analytics/data_lineage.md` (end-to-end lineage).

| Stage | Code | Reads | Produces |
|---|---|---|---|
| 1. Ingestion and validation | `src/ingestion/` | `data/raw/` | `data/validated/`, `output/dq/`, `output/logs/` |
| 2. Initial relational load | `src/operational/build_database.py` | `data/validated/`, `data/reference/` | `database/banking.db` |
| 3. Incremental daily load | `src/operational/incremental_load.py` | `data/daily/` | updated `database/banking.db` |
| 4. Analytical build | `src/analytics/build_analytics.py` | `database/banking.db` only | `database/analytics.db` |
| 5. Analysis | `sql/analytical_queries.sql` | `database/analytics.db` | query results |

## Setup

Requirements: Python 3.11. Dependencies are listed in `requirements.txt` (`pandas`, `pytest`). `sqlite3` is part of the Python standard library.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

All commands in this README are run from the repository root, using `python -m` (for example `python -m pytest`). Running bare `pytest` fails with `No module named 'src'`.

## Repository Structure

```text
.
|-- README.md
|-- requirements.txt
|-- data/
|   |-- raw/          branch transaction files (BR001, BR002, BR003)
|   |-- reference/    customers.csv, accounts.csv, branches.csv
|   |-- validated/    valid_transactions.csv, invalid_transactions.csv
|   `-- daily/        transactions_20260907.csv, _20260908.csv, _20260909.csv
|-- src/
|   |-- ingestion/    config, extract, validate, pipeline, run_test_scenario
|   |-- operational/  schema, database, loader, build_database, incremental_load, analysis, evidence scripts
|   `-- analytics/    build_analytics.py
|-- output/
|   |-- dq/           DQsummary.csv
|   `-- logs/         pipeline.log
|-- database/         banking.db, analytics.db
|-- sql/              operational_queries.sql, analytical_queries.sql
|-- tests/
|   |-- fixtures/     test_scenarios/ (T01-T10), daily_day1.csv, daily_day2.csv
|   `-- test_*.py     validation, pipeline, database integrity, incremental load, analytics
|-- evidence/
|   |-- earlier_pipeline/   earlier pipeline test results, DQ summary, log
|   |-- class_4/            integrity failures, SQL results, query plans
|   `-- week_5/             incremental, correction, rerun, table counts, query results, pytest
`-- docs/
    |-- erd/          relational ERD
    `-- analytics/    star-schema and data-lineage diagrams
```

## Folder Responsibilities

| Folder | Responsibility |
|---|---|
| `data/raw` | Original supplied branch files. Untrusted source data, kept unchanged. |
| `data/reference` | Supplied customer, account and branch master data. |
| `data/validated` | Business-data output of the validation stage: valid and rejected transactions. |
| `data/daily` | Supplied Week 5 daily files (new transactions and corrections). Not edited. |
| `src` | All code that does the work, one folder per stage. |
| `output` | Artifacts generated each time the pipeline runs (DQ summary, log). |
| `database` | The two persisted SQLite layers. `banking.db` is the trusted relational state, `analytics.db` is derived from it. |
| `sql` | Operational and analytical SQL. |
| `tests` | Automated pytest tests. `tests/fixtures` holds deliberately constructed test input, kept apart from real data. |
| `evidence` | Proof deliberately captured to show requirements work (different from `output`, which is generated on every run). |
| `docs` | Design diagrams. |

There is no `config/` folder: configuration lives in `src/ingestion/config.py` and `src/operational/config.py`, as it did in the earlier projects.

## Run Order

Run these from the repository root, in this order.

| # | Command | Expected result |
|---|---|---|
| 1 | `python -m src.ingestion.pipeline` | 24 records read, 10 valid, 14 invalid. Writes `data/validated/`, `output/dq/DQsummary.csv` and `output/logs/pipeline.log`. |
| 2 | `python -m src.operational.build_database` | Deletes and rebuilds `database/banking.db`: 6 customers, 3 branches, 10 accounts, 10 transactions. |
| 3 | `python -m src.operational.incremental_load` | Processes `data/daily/transactions_*.csv` in date order. First run: 0907 inserted 4, 0908 inserted 3 and updated 1, 0909 inserted 3 and updated 1. Total 20 transactions. |
| 4 | `python -m src.operational.incremental_load` (again) | Rerun: nothing inserted or updated (unchanged 3, 4 and 4), the 0907 file reports `skipped_stale=1`. Total stays 20. |
| 5 | `python -m src.analytics.build_analytics` | Deletes and rebuilds `database/analytics.db`: 6 customers, 10 accounts, 3 branches, 4 dates, 20 fact rows. |
| 6 | `sql/analytical_queries.sql` | Seven queries against `analytics.db` (see Analytical SQL below). |
| 7 | `python -m pytest -v` | 41 passed. |

Step 2 rebuilds `banking.db` from scratch, so after it runs, the daily files must be loaded again (step 3). Edge-case scenarios from the earlier pipeline can be run with `python -m src.ingestion.run_test_scenario T01_new_branch` (T01 to T10). Each writes only to its own folder under `tests/fixtures/test_scenarios/`.

## From Raw Files to Validated Data

`src/ingestion` reads every file in `data/raw` matching `BR*_*_TRANSACTION.csv`. Files must contain the six required columns: `transaction_id`, `account_id`, `transaction_date`, `transaction_type`, `amount`, `currency`. Rules applied:

- `transaction_id` and `account_id` must be present.
- `transaction_date` must be a real calendar date in `YYYY-MM-DD` format.
- `transaction_type` must be `CREDIT` or `DEBIT`.
- `amount` must be a plain decimal number greater than zero.
- `currency` must be `USD`.
- `transaction_id` must be unique across all branch files. Every occurrence of a duplicated ID is invalid.

A file with a missing column is skipped and recorded as a file-level error, so the other files can still be processed. Row-level failures go to `data/validated/invalid_transactions.csv` with an `error_reason` column (several reasons for one row are separated by `; `). Valid rows go to `data/validated/valid_transactions.csv`.

Generated artifacts: `output/dq/DQsummary.csv` (files discovered, read and rejected, record counts, rejection rate, duplicates, failures by rule) and `output/logs/pipeline.log` (start and end, files processed, warnings and errors). The earlier pipeline has no separate run-summary file: the run summary is `DQsummary.csv`.

## Initial Relational Load

`build_database.py` creates `banking.db` with four tables (`customer`, `branch`, `account`, `bank_transaction`), enabling foreign keys. It loads customers, branches and accounts from `data/reference` and the 10 valid transactions from `data/validated`. Constraints enforced by SQLite: primary keys, foreign keys, `NOT NULL`, `CHECK (amount > 0)`, `CHECK` on transaction type (`CREDIT` or `DEBIT`) and currency (`USD`). The ERD is in `docs/erd/ERD.md`.

## Incremental Daily Load

`src/operational/incremental_load.py` applies one daily file at a time to the existing `banking.db`, without rebuilding it. For each row it:

1. normalizes the date (`YYYY-MM-DD` and `MM/DD/YYYY` are accepted) and the amount;
2. validates the row, and counts it as `rejected` if it fails;
3. sets `source_file` from the file name;
4. writes it with an UPSERT: `ON CONFLICT(transaction_id) DO UPDATE ... WHERE excluded.source_file >= bank_transaction.source_file`.

Each file reports `inserted`, `updated`, `unchanged`, `skipped_stale` and `rejected` counts.

**New transactions:** a `transaction_id` that does not exist yet is inserted.

**Corrections:** a later trusted row with an existing `transaction_id` is treated as a correction, and the stored row is updated. For example, T1001 changes from 500.0 to 550.0 (from `transactions_20260908.csv`), and T4002 ends at 55.0 (from `transactions_20260909.csv`). `INSERT OR IGNORE` would have kept the old values.

**Rerun safety:** running the same files again is safe for three reasons. `transaction_id` is the primary key, so a duplicate row cannot exist. Writing is an UPSERT, not a plain insert, so a repeated row updates in place. And the `source_file` guard stops an older file from overwriting a newer correction: re-running `transactions_20260907.csv` after the 0909 file is reported as `skipped_stale`, and T4002 keeps 55.0. Files are named with their date, so the order in which `sorted()` processes them is date order.

## Analytical Layer

`src/analytics/build_analytics.py` reads only `banking.db` (never the raw branch files) and builds `database/analytics.db` as a star schema. The file is deleted and rebuilt on every run, so the result is repeatable.

**Grain: one row in `fact_transaction` represents one banking transaction.** `transaction_id` is its primary key.

| Table | Role | Columns |
|---|---|---|
| `fact_transaction` | fact | `transaction_id` (PK), `account_id`, `customer_id`, `branch_id`, `date_key`, `transaction_type`, `amount`, `currency` |
| `dim_customer` | dimension | `customer_id` (PK), `customer_name`, `email`, `customer_segment` |
| `dim_account` | dimension | `account_id` (PK), `account_type`, `account_status` |
| `dim_branch` | dimension | `branch_id` (PK), `branch_name`, `city`, `state` |
| `dim_date` | dimension | `date_key` (PK, `YYYYMMDD`), `full_date`, `year`, `month`, `day`, `day_name` |

The dimensions use natural keys (no surrogate keys or history tracking, which are out of scope this week). `customer_id` and `branch_id` are carried on the fact row by joining each transaction to its account. Foreign keys are enforced in `analytics.db`. Diagram: `docs/analytics/star_schema.md`. Lineage: `docs/analytics/data_lineage.md`.

**About `amount`:** it is always positive, and `transaction_type` says whether money came in or went out. So `SUM(amount)` is gross volume, not a balance. Net cash flow is `SUM(CASE WHEN transaction_type = 'CREDIT' THEN amount ELSE -amount END)`.

## SQL

- **Operational:** `sql/operational_queries.sql` holds the relational queries against `banking.db`, run with `python -m src.operational.analysis`.
- **Analytical:** `sql/analytical_queries.sql` holds seven queries against `analytics.db`: by branch, by transaction type, by customer, by account, by date, segment by branch (a fact joined to two dimensions), and our own question (accounts with net outflow). Run them with any SQLite client against `database/analytics.db`. The returned results and interpretations are saved in `evidence/week_5/analytical_query_results.txt`.

## Tests

```powershell
python -m pytest -v
```

41 tests, all passing (`evidence/week_5/pytest_output.txt`):

| File | Tests | Covers |
|---|---|---|
| `test_validation.py` | 15 | each field rule in isolation |
| `test_pipeline.py` | 8 | extract plus validate, bad files, DQ summary and log, duplicates, the 24 / 10 / 14 baseline |
| `test_database_integrity.py` | 8 | constraints, foreign keys, table list, row counts |
| `test_incremental_load.py` | 4 | new rows inserted, correction updates the value, rerun keeps the count, older file cannot reverse a correction |
| `test_analytics.py` | 6 | fact count matches banking, no duplicate IDs, valid dimension keys, customer and branch from account, known net cash flow result, repeatable rebuild |

Always use `python -m pytest`, not bare `pytest`.

## Fixtures and Evidence

- `tests/fixtures/` holds deliberately constructed input: the T01 to T10 scenario inputs and the two daily test files. Generated `output/` folders inside the scenarios are ignored by git.
- `evidence/earlier_pipeline/`: pytest run for the earlier pipeline tests, DQ summary, pipeline log, Week 2 test results workbook.
- `evidence/class_4/`: integrity failures, SQL analysis results, query plans.
- `evidence/week_5/`: `incremental_load_evidence.txt` (first load, new rows), `correction_evidence.txt` (T1001 before and after), `rerun_evidence.txt` (stable counts, corrections kept), `table_counts.txt`, `analytical_query_results.txt`, `pytest_output.txt`.

## Assumptions

- The three supplied daily files are already valid, trusted input. Their values are not changed.
- A later row with an existing `transaction_id` is a correction, so the stored row is updated to the later values.
- "Later" is decided by the file name: files are named `transactions_YYYYMMDD.csv`, so sorting the names sorts them by date.
- Dates are stored as text in `YYYY-MM-DD` format. The daily loader also accepts `MM/DD/YYYY` and converts it.
- All transactions are in USD. `amount` is always positive, and `transaction_type` (`CREDIT` or `DEBIT`) gives the direction.
- Customer, account, branch and transaction IDs are stable business keys, so the star schema uses them directly (no surrogate keys).
- `banking.db` is the trusted relational state. `analytics.db` is derived from it and can always be rebuilt.
- The earlier pipeline's only run-summary output is `output/dq/DQsummary.csv`, so there is no separate summary folder.

## Known Limitations

- **Corrections are ordered by file name, not by event time.** If a file were renamed so its date no longer matches its contents, the stale-file guard would compare the wrong order.
- **Only the latest value is kept.** When a correction updates a row, the old value is overwritten, so `banking.db` has no history of changes. History tracking (SCD Type 2) was out of scope this week. The old and new values are shown in `evidence/week_5/correction_evidence.txt`.
- **`analytics.db` is rebuilt completely each time.** That keeps it simple and repeatable, but it would not suit very large data.
- **`SUM(amount)` is not a balance.** The data has no opening balances, so net cash flow only covers the loaded transactions.
- **The stages are run by hand, in the order shown in Run Order.** There is no one-command orchestrator, which this week did not require.
- **Small, local data.** The pipeline reads local CSV files with pandas and uses SQLite, which is fine for this dataset but not for production banking workloads. A production system would also need security, backups and monitoring.
- **Rebuilding `banking.db` resets it to the 10 initial rows.** The daily files must be loaded again after `build_database`.

## Concept Questions

### 1. What is the grain of `fact_transaction`, and why must it be defined before building the table?

The grain is one row for one banking transaction. Every row in `fact_transaction` is exactly one transaction, and `transaction_id` is the primary key.

It has to be decided first because the grain controls everything else in the table: which columns belong in it, which dimensions it can join to, and what a count or a sum actually means. If the grain were unclear, a table could mix rows of different kinds (a transaction in one row, a daily total in another), and then counts and totals would give wrong answers. With the grain fixed, `COUNT(*)` is the number of transactions, and a duplicate transaction is simply not allowed.

### 2. What is the difference between a full load and the incremental approach you implemented?

A full load deletes everything and rebuilds the whole database from the source files. That is what `build_database` and `build_analytics` do. It is simple, but it throws away changes made since and has to reprocess all the data.

The incremental load keeps the existing `banking.db` and applies only the new daily file. New transaction IDs are inserted, and IDs that already exist are updated with the corrected values. Rows that did not change are left alone. Each run reports how many rows were inserted, updated, unchanged, stale or rejected, so it is clear exactly what changed.

### 3. Why is `INSERT OR IGNORE` not sufficient for the correction scenario in this assignment?

`INSERT OR IGNORE` skips a row when its `transaction_id` already exists. In this assignment a later row with an existing ID is a correction, so the stored value must change. With `INSERT OR IGNORE` the correction would be silently thrown away and the old, wrong value would stay. For example, T1001 would remain 500.0 instead of becoming 550.0. An UPSERT (`ON CONFLICT ... DO UPDATE`) inserts new IDs and updates existing ones, which is the behavior needed here.

### 4. What specifically makes your implementation safe to rerun?

Three things work together:
- **`transaction_id` is the primary key**, so the database cannot hold two rows with the same ID. A rerun can never create duplicate business transactions.
- **The write is an UPSERT**, so a row that already exists is updated in place instead of inserted again. Rerunning a file leaves the same data (the rerun evidence shows 0 inserted, 0 updated and still 20 rows).
- **The stale-file guard** only allows an update when the incoming file is the same as or newer than the file that wrote the stored row (`WHERE excluded.source_file >= bank_transaction.source_file`). So rerunning an older file cannot reverse a newer correction. In the rerun, `transactions_20260907.csv` reports `skipped_stale=1` and T4002 keeps its corrected value of 55.0.

### 5. In your model, what is a fact and what is a dimension?

A fact is a measurable event. In my model it is `fact_transaction`: each row is one banking transaction, with its `amount` as the measure and keys that point to the dimensions. Facts are what we count and sum.

A dimension describes the context of the event: who, which account, where and when. In my model these are `dim_customer`, `dim_account`, `dim_branch` and `dim_date`. They hold descriptive columns such as customer name, account type, branch city or day name, and we use them to group and filter the facts (for example, total amount by branch).

## Author

Zoya Haider
