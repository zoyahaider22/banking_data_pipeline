# Banking Data Pipeline

An end-to-end banking data engineering project covering transaction ingestion, validation, relational data modelling, incremental loading, analytics, PySpark processing and Dagster orchestration (Weeks 2-7). Week 8 adds an Integrated Banking Capstone with Landing, Bronze, Silver, Gold, Exceptions and audit tables. The Week 8 CDP Readiness Extension builds on that capstone by creating a customer-level Customer 360 data product and exposing approved customer summaries through a read-only HTTP API using Python and SQLite.

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
   |---------------------------------------------.
   v                                             v
src/analytics/build_analytics.py          src/spark/  (Week 6, read-only access to banking.db)
   |                                             |  sqlite3 -> spark.createDataFrame
   v                                             v
database/analytics.db   (star schema)     Spark DataFrames: transactions, accounts, customers, branches
   |                                             |-- transformations, aggregations, joins
   v                                             |-- data quality checks, Spark SQL comparison
sql/analytical_queries.sql                       '-- results printed and saved in evidence/week6/

src/spark/generate_transactions.py -> data/generated/synthetic_transactions.csv (git-ignored)
   |
   v
src/spark/large_data_analysis.py   (100,000 synthetic transactions)

database/banking.db  (read-only)
   |
   v
orchestration/banking_job.py   (Week 7 Dagster job, reuses src/spark)
   extract -> validate -> transform -> publish
   a failed validation stops the job: transform and publish never run
   publish writes output/reports/branch_summary.csv
```
This overview summarizes the Weeks 2–7 pipeline.
The Week 8 Integrated Banking Capstone and CDP
Readiness Extension architectures are documented
in their respective sections below.

Diagrams: `docs/erd/ERD.md` (relational ERD), `docs/analytics/star_schema.md` (star schema), `docs/analytics/data_lineage.md` (end-to-end lineage).

| Stage | Code | Reads | Produces |
|---|---|---|---|
| 1. Ingestion and validation | `src/ingestion/` | `data/raw/` | `data/validated/`, `output/dq/`, `output/logs/` |
| 2. Initial relational load | `src/operational/build_database.py` | `data/validated/`, `data/reference/` | `database/banking.db` |
| 3. Incremental daily load | `src/operational/incremental_load.py` | `data/daily/` | updated `database/banking.db` |
| 4. Analytical build | `src/analytics/build_analytics.py` | `database/banking.db` only | `database/analytics.db` |
| 5. Analysis | `sql/analytical_queries.sql` | `database/analytics.db` | query results |
| 6. Spark processing (Week 6) | `src/spark/` | `database/banking.db` (read-only) | printed results, `evidence/week6/` |
| 7. Orchestration (Week 7) | `orchestration/banking_job.py` | `database/banking.db` (read-only) | `output/reports/branch_summary.csv`, Dagster run history under `DAGSTER_HOME`, `evidence/week7/` |

## Setup

Requirements: Python 3.11, Java 17 (needed by Spark), and the packages in `requirements.txt` (`pandas`, `pytest`, `pyspark`, `dagster`, `dagster-webserver`). `sqlite3` is part of the Python standard library.

Versions used for this project: Python 3.11.3, Java OpenJDK 17.0.20.1 (Eclipse Temurin), PySpark 4.2.0 (runs Spark 4.2.0). They are recorded by `src/spark/check_environment.py` (`evidence/week6/part1_environment.txt`).

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
java -version
```

`java -version` must report version 17. On Windows, Java 17 was installed from the Eclipse Temurin MSI installer with the "Add to PATH" and "Set JAVA_HOME" options, and VS Code was restarted so the terminal sees the new PATH. No Hadoop or winutils was installed (see Known Limitations).

All commands are run from the repository root.
Python modules and pytest commands use `python -m`
where specified. Standalone Spark setup scripts are
shown with direct Python script execution.

## Repository Structure

```text
.
|-- README.md
|-- requirements.txt
|-- data/
|   |-- raw/          branch transaction files (BR001, BR002, BR003)
|   |-- reference/    customers.csv, accounts.csv, branches.csv
|   |-- validated/    valid_transactions.csv, invalid_transactions.csv
|   |-- daily/        transactions_20260907.csv, _20260908.csv, _20260909.csv
|   `-- generated/    synthetic_transactions.csv (Week 6, created by the generator, git-ignored)
|-- orchestration/    banking_job.py (Week 7 Dagster job)
|-- src/
|   |-- ingestion/    config, extract, validate, pipeline, run_test_scenario
|   |-- operational/  schema, database, loader, build_database, incremental_load, analysis, evidence scripts
|   |-- analytics/    build_analytics.py
|   `-- spark/        Week 6 PySpark code (see "Week 6: PySpark Processing"), plus reporting.py (Week 7)
|-- output/
|   |-- dq/           DQsummary.csv
|   `-- logs/         pipeline.log
|-- database/         banking.db, analytics.db
|-- sql/              operational_queries.sql, analytical_queries.sql
|-- tests/
|   |-- fixtures/     test_scenarios/ (T01-T10), daily_day1.csv, daily_day2.csv
|   |-- orchestration/  Week 7 tests (test_reporting_logic.py, test_banking_job.py)
|   |-- spark/        Week 6 pytest tests (conftest.py, test_load_and_transform.py, test_quality_and_joins.py)
|   `-- test_*.py     validation, pipeline, database integrity, incremental load, analytics
|-- evidence/
|   |-- earlier_pipeline/   earlier pipeline test results, DQ summary, log
|   |-- class_4/            integrity failures, SQL results, query plans
|   |-- week_5/             incremental, correction, rerun, table counts, query results, pytest
|   |-- week6/              Spark output evidence, parts 1-11
|   `-- week7/              Dagster scenario A-E screenshots (22 PNGs)
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
| `data/generated` | Week 6 synthetic data created by `generate_transactions.py`. Not committed: the generator is committed instead. |
| `src` | All code that does the work, one folder per stage. `src/spark` holds the Week 6 PySpark code. |
| `orchestration` | The Week 7 Dagster job (`banking_job.py`). Its ops are thin wrappers over the code in `src/spark`. |
| `output` | Artifacts generated each time the pipeline runs (DQ summary, log). |
| `database` | The two persisted SQLite layers. `banking.db` is the trusted relational state, `analytics.db` is derived from it. |
| `sql` | Operational and analytical SQL. |
| `tests` | Automated pytest tests. `tests/fixtures` holds deliberately constructed test input, kept apart from real data. `tests/spark` holds the Week 6 Spark tests. |
| `evidence` | Proof deliberately captured to show requirements work (different from `output`, which is generated on every run). |
| `docs` | Design diagrams. |

There is no `config/` folder: configuration lives in `src/ingestion/config.py` and `src/operational/config.py`, as it did in the earlier projects.

Week 8 adds a `capstone` subfolder inside each of `data`, `src`, `sql`, `output`, `tests`, `docs` and `evidence`. It is described in the Week 8 section and is not repeated in the tree above.


### CDP Readiness Extension Structure

The Week 8 CDP Readiness Extension adds the following folders:

```text
data/
└── customer360/
    ├── customers.csv
    └── accounts.csv

sql/
└── customer360/
    └── schema.sql

src/
└── customer360/
    ├── build_customer360.py
    └── api_server.py

tests/
└── customer360/
    └── test_api_server.py

output/
└── customer360/
    ├── backups/
    ├── customer_360.csv
    └── customer360_exceptions.csv
```

Supporting documentation is maintained in the repository root:

- `TEST_RESULTS.md`
- `ARCHITECTURE.md`
- `PRIVACY_AND_DESIGN.md`


## Run Order

Run these from the repository root, in this order. This is the Week 2-5 pipeline; the Week 6 Spark scripts are listed in their own section below.

| # | Command | Expected result |
|---|---|---|
| 1 | `python -m src.ingestion.pipeline` | 24 records read, 10 valid, 14 invalid. Writes `data/validated/`, `output/dq/DQsummary.csv` and `output/logs/pipeline.log`. |
| 2 | `python -m src.operational.build_database` | Deletes and rebuilds `database/banking.db`: 6 customers, 3 branches, 10 accounts, 10 transactions. |
| 3 | `python -m src.operational.incremental_load` | Processes `data/daily/transactions_*.csv` in date order. First run: 0907 inserted 4, 0908 inserted 3 and updated 1, 0909 inserted 3 and updated 1. Total 20 transactions. |
| 4 | `python -m src.operational.incremental_load` (again) | Rerun: nothing inserted or updated (unchanged 3, 4 and 4), the 0907 file reports `skipped_stale=1`. Total stays 20. |
| 5 | `python -m src.analytics.build_analytics` | Deletes and rebuilds `database/analytics.db`: 6 customers, 10 accounts, 3 branches, 4 dates, 20 fact rows. |
| 6 | `sql/analytical_queries.sql` | Seven queries against `analytics.db` (see Analytical SQL below). |
| 7 | `python -m pytest -v` | Historical Week 7 baseline: 64 passed. See the Tests section for subsequent Week 8 results. |

Step 2 rebuilds `banking.db` from scratch, so after it runs, the daily files must be loaded again (step 3). The Week 6 Spark code expects `banking.db` to be in its final state (20 transactions, after step 3). Edge-case scenarios from the earlier pipeline can be run with `python -m src.ingestion.run_test_scenario T01_new_branch` (T01 to T10). Each writes only to its own folder under `tests/fixtures/test_scenarios/`.

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

## Week 6: PySpark Processing

Week 6 repeats the loading, transformation, aggregation, join and data-quality work with PySpark. The flow is `banking.db` -> PySpark DataFrames -> transformations, joins, data-quality checks and analysis -> printed Spark results. `analytics.db` is not used and is not rebuilt in Week 6, because it is itself a derived output of Week 5.

### Inputs and outputs

- **Input:** `database/banking.db` (6 customers, 3 branches, 10 accounts, 20 transactions after the incremental load). It is opened read-only (`mode=ro`), so the Spark code can never change it.
- **How the data gets into Spark:** Spark cannot read SQLite directly without a JDBC driver, and the setup instructions say not to install extra Spark or Hadoop software. So `load_data.py` reads each table with Python's built-in `sqlite3` and builds a Spark DataFrame with `spark.createDataFrame(rows, columns)`.
- **Second input (Part 8 only):** `data/generated/synthetic_transactions.csv`, created by `generate_transactions.py`.
- **Outputs:** the scripts print their results to the terminal. The captured outputs are in `evidence/week6/`. No Parquet files are produced on this machine (see Parquet below).

### Spark files

| File | Part | What it does |
|---|---|---|
| `src/spark/spark_test.py` | 1 | The setup test from the class instructions: starts Spark and prints its version. |
| `src/spark/check_environment.py` | 1 | Prints the Python, Java, PySpark and Spark versions and shows a small DataFrame. |
| `src/spark/load_data.py` | 2 | `get_spark()` and the loaders for transactions, accounts, customers and branches. Shows sample rows, schema and row count of each. |
| `src/spark/transformations.py` | 3 | `prepare_transactions`, `credit_transactions`, `high_value_transactions`, `reporting_columns`, `add_signed_amount`. |
| `src/spark/analytics.py` | 4 | Summaries by transaction type, account and branch. |
| `src/spark/joins.py` | 5 | Joins all four tables, then activity by customer, branch and account type. |
| `src/spark/data_quality.py` | 6 | The data-quality checks with a PASS/FAIL report (seven in Week 6, eight since Week 7). |
| `src/spark/parquet_io.py` | 7 | Parquet write and read-back attempt with row-count validation. |
| `src/spark/generate_transactions.py` | 8 | Generates 100,000 synthetic transactions (fixed seed). |
| `src/spark/large_data_analysis.py` | 8 | Loads the generated data and runs a filter, an aggregation and a join. |
| `src/spark/spark_concepts.py` | 9 | Prints partition counts, a transformation, an action and a shuffle plan from this project's code. |
| `src/spark/spark_sql_analysis.py` | 10 | The branch analysis written with the DataFrame API and with `spark.sql()`, compared. |

### How to run the Week 6 work

Run from the repository root, after the Week 2-5 pipeline has produced the final `banking.db` (Run Order steps 1-3). The first Spark command in a session takes a few seconds to start Spark. Each Spark job on the `banking.db` DataFrames takes around 11 seconds on the development machine (see Known Limitations).

| # | Command | Expected result |
|---|---|---|
| 1 | `python src/spark/spark_test.py` | Prints `Spark version: 4.2.0`. |
| 2 | `python src/spark/check_environment.py` | Python, Java, PySpark and Spark versions, and a 2-row DataFrame. |
| 3 | `python -m src.spark.load_data` | Row counts 6 (customers), 10 (accounts), 3 (branches), 20 (transactions). |
| 4 | `python -m src.spark.transformations` | 20 transactions, 11 CREDIT, 3 high-value, gross 4735.5, net 3384.5. |
| 5 | `python -m src.spark.analytics` | Summaries by type, account and branch (see below). |
| 6 | `python -m src.spark.joins` | 20 joined rows, then activity by customer, branch and account type. |
| 7 | `python -m src.spark.data_quality` | `8 of 8 checks passed` (it was `7 of 7` in Week 6, before the Week 7 non-positive amounts check). |
| 8 | `python -m src.spark.parquet_io` | On the development machine: `PARQUET WRITE FAILED` (see Parquet below). |
| 9 | `python -m src.spark.generate_transactions` | 10 accounts used, 100000 rows generated, written to `data/generated/`. |
| 10 | `python -m src.spark.large_data_analysis` | 100000 rows loaded, 4294 high-value, branch counts adding up to 100000. |
| 11 | `python -m src.spark.spark_concepts` | Partition counts 8, 2 and 1, a `count()` of 55376, and a plan with `Exchange` (shuffle) steps. |
| 12 | `python -m src.spark.spark_sql_analysis` | DataFrame and SQL tables are identical: `Rows that differ between the two versions: 0`. |
| 13 | `python -m pytest tests/spark -v` | 18 passed (takes several minutes on the development machine). |

### Part 2: types reviewed

The loaders build the DataFrames from SQLite rows, so Spark takes each column's type from the Python value. Ids and text columns load as `string` and `amount` loads as `double`, which is correct. One column needs attention: **`transaction_date` loads as `string`**, because SQLite stores dates as text (`YYYY-MM-DD`). `prepare_transactions()` converts it with `to_date(..., "yyyy-MM-dd")`, so the transformations and the schema printed by `transformations.py` show a real `date`.

### Part 3: transformations and the high-value threshold

All of these work on the 20 `banking.db` transactions:

- **CREDIT-only dataset:** `credit_transactions()` - a `filter` on `transaction_type = 'CREDIT'`. 11 rows.
- **High-value dataset:** `high_value_transactions()` - `amount >= 500.0`. 3 rows (T1001, T2001, T3001). The threshold is the constant `HIGH_VALUE_THRESHOLD` in `transformations.py`. 500.0 was chosen as a round figure that separates large transfers from everyday amounts in this data (most transactions are below 500), and it can be changed in one place.
- **Reporting columns:** `reporting_columns()` - a `select` of `transaction_id`, `account_id`, `transaction_date`, `transaction_type`, `amount`.
- **Derived column:** `add_signed_amount()` - `withColumn("signed_amount", ...)`: credits positive, debits negative. This is what makes net cash flow a simple sum.

### Part 4: aggregations

`analytics.py` uses `groupBy()` and `agg()` with `count`, `sum` and `avg`. `summary_by_type()` returns three aggregations in one result (count, total, average). The results:

| Summary | Result |
|---|---|
| By type | CREDIT: 11 rows, total 4060.0, average 369.09. DEBIT: 9 rows, total 675.5, average 75.06. |
| By branch | BR001: 6 rows, gross 930.5, net 529.5. BR002: 6 rows, gross 1355.0, net 1075.0. BR003: 8 rows, gross 2450.0, net 1780.0. |
| By account | 10 accounts with 2 transactions each (20 in total). |

Amounts are always positive, so `SUM(amount)` is gross volume, not a balance. The by-account and by-branch summaries show it next to `net_cash_flow` (`SUM(signed_amount)`, credits minus debits). Account A1002 shows the difference: gross 160.5 but net -160.5, because it only has debits. Totals: gross 4735.5, net 3384.5.

### Part 5: join relationships

`joins.py` joins the four tables with inner joins, all many-to-one, so the joined result keeps exactly 20 rows:

```text
bank_transaction.account_id -> account.account_id      (each transaction belongs to one account)
account.customer_id         -> customer.customer_id    (each account belongs to one customer)
account.branch_id           -> branch.branch_id        (each account is held at one branch)
```

Transactions do not carry a branch or a customer, so both are reached through the account. The analyses on the joined data:

| Analysis | Result |
|---|---|
| By account type | CHECKING: 12 rows, gross 3845.0, net 3485.0. SAVINGS: 8 rows, gross 890.5, net -100.5. |
| By branch | Same as Part 4 (6, 6 and 8 rows), a cross-check of the join. |
| By customer | All 6 customers appear (C1001 to C1006). Row counts add up to 20, gross to 4735.5 and net to 3384.5. |

### Part 6: data quality

`data_quality.py` ran seven checks in Week 6. Week 7 added an eighth, non-positive amounts, so it now runs eight and prints PASS or FAIL with the number of bad records for each:

| Check | Method | Result |
|---|---|---|
| Null transaction IDs | filter on `isNull()` | PASS, 0 |
| Null account IDs | filter on `isNull()` | PASS, 0 |
| Null amounts | filter on `isNull()` | PASS, 0 |
| Duplicate transaction IDs | `groupBy` the ID, keep counts above 1 | PASS, 0 |
| Transactions referencing nonexistent accounts | `left_anti` join to `account` | PASS, 0 |
| Accounts referencing nonexistent customers | `left_anti` join to `customer` | PASS, 0 |
| Accounts referencing nonexistent branches | `left_anti` join to `branch` | PASS, 0 |
| Non-positive amounts (added in Week 7) | filter on `amount <= 0` (null amounts are reported by the null check, not here) | PASS, 0 |

A `left_anti` join returns only the rows that have no match in the other table, which is how a missing reference is found. All eight pass because `banking.db` already enforces keys and the `CHECK (amount > 0)` rule. To show that the checks do not simply pass because the data happens to be clean, the tests also run them on small deliberately broken DataFrames (a duplicated ID, null values, an account that does not exist) and confirm they are detected.

### Part 7: Parquet

`parquet_io.py` writes the branch activity summary (3 rows) to `output/spark/parquet/branch_activity` with `df.write.parquet()`, reads it back with `spark.read.parquet()`, and compares the row counts. The intended operations are:

- **Write:** save a DataFrame as Parquet, a compressed, column-based file format that keeps the column types (Spark writes a folder of part files).
- **Read:** load that folder back into a DataFrame.
- **Validate:** the read-back row count must equal the original count (3).

**Result on the development machine (Windows): the write fails.** Spark stops with `java.io.FileNotFoundException: HADOOP_HOME and hadoop.home.dir are unset`, which comes from Hadoop's Windows file-permission code that needs `winutils.exe`. As the assignment instructs, Hadoop and winutils were not installed. The script catches the error, prints `PARQUET WRITE FAILED` with its first lines, and skips the read-back (`Read-back skipped: nothing was written.`). The saved output is `evidence/week6/part7_parquet_attempt.txt`. On a machine without this limitation, the same script writes, reads back and prints `Row counts match: True`. Because the write cannot run here, there is no Parquet read-back test in `tests/spark`.

### Part 8: larger synthetic dataset

`generate_transactions.py` creates `data/generated/synthetic_transactions.csv`:

- 100,000 rows with `transaction_id` (`G000001` and up), `account_id`, `transaction_date`, `transaction_type`, `amount` and `currency`.
- Each row uses a real `account_id` read from `banking.db` (10 accounts), so the relationship to the reference data is preserved.
- Dates are random days between 2026-01-01 and 2026-09-30. Types are about 55% CREDIT and 45% DEBIT. Amounts are between 1.00 and 5000.00, mostly small with a few large (a log-normal distribution).
- **Reproducible:** the random generator uses the fixed seed 42. The program was run twice and the SHA-256 hash of the file was identical both times (`03cc42c31ee270a2...`).
- The CSV is git-ignored (`data/generated/`); the generator is committed instead.

`large_data_analysis.py` loads the CSV with an explicit schema (so dates and amounts are read as `date` and `double`) and runs:

- **Filter:** `high_value_transactions()` (the same Part 3 function): 4,294 rows with amount >= 500.0.
- **Aggregation:** by transaction type: CREDIT 55,376 rows (total 8,194,376.73), DEBIT 44,624 rows (total 6,691,932.39).
- **Join:** to the real `account` table to get each account's branch: BR001 30,089 rows, BR002 30,035 rows, BR003 39,876 rows. The counts add up to 100,000, so the join dropped nothing.

### Part 9: Spark execution concepts (observed in this project)

`spark_concepts.py` prints:

- **Partitions (`df.rdd.getNumPartitions()`):** 8 for the 20-row `banking.db` transactions, 2 for the 100,000-row generated CSV, 1 for the summary after the `groupBy`. These are the numbers observed on the development machine.
- **Transformation:** `credit_transactions(generated)` - a `filter()`. It returns a DataFrame immediately and no work is done.
- **Action:** `credits.count()` - runs the plan and returns 55,376.
- **Shuffle:** `summary_by_type()` uses `groupBy("transaction_type")`. Its plan from `explain()` contains `Exchange hashpartitioning(transaction_type, 200)`, the shuffle that brings all rows with the same type into one partition. The `orderBy` adds a second `Exchange` (`rangepartitioning`). The plan also shows `AQEShuffleRead coalesced`, which is Spark merging the 200 planned shuffle partitions because the result is tiny. No repartitioning, caching or tuning was done.

### Part 10: Spark SQL comparison

`spark_sql_analysis.py` registers the transactions and accounts DataFrames as temporary views (`createOrReplaceTempView`) and runs the branch analysis with `spark.sql()`, next to the DataFrame version (`summary_by_branch()`). They express the same business operation:

| Business step | DataFrame API | Spark SQL |
|---|---|---|
| Find each transaction's branch | `.join(accounts, on="account_id")` | `JOIN accounts a ON t.account_id = a.account_id` |
| One result per branch | `.groupBy("branch_id")` | `GROUP BY a.branch_id` |
| Count and total | `F.count("*")`, `F.sum("amount")` inside `.agg()` | `COUNT(*)`, `SUM(t.amount)` |
| Credits minus debits | `F.when(...).otherwise(...)` (the `signed_amount` column) | `CASE WHEN ... THEN ... ELSE ... END` |

Both versions return the same three rows (BR001, BR002, BR003), and the comparison of the two results reports `Rows that differ between the two versions: 0`.

## Week 7: Dagster Orchestration

Week 7 adds one Dagster job, `banking_job`, that runs the Week 6 Spark code as four steps with real dependencies: extract -> validate -> transform -> publish. `database/banking.db` stays the only data source. The job code is in `orchestration/banking_job.py`. The ops are thin wrappers: the banking work is done by the existing functions in `src/spark/`.

| Op | Calls | What it does |
|---|---|---|
| `extract` | `load_transactions`, `load_accounts` (`load_data.py`) | Reads `banking.db` read-only and counts the transactions and accounts. Retries up to 2 times, 1 second apart. |
| `validate` | `run_checks` (`data_quality.py`), `raise_if_checks_failed` (`reporting.py`) | Loads the four tables, runs the eight data-quality checks, logs PASS or FAIL for each, and raises an error if any check fails. |
| `transform` | `get_transactions`, `summary_by_branch` (`analytics.py`) | Builds the branch summary with Spark and turns it into 3 plain rows. |
| `publish` | `write_branch_report` (`reporting.py`) | Writes the branch summary to `output/reports/branch_summary.csv`. |

### Prerequisites

- Everything from Setup above: Python 3.11, Java 17, and the packages in `requirements.txt`.
- `dagster==1.13.26` and `dagster-webserver==1.13.26`, which Week 7 added to `requirements.txt`. `pip install -r requirements.txt` installs them in the same `.venv`.
- `database/banking.db` in its final state (20 transactions), as for Week 6.

### DAGSTER_HOME

Dagster keeps its own run data in the folder named by the `DAGSTER_HOME` environment variable (for example, the small step outputs are stored under `dagster_home\storage`). This project uses a folder outside the repository: `C:\Users\zoyah\dagster_home`. The variable must be set again in every new terminal:

```powershell
$env:DAGSTER_HOME = "C:\Users\zoyah\dagster_home"
```

### Launch the Dagster UI

Run from the repository root, in its own terminal with the `.venv` active and `DAGSTER_HOME` set. Keep this terminal open: the UI stops when it is closed.

```powershell
dagster dev -f orchestration/banking_job.py
```

Open http://localhost:3000, select `banking_job`, open the Launchpad and click Launch Run. The Launchpad config has these fields, and the defaults are used if they are left unchanged:

| Op | Config | Default |
|---|---|---|
| `extract` | `db_path` | `database/banking.db` |
| `extract` | `fail_first_attempts` | `0` (used only to simulate a temporary failure) |
| `publish` | `output_dir` | `output/reports` |

Config edits made in the Launchpad are lost if the server is restarted.

### How the job runs

**Execution order.** The order comes from the dependencies in `banking_job()`: `publish(transform(validate(extract())))`. Each op takes the output of the op before it as its input, so Dagster cannot start an op until the op before it has succeeded. The job uses `in_process_executor`, so the steps run one at a time in a single process. The ops pass small dicts, not DataFrames: `extract` returns the database path and the row counts, `validate` returns the database path, `transform` returns the 3 branch rows, and `publish` returns the report path and totals.

**Error handling.**

- **Validation gate.** `validate` runs the eight data-quality checks from `data_quality.py` and logs PASS or FAIL for each one. `raise_if_checks_failed` then raises `DataQualityError` if any check found a bad record. `validate` logs `status=FAILED` with the check names and counts and raises the error again, so Dagster marks the step as failed. `transform` and `publish` depend on `validate`, so they never start. Measured in scenario B: `validate` failed with `1 data quality check(s) failed - Transactions referencing nonexistent accounts: 1`, `transform` and `publish` did not start, and the report folder was never created.
- **Retry.** Only `extract` has a `RetryPolicy` (2 retries, 1 second apart). It is meant for a temporary problem such as a file that cannot be read for a moment. `validate` has no retry because a data-quality failure gives the same result every time the same data is checked, so a retry would only delay the failure. This is a design choice. The temporary failure in scenario E is simulated with the `fail_first_attempts` config value, not caused by a real fault.

**Logging.** Every op logs `<op>: start` and `<op>: end, status=OK` with its row counts: transactions and accounts in `extract`, the number of checks passed in `validate`, the number of branch rows in `transform`, and the report path, rows, transaction count and net cash flow in `publish`. `validate` also logs each check by name. Only `validate` logs a `status=FAILED` line itself. If `extract` fails, the error is recorded in Dagster's own event log.

**Where `banking.db` is read and where output is written.**

- **Read:** `extract` (transactions and accounts), `validate` (all four tables) and `transform` (transactions and accounts) each read the database through `load_table` in `load_data.py`. It opens the file read-only (`mode=ro`), so the job cannot change `banking.db`. The path is the `db_path` config value, `database/banking.db` by default, and `extract` passes it on to the later ops.
- **Written:** only `publish` writes business output, to `branch_summary.csv` in the `output_dir` config folder (`output/reports` by default). It creates the folder if needed and overwrites the same file on every run. Dagster's own run history and step outputs are stored separately, under `DAGSTER_HOME`.

### Schedule

`banking_job` has a daily schedule, defined in the code as `daily_banking_schedule` and shown in the Dagster UI as `banking_job_schedule` (no name was given, so Dagster named it after the job). The daily schedule (`banking_job_schedule`, cron `0 6 * * *`, execution time zone UTC) is defined in code with default status STOPPED. I did not enable it. The Dagster schedule page shows "Schedule has never run", so no scheduled run was created, and every run in this submission was launched manually from the Launchpad. Because the schedule was never enabled, its automatic triggering was not tested. No time zone is set in the code, so Dagster uses UTC. Dagster only evaluates schedules while its daemon is running, which `dagster dev` starts together with the UI.

### Week 7 tests

Run from the repository root with `python -m pytest`. The job tests copy `banking.db` into a temporary folder and run on the copy, so the source database is never changed. The tests call the production functions and the job itself, not a rewritten version of the calculations.

| Command | Tests | Measured time |
|---|---|---|
| `python -m pytest tests/orchestration/test_reporting_logic.py -q` | 3 | 0.97 s (0.81 s in an earlier run), no Spark |
| `python -m pytest tests/orchestration/test_banking_job.py -k succeeds -q` | 1 | 269.49 s (4 min 29 s) |
| `python -m pytest tests/orchestration/test_banking_job.py -k validation_failure -q` | 1 | 420.09 s (7 min) |
| `python -m pytest` (full suite) | 64 | 3598.72 s (59 min 58 s), 64 passed |

- **`test_reporting_logic.py` (valid, bad and safe rerun):** valid data passes the gate and the report has the known totals (3 rows, 20 transactions, net cash flow 3384.5); bad data raises `DataQualityError` and the message names the failed check; running the report twice overwrites it with identical bytes and leaves one file.
- **`test_job_succeeds_on_isolated_copy_and_publishes_report`:** runs the real job with `execute_in_process` on a copy of `banking.db` and asserts success, the publish result (3 rows, 20 transactions, net 3384.5) and that the report file exists.
- **`test_validation_failure_blocks_publish`:** runs the job on a copy that has an orphan transaction (T9999 pointing to account A9999) and asserts that the run failed, that the only failed step is `validate`, that the only successful step is `extract`, and that the output folder was never created. This is the proof that the report step does not run after validation fails.
- **`test_non_positive_amounts_are_detected` (in `tests/spark/test_quality_and_joins.py`):** covers the eighth data-quality check added this week.

The full suite took about 10 minutes before Week 7 (58 tests, 592 s) and about 60 minutes in the Week 7 run. The two job tests took about 12 minutes when run on their own, which does not account for the whole increase. The cause was not determined.

### Safe reruns and run history

Two different things are involved when the job is run again:

- **Business-data idempotency:** running the job again on unchanged source data gives the same business result. `banking.db` is only read (`mode=ro`) and `publish` overwrites one report file, so the job cannot add rows to the database or create a second report. This follows from how the job is built.
- **Dagster run history:** every run is recorded under `DAGSTER_HOME`, so the history grows with each run. This is Dagster's own record of what ran. It is separate from the banking data, and a longer history does not mean the business data changed.

Scenario D measured this: before and after the second run the source still had 20 rows and 20 distinct transaction IDs, and the report still had 3 rows, 20 transactions and net cash flow 3384.5. The report file was byte-identical in this run (SHA-256 `457a405dcc3cb50a2f97668d7c6c12f78535f6147016148b54417851cd2349bf`).

### Evidence for scenarios A-E

The screenshots are in `evidence/week7/`. Run IDs are the first 8 characters of the run ID shown in the Dagster UI.

| Scenario | Run | Result | Files in `evidence/week7/` |
|---|---|---|---|
| A. Successful run | `134effe1` | Success in 5m42s on `banking.db`. extract: 20 transactions, 10 accounts. validate: 8 checks passed. transform: 3 branch rows. publish: 3 rows, 20 transactions, net 3384.5. | `A_success_config`, `A_success_run_overview`, `A_success_validate_log`, `A_success_publish_log`, `A_success_report_csv` |
| B. Validation failure | `85c3ad91` | Failure in 2m58s on a copy of `banking.db` with an orphan transaction (T9999 pointing to account A9999). extract succeeded, validate failed with `1 data quality check(s) failed - Transactions referencing nonexistent accounts: 1`, transform and publish did not start, and the report folder was never created. | `B_failure_launchpad_config`, `B_failure_run_overview`, `B_failure_validate_log`, `B_failure_publish_not_started`, `B_failure_no_report_folder` |
| C. Recovery | `05b1a1fb` | T9999 was deleted from the copy (20 rows, 0 orphans). With the same config the run succeeded in 3m32s with the same report numbers as A. | `C_recovery_input_fixed`, `C_recovery_launchpad_config`, `C_recovery_run_overview`, `C_recovery_publish_log`, `C_recovery_report_csv` |
| D. Safe rerun | `4c56e671` | Same source and config as C. Success in 2m36s. Source rows, report rows, report totals and report SHA-256 were the same before and after. | `D_rerun_baseline`, `D_rerun_launchpad_config`, `D_rerun_run_overview`, `D_rerun_after` |
| E. Temporary failure and retry | `173160f1` | With `fail_first_attempts: 1` on the fixed copy `banking_bad.db` (report folder `dagster_test\reports`), attempt 1 raised `Simulated transient failure on attempt 1` and Dagster scheduled a retry after 1 second. Attempt 2 succeeded (20 transactions, 10 accounts). The run succeeded in 2m50s. | `E_retry_launchpad_config`, `E_retry_run_overview`, `E_retry_event_log` |

- Scenarios B to E used a copy of the database, `banking_bad.db` in `C:\Users\zoyah\dagster_test`, and wrote the report to `C:\Users\zoyah\dagster_test\reports`, both outside the repository. Only scenario A ran on `database/banking.db`, and the job only reads that file. `database/banking.db` was never changed. The copy is not committed.
- The orphan transaction was the only kind of bad data that could be planted. The database's own constraints already reject null, zero or negative amounts, duplicate transaction IDs and null account IDs, so those cases cannot exist in a copy of `banking.db`. The checks for them are tested on small broken DataFrames in `tests/spark/test_quality_and_joins.py`.
- The gross amount (4735.5) is in the report CSV (`A_success_report_csv`), not in the publish log.
- The failure in scenario E is simulated with a config value. It is not a real network or disk fault.

### Incident note and Airflow comparison

- `docs/week7/incident_runbook.md`: one-page incident and runbook note for a failed validation (symptom, detection, likely cause, recovery, safe rerun, escalation and limitations).
- `docs/week7/airflow_vs_dagster.md`: short conceptual comparison of Airflow and Dagster (DAG and job, task and op, scheduler and daemon, retries, monitoring, backfills). Airflow was not installed, so that column is conceptual.

## Week 8: Integrated Banking Capstone

Week 8 adds a capstone pipeline that takes branch transaction CSV files through Landing, Bronze, Silver and Gold, keeps rejected rows in Exceptions, and records every run in audit tables. A plain Python runner runs five steps in order: discover -> ingest -> validate -> transform -> publish. It uses its own database, `output/capstone/banking_capstone.db`; `database/banking.db` is not used. Earlier-week files were not changed: the capstone only imports the single-value checks from `src/ingestion/validate.py`, the constants from `src/ingestion/config.py` and the Spark helpers from `src/spark/load_data.py`.

| Step | Code (`src/capstone/`) | What it does |
|---|---|---|
| discover | `discover.py` | Lists the files in `data/capstone/landing` named `BR<digits>_<YYYYMMDD>_TRANSACTION.csv`, reads branch ID and file date from the name and computes a SHA-256. Other files are listed as unrecognized. |
| ingest | `ingest.py` | Loads every row into Bronze as received, with filename, branch ID, run ID and source row number. An identical file that was already processed is skipped. |
| validate | `validate.py` | Bronze to Silver (accepted) and Exceptions (rejected, with all reasons). The first accepted `transaction_id` wins. Source rows must equal accepted plus rejected. |
| transform | `transform.py` | Builds Gold (count and total per branch, date and type) with SQL and with PySpark, and compares them. |
| publish | `publish.py` | Replaces the Gold table and `output/capstone/gold_branch_daily_summary.csv` only after the earlier steps succeeded. |
| runner | `pipeline.py` | Runs the steps in order and records SUCCESS or FAILED with the failing step. |

```powershell
python -m src.capstone.pipeline
python -m pytest tests/capstone -q
```

- Six scenarios were run on the real capstone database (normal input, bad rows, duplicates, late and corrected files, a failed run with recovery, the same inputs twice). All passed. End state: Silver 23 rows, Exceptions 16 rows, Gold 15 rows, Gold total 5436.0.
- The 66 capstone tests passed in 58.08 s.
- A run in a fresh copy of the repository (no `output` folder) with all 9 input files gave the same Silver, Exceptions, Gold and Gold CSV as the staged runs.
- Main limitations: only an ingest-step failure was shown on the real database; there is no upsert (a correction to an accepted transaction is kept in Exceptions and changes nothing); the Gold table and the Gold CSV are not replaced as one unit; Spark steps took about 14 to 47 seconds per run for an undetermined reason. The full list is in `docs/capstone/README.md`.

Documents and evidence:

- `docs/capstone/README.md`: setup, commands, input contract, assumptions, technology choices and known limitations for Week 8.
- `docs/capstone/DESIGN_DECISIONS.md`: duplicate policy, correction policy, idempotency strategy, SQL versus PySpark.
- `docs/capstone/RUNBOOK.md`: normal run, rerun, failed-run diagnosis, recovery and read-only queries.
- `docs/capstone/TEST_RESULTS.md`: scenario, expected, actual, result and evidence path.
- `docs/capstone/architecture.svg`: data-flow diagram with the orchestrator.
- `evidence/capstone/`: the screenshots cited in `TEST_RESULTS.md`.

## Week 8: CDP Readiness Extension — Customer 360 and API

The second part of the Week 8 assignment extends the Integrated Banking Capstone into a CDP-ready Customer 360 data product.

The objective is to create one unified profile per customer using trusted Silver transactions and synthetic customer/account reference data, then expose approved customer summary metrics through a small read-only HTTP API.

This extension reuses the existing capstone database:

`output/capstone/banking_capstone.db`

It is separate from the earlier `database/banking.db` and does not replace the existing branch-level Gold summary.

### Architecture

```text
Week 8 Silver Transactions
             |
             v
    Customer 360 Builder
             ^
             |
    ---------------------
    |                   |
customers.csv       accounts.csv
    |                   |
    ---------------------
             |
             v
     Data Validation
             |
       ---------------
       |             |
       v             v
   Accepted       Exceptions
   Customers      Rejected
   and Accounts    Records
       |
       v
   SQLite Database
       |
       v
  customer_360 SQL View
       |
       |----------------------|
       v                      v
customer_360.csv       Read-only HTTP API
                              |
                              v
                       JSON Responses
```

### Customer 360 Data Model

The extension uses three related entities:

`Customers → Accounts → Transactions`

| Entity | Grain | Primary key |
|---|---|---|
| Customers | One row per customer | customer_id |
| Accounts | One row per account | account_id |
| Silver transactions | One row per accepted transaction | transaction_id |
| Customer 360 Gold | One row per customer | customer_id |

The customer identity key is `customer_id`. Accounts are connected to customers through `customer_id`, while transactions are connected to accounts through `account_id`.

Customer records are not merged using names alone.

### Input Files

The extension uses two synthetic reference files:

| File | Location | Purpose |
|---|---|---|
| `customers.csv` | `data/customer360/` | Customer identifiers, names and segments |
| `accounts.csv` | `data/customer360/` | Account identifiers and customer ownership |

The extension uses customer IDs C001–C007, reuses
the 10 account IDs present in the Week 8 Capstone
Silver transactions, and adds A9001 as a synthetic
account for C003, who has no transactions.

C003 represents a customer with one account and no transactions. Account A9999 is deliberately included with an unknown customer reference C999 to demonstrate orphan-account validation.

Only synthetic data is used.

### Customer 360 Gold Transformation

The customer-level Gold data product is implemented as a SQLite SQL view named `customer_360`.

It contains:

- `customer_id`
- `customer_name`
- `account_count`
- `transaction_count`
- `total_transaction_amount`
- `last_transaction_date`

The SQL transformation uses separate account and transaction aggregations to avoid join fanout and inflated totals.

`LEFT JOIN` preserves customers without transactions, while `COALESCE()` returns zero for their missing transaction counts and totals.

The Gold CSV snapshot is generated at:

`output/customer360/customer_360.csv`

### Data Validation and Exceptions

The extension validates:

- Missing customer and account fields.
- Duplicate customer IDs.
- Duplicate account IDs.
- Account references to unknown customers.
- Accepted Silver transaction references to unknown extension accounts.

Rejected records are retained in `customer360_exceptions` with source metadata, raw record information and rejection reasons.

Relevant Week 8 transaction exceptions are also imported into the extension exception output.

Exception CSV:

`output/customer360/customer360_exceptions.csv`

### Build Commands

Run these commands from the repository root with the virtual environment activated.

**1. Build Customer 360**

```powershell
python -m src.customer360.build_customer360
```

The builder:

- Creates a SQLite database backup.
- Applies the Customer 360 schema.
- Loads synthetic customers and accounts.
- Validates references and records exceptions.
- Reuses accepted Silver transactions.
- Reconciles Silver and Gold transaction counts and totals.
- Exports Customer 360 and exception CSV snapshots.

**2. Run Customer 360 API Tests**

```powershell
python -m pytest tests/customer360/test_api_server.py -v
```

**Observed result:**

`6 passed in 0.75s`

The API tests cover known customer lookups, a customer without transactions, unknown customer handling, rejection of POST requests and parameterized customer ID lookup.

### Starting the Read-only API

The extension uses Python's built-in `http.server` library. No Flask, FastAPI or commercial CDP platform is required.

Start the server:

```powershell
python -m src.customer360.api_server
```

Server configuration:

| Setting | Value |
|---|---|
| Host | `127.0.0.1` |
| Port | `8765` |
| HTTP method | GET |
| Database | `banking_capstone.db` |

Keep the server terminal open while testing.

Available endpoint:

```http
GET /customers/<customer_id>/summary
```

Example URLs:

```text
http://127.0.0.1:8765/customers/C001/summary
http://127.0.0.1:8765/customers/C002/summary
http://127.0.0.1:8765/customers/C003/summary
http://127.0.0.1:8765/customers/C999/summary
```

Known customers return HTTP 200 with JSON summary data.

Unknown customers return HTTP 404:

```json
{
  "error": "Customer not found"
}
```

Write methods such as POST, PUT, PATCH and DELETE are rejected with HTTP 405.

Stop the server using `Ctrl+C`.

### Verified Build Results

The observed successful build produced the following results:

| Metric | Actual result |
|---|---:|
| Customers loaded | 7 |
| Accounts loaded | 11 |
| Silver transactions | 23 |
| Customer 360 Gold rows | 7 |
| Customer 360 exceptions | 17 |
| Mapped Silver transactions | 23 |
| Unmapped Silver transactions | 0 |
| Gold transaction count | 23 |
| Gold total transaction amount | 5436.00 |

The 17 exception records consist of one orphan account and 16 imported Week 8 transaction exceptions.

The Gold transaction count and amount were independently reconciled against mapped Silver transactions.

### Rerun Safety

The extension is designed to rebuild its own customer and account reference data without modifying the existing Week 8 Silver transactions or branch-level Gold summary.

A database backup is created before each build.

Rerun safety was verified by building Customer 360 twice with unchanged inputs and comparing the SHA-256 hashes of the Gold CSV.

The before-and-after hashes were identical.

This demonstrates that unchanged source data produces an identical Customer 360 business result.

### Documentation and Evidence

The extension includes the following supporting documents:

| Document | Purpose |
|---|---|
| `TEST_RESULTS.md` | Test scenarios, expected and actual results, and verification evidence |
| `ARCHITECTURE.md` | Architecture and data-flow explanation |
| `PRIVACY_AND_DESIGN.md` | Identity matching, grain, privacy decisions and production limitations |

Additional source files:

| File | Responsibility |
|---|---|
| `sql/customer360/schema.sql` | Customer and account tables, exception table, indexes and Customer 360 SQL view |
| `src/customer360/build_customer360.py` | Reference loading, validation, reconciliation and exports |
| `src/customer360/api_server.py` | Local read-only HTTP API |
| `tests/customer360/test_api_server.py` | API integration tests |

### Privacy and Production Limitations

The API binds only to localhost and uses read-only SQLite connections with parameterized SQL queries.

Email addresses and full transaction histories are excluded from the API response.

This is a local CDP-readiness demonstration, not a production Customer Data Platform.

A real banking implementation would additionally require authentication, authorization, audit logging, customer consent and privacy controls, rate limiting, secure transport and production monitoring.

The extension does not implement advanced cross-system identity resolution or historical customer attribute tracking using SCD Type 2.

### Conclusion

The Week 8 CDP Readiness Extension demonstrates how trusted banking transactions and customer/account reference data can be combined into a unified Customer 360 data product.

It reuses the existing Integrated Banking Capstone, validates customer-account relationships, preserves exception evidence, independently reconciles Gold metrics, demonstrates safe reruns and exposes approved customer summaries through a read-only HTTP API.

The implementation provides a practical demonstration of Customer 360 and CDP readiness using Python, SQLite, SQL and standard HTTP functionality.

## Tests

```powershell
python -m pytest -v
```

64 tests, all passing (the Week 7 full run: 64 passed in 3598.72 s). The Weeks 2-5 evidence is in `evidence/week_5/pytest_output.txt` and the Week 6 run including Spark (58 tests at that time) is in `evidence/week6/part11_pytest_output.txt`.

| File | Tests | Covers |
|---|---|---|
| `test_validation.py` | 15 | each field rule in isolation |
| `test_pipeline.py` | 8 | extract plus validate, bad files, DQ summary and log, duplicates, the 24 / 10 / 14 baseline |
| `test_database_integrity.py` | 8 | constraints, foreign keys, table list, row counts |
| `test_incremental_load.py` | 4 | new rows inserted, correction updates the value, rerun keeps the count, older file cannot reverse a correction |
| `test_analytics.py` | 6 | fact count matches banking, no duplicate IDs, valid dimension keys, customer and branch from account, known net cash flow result, repeatable rebuild |
| `tests/spark/test_load_and_transform.py` | 7 | input row counts (20, 10, 6, 3), known CREDIT count (11), CREDIT dataset contains only CREDIT, high-value count (3), the two Week 5 corrections (T1001 = 550.0, T4002 = 55.0), reporting columns, gross 4735.5 and net 3384.5 |
| `tests/spark/test_quality_and_joins.py` | 11 | known aggregation results (by type and by branch), duplicate IDs (none in the real data, detected in a bad DataFrame), nulls (same two checks), join keeps all 20 transactions, no orphan references (and one is detected in a bad DataFrame), all eight DQ checks pass, and the Week 7 non-positive amounts check detects a bad amount |
| `tests/orchestration/test_reporting_logic.py` | 3 | valid data passes the gate with known report totals, bad data raises `DataQualityError`, a rerun overwrites the report with identical bytes |
| `tests/orchestration/test_banking_job.py` | 2 | runs the real Dagster job with `execute_in_process` on a copy of `banking.db`: a success that publishes the report, and a validation failure that blocks publish |

`tests/spark/conftest.py` starts one SparkSession for the whole test run and loads the four tables from `banking.db` once, so the tests check the same loaders and functions the pipeline uses. The Spark tests only read `banking.db`.

Always use `python -m pytest`, not bare `pytest`. To run only the Spark tests: `python -m pytest tests/spark -v`.


Week 8 Core adds 66 tests in `tests/capstone/` (66 passed in 58.08 seconds).

The last recorded full-repository collection before the CDP Readiness Extension reported 130 tests (64 Week 7 baseline tests + 66 Week 8 Core tests).

The CDP Readiness Extension adds 6 API integration tests in `tests/customer360/test_api_server.py`. These were executed separately:

`python -m pytest tests/customer360/test_api_server.py -v`

Result: 6 passed in 0.75 seconds.

The complete repository test suite was executed after
adding the Customer 360 extension:

- 136 tests passed in 596.22 seconds (9 minutes 56 seconds).
- 0 failed tests.
- 1 non-fatal PySpark/pandas compatibility warning.

This includes 64 Week 7 baseline tests, 66 Week 8
Core tests and 6 Customer 360 API tests.


## Fixtures and Evidence

- `tests/fixtures/` holds deliberately constructed input: the T01 to T10 scenario inputs and the two daily test files. Generated `output/` folders inside the scenarios are ignored by git.
- `evidence/earlier_pipeline/`: pytest run for the earlier pipeline tests, DQ summary, pipeline log, Week 2 test results workbook.
- `evidence/class_4/`: integrity failures, SQL analysis results, query plans.
- `evidence/week_5/`: `incremental_load_evidence.txt` (first load, new rows), `correction_evidence.txt` (T1001 before and after), `rerun_evidence.txt` (stable counts, corrections kept), `table_counts.txt`, `analytical_query_results.txt`, `pytest_output.txt`.
- `evidence/week6/` (terminal output of the Spark scripts, saved as text; the Spark and Hadoop warning lines and the Windows `SUCCESS: The process with PID ...` lines were removed):

| File | Part | Shows |
|---|---|---|
| `part1_environment.txt` | 1 | Python, Java, PySpark and Spark versions, a 2-row DataFrame |
| `part2_load_inspect.txt` | 2 | sample rows, schema and row count of each loaded DataFrame |
| `part3_transformations.txt` | 3 | the transformations and their totals |
| `part4_aggregations.txt` | 4 | summaries by type, account and branch |
| `part5_joins.txt` | 5 | joined row count and activity by customer, branch and account type |
| `part6_data_quality.txt` | 6 | the seven checks, all PASS |
| `part7_parquet_attempt.txt` | 7 | the documented Windows Parquet write failure |
| `part8_large_data.txt` | 8 | the 100,000-row analysis |
| `part9_spark_concepts.txt` | 9 | partitions, transformation, action and the shuffle plan |
| `part10_spark_sql.txt` | 10 | DataFrame and Spark SQL results side by side |
| `part11_pytest_output.txt` | 11 | the full pytest run: 58 passed |

## Assumptions

- The three supplied daily files are already valid, trusted input. Their values are not changed.
- A later row with an existing `transaction_id` is a correction, so the stored row is updated to the later values.
- "Later" is decided by the file name: files are named `transactions_YYYYMMDD.csv`, so sorting the names sorts them by date.
- Dates are stored as text in `YYYY-MM-DD` format. The daily loader also accepts `MM/DD/YYYY` and converts it.
- All transactions are in USD. `amount` is always positive, and `transaction_type` (`CREDIT` or `DEBIT`) gives the direction.
- Customer, account, branch and transaction IDs are stable business keys, so the star schema uses them directly (no surrogate keys).
- `banking.db` is the trusted relational state. `analytics.db` is derived from it and can always be rebuilt.
- The earlier pipeline's only run-summary output is `output/dq/DQsummary.csv`, so there is no separate summary folder.
- Week 6: the Spark pipeline starts from `banking.db`, as instructed, and is run after the incremental load, so it sees the 20 final transactions with the corrections already applied.
- Week 6: a transaction is "high value" when `amount >= 500.0`. This threshold is a documented choice, not a rule from the data.
- Week 6: the synthetic data uses the 10 real account IDs from `banking.db`, and its IDs start with `G` so they cannot be confused with real transaction IDs.

## Known Limitations

- **Corrections are ordered by file name, not by event time.** If a file were renamed so its date no longer matches its contents, the stale-file guard would compare the wrong order.
- **Only the latest value is kept.** When a correction updates a row, the old value is overwritten, so `banking.db` has no history of changes. History tracking (SCD Type 2) was out of scope this week. The old and new values are shown in `evidence/week_5/correction_evidence.txt`.
- **`analytics.db` is rebuilt completely each time.** That keeps it simple and repeatable, but it would not suit very large data.
- **`SUM(amount)` is not a balance.** The data has no opening balances, so net cash flow only covers the loaded transactions.
- **The Week 2-5 stages are run by hand, in the order shown in Run Order.** There is no one-command orchestrator for them. The Week 7 Dagster job orchestrates only the Spark steps (extract, validate, transform, publish) and does not run the Week 2-5 stages.
- **Small, local data.** The pipeline reads local CSV files with pandas and uses SQLite, which is fine for this dataset but not for production banking workloads. A production system would also need security, backups and monitoring.
- **Rebuilding `banking.db` resets it to the 10 initial rows.** The daily files must be loaded again after `build_database`.

Week 6 (Spark) limitations:

- **Parquet write fails on Windows.** `df.write.parquet()` fails with a `HADOOP_HOME` / winutils error, so Parquet output and its read-back validation could not run on the development machine. Hadoop and winutils were deliberately not installed, as the assignment instructs. The attempted code is `src/spark/parquet_io.py` and the error output is in `evidence/week6/part7_parquet_attempt.txt`. No Parquet files are committed.
- **Hadoop warnings on every Spark run.** Spark prints `Did not find winutils.exe` and `Unable to load native-hadoop library` warnings. They are harmless for everything except Parquet.
- **Pandas warning.** PySpark 4.2.0 warns that it does not fully support pandas 3 or newer (the project uses pandas 3.0.6). It only affects Spark's pandas conversion features, which this project does not use, so the pandas version was left unchanged to avoid breaking the Week 2-5 code and tests.
- **Spark jobs on the `banking.db` tables are slow on the development machine.** Measured: each job on those DataFrames (built from Python rows) took about 11 seconds, even a plain `count()` on 20 rows, while jobs on the DataFrame read from the 100,000-row CSV took about 0.6 seconds. Shuffles, row count and the number of partitions did not explain it (a one-partition copy took the same time). The exact cause was not determined. As a result the full test suite (58 tests) takes about 10 minutes (592 seconds in the saved run), and the 17 Spark tests take several minutes. No caching or repartitioning was added, because those are out of scope.
- **Windows noise in the terminal.** After a Spark script ends, Windows prints `SUCCESS: The process with PID ... has been terminated` lines. They are harmless.
- **Spark reads `banking.db` through Python.** Spark cannot read SQLite directly without a JDBC driver, so tables are read with `sqlite3` and converted with `createDataFrame`. That is fine for these small tables, but it is not how Spark would read a large database.

Week 7 (Dagster) limitations:

- **The schedule was never enabled.** `banking_job_schedule` is defined with default status STOPPED and the Dagster UI shows "Schedule has never run". Its automatic triggering was therefore not tested; only the definition (cron `0 6 * * *`, target `banking_job`) was checked in the UI. Every run was launched manually from the Launchpad.
- **The schedule time zone is UTC.** No time zone is set in the code, so Dagster uses UTC and the UI shows 06:00 UTC, not local time.
- **The retry is simulated.** The temporary failure in scenario E is raised by the `fail_first_attempts` config value, not by a real network or disk fault. It proves that the retry policy on `extract` retries and then succeeds. Only `extract` has a retry policy.
- **Only one kind of bad data was planted.** Scenario B used an orphan transaction because the database's own constraints reject the other kinds. The other checks are tested on small broken DataFrames, not through the Dagster job.
- **Only `validate` logs a failed status itself.** If `extract`, `transform` or `publish` fails, the error is recorded in Dagster's event log, not by a `status=FAILED` line from the op. A real `extract` failure, such as a missing database file, was not tested.
- **Spark steps are slow, and the cause was not determined.** Measured in scenario A on 20 transactions: `extract` 1m30s, `validate` 3m28s, `transform` 38s. The success test took 269.49 s and the validation-failure test 420.09 s, and durations varied between runs. The full suite took 3598.72 s (59m58s), against 592 s for the 58 tests before Week 7. The two job tests alone (about 12 minutes) do not account for that difference. These are observations only.
- **Compute logs are not captured on Windows.** Dagster reports that compute log capture is disabled on Windows. The `context.log` lines from the ops still appear in the UI event log, which is where the scenario evidence comes from.
- **Dagster warnings at startup.** `dagster dev` warns that `dev_command` is superseded by `dg dev`, and that there is no `dagster.yaml`, so Dagster uses `DAGSTER_HOME`. The job runs normally. PySpark also warns about pandas 3 (see Week 6 limitations).
- **The Dagster UI must stay open and set up each time.** The UI stops when its terminal is closed, `DAGSTER_HOME` must be set again in every new terminal, and Launchpad config edits are lost if the server restarts.
- **The report is a CSV, not Parquet.** The Week 6 Parquet write fails on Windows, so `publish` uses Python's `csv` module. It overwrites one file and keeps no history of earlier reports.
- **The ops pass small dicts, not DataFrames.** `transform` converts the 3 branch rows with `collect()` before Dagster stores them. That is fine for 3 rows, but it would not suit a large result.

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

## Week 6 Understanding Questions

### 1. What is the difference between Apache Spark and PySpark?

Apache Spark is the data-processing engine itself. It is written in Scala and runs on Java, which is why this project needs Java 17. PySpark is the Python interface to that engine: I write Python, and PySpark sends the work to Spark.

### 2. What is a Spark DataFrame?

A DataFrame is a table of rows and named columns with a schema (a type for each column). In this project, `load_transactions()` returns a DataFrame of the 20 banking transactions. DataFrames are not changed in place: every operation, such as `filter`, returns a new DataFrame.

### 3. What is the difference between a transformation and an action?

A transformation describes a change to the data and returns a new DataFrame; an action makes Spark actually run the work and return a result. Transformation example: `credit_transactions()` in `transformations.py`, which is a `filter()` on `transaction_type`. Action example: `credits.count()` in `spark_concepts.py`, which returned 55,376 on the generated data.

### 4. What does lazy evaluation mean in Spark?

Spark does not run a transformation when I write it; it only records what I asked for as a plan. The work starts when an action is called. In `spark_concepts.py`, calling `credit_transactions()` returned a DataFrame immediately, and the actual filtering happened only at `count()`. This lets Spark look at the whole plan before it runs anything.

### 5. What is a partition?

A partition is one chunk of a DataFrame that Spark can process separately from the others. Spark splits data into partitions so the chunks can be processed in parallel. In this project, `getNumPartitions()` gave 8 for the 20-row `banking.db` transactions, 2 for the 100,000-row generated CSV, and 1 for the summary after a `groupBy`.

### 6. What is a shuffle? Which operation in your project could cause one?

A shuffle moves rows between partitions so that rows that belong together end up in the same partition. `groupBy("transaction_type")` in `summary_by_type()` causes one: all CREDIT rows must come together to be counted and summed. The query plan from `explain()` shows it as `Exchange hashpartitioning(transaction_type, 200)`, and the `orderBy` adds a second one (`rangepartitioning`). Joins, such as the one on `account_id` in `summary_by_branch()`, can also need a shuffle.

### 7. Why might Parquet be preferable to CSV for analytical processing?

Parquet stores data by column, compressed, and keeps the column types inside the file. An analysis that needs two columns can read only those two, and nothing has to guess types. CSV is plain text with no types, so in this project I had to give the generated CSV an explicit schema for the date and amount columns. Note: on my Windows machine the Parquet write failed with a `HADOOP_HOME` / winutils error, so I could not run it. The attempted code is `parquet_io.py` and the error is saved in `evidence/week6/part7_parquet_attempt.txt`.

### 8. How can Spark SQL and the PySpark DataFrame API solve the same data problem?

Both go through the same Spark engine. In `spark_sql_analysis.py` I registered the DataFrames as temporary views and wrote the branch analysis as one SQL query, then compared it with `summary_by_branch()`. `JOIN ... ON` matches `.join()`, `GROUP BY` matches `.groupBy()`, `COUNT/SUM` match `F.count/F.sum` inside `.agg()`, and `CASE WHEN` matches `F.when().otherwise()`. The two results had 0 differing rows.

### 9. Which parts of your banking business logic stayed the same when moving from Python/SQLite/SQL to PySpark?

The business rules did not change. Amounts are always positive, so net cash flow is credits minus debits (the `signed_amount` column), not `SUM(amount)`. The totals are the same as in Week 5: 20 transactions, 11 CREDIT, gross 4735.5 and net 3384.5. The data-quality ideas are the same (nulls, duplicate IDs, accounts and transactions pointing to something that does not exist), and the join path is the same: transaction to account, account to customer and branch.

### 10. What changed because Spark is a different processing engine?

Spark needs Java and a SparkSession, and it cannot read SQLite directly, so I read the tables with Python's `sqlite3` and built DataFrames from them. Work is lazy and split into partitions, and operations such as `groupBy` shuffle data. Spark DataFrames have no key constraints, so duplicates and orphan records have to be checked in code (`data_quality.py`). On this Windows machine, each Spark job on the `banking.db` DataFrames took about 11 seconds, versus 0.6 seconds for the CSV DataFrame, so the Spark tests take around 10 minutes.

## Author

Zoya Haider