# Week 9 – Standalone Banking Analytics with dbt and DuckDB

## 1. Project Overview

This project implements a reproducible banking analytics transformation pipeline using dbt Core and DuckDB.

It is a standalone Week 9 assignment and is intentionally maintained separately from the original banking data engineering capstone.

The project uses three synthetic banking CSV datasets: customers, accounts and transactions. dbt seeds load the input files into DuckDB, staging models standardize the data, an intermediate model enriches transactions, and mart models produce reporting-ready analytical tables.

The project also includes automated data-quality tests, SQL documentation, model lineage and a GitHub Actions CI workflow.

## 2. Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.11 | Runtime environment |
| dbt Core 1.10.13 | SQL transformation and testing |
| dbt-duckdb 1.10.1 | DuckDB adapter for dbt |
| DuckDB | Local analytical database |
| SQL | Data transformations and quality checks |
| Git and GitHub | Version control and collaboration |
| GitHub Actions | Continuous integration |

## 3. Input Datasets

The project uses three supplied synthetic CSV files.

| Dataset | Records | Description |
|---|---:|---|
| customers.csv | 12 | Customer identifiers, names, cities and segments |
| accounts.csv | 15 | Account identifiers, customer relationships and account details |
| transactions.csv | 48 | Transaction identifiers, dates, amounts, types and currencies |
| **Total** | **75** | **Input records** |

The original CSV contents are preserved in the seeds directory and are not modified.

### Business Rules

- Each account belongs to one customer.
- Each transaction belongs to one account.
- Transaction amounts are stored as positive magnitudes in the source data.
- DEPOSIT represents an inflow and receives a positive signed amount.
- PURCHASE and WITHDRAWAL represent outflows and receive negative signed amounts.
- All supplied transaction records use USD.
- Transaction types are restricted to DEPOSIT, PURCHASE and WITHDRAWAL.

## 4. Project Structure

```text
week_09_dbt_project/
│
├── README.md
├── requirements.txt
├── dbt_project.yml
├── profiles.yml.example
│
├── seeds/
│   ├── customers.csv
│   ├── accounts.csv
│   └── transactions.csv
│
├── models/
│   ├── staging/
│   │   ├── stg_customers.sql
│   │   ├── stg_accounts.sql
│   │   ├── stg_transactions.sql
│   │   └── sources_and_models.yml
│   │
│   ├── intermediate/
│   │   └── int_transaction_enriched.sql
│   │
│   └── marts/
│       ├── dim_accounts.sql
│       ├── fct_daily_account_activity.sql
│       └── marts.yml
│
├── tests/
│   └── assert_nonnegative_transaction_amount.sql
│
└── evidence/
    └── dbt_lineage.png
```

The GitHub Actions workflow is maintained separately at the repository root:

```text
.github/
└── workflows/
    └── week9_dbt_ci.yml
```

## 5. Data Transformation Architecture

The project follows a three-layer dbt transformation structure.

### 5.1 Seeds

The three CSV files are loaded into DuckDB using:

```bash
dbt seed --profiles-dir .
```

This creates the customers, accounts and transactions seed tables.

### 5.2 Staging Models

Staging models standardize the source data and provide consistently typed columns.

| Model | Source | Materialization |
|---|---|---|
| stg_customers | customers seed | View |
| stg_accounts | accounts seed | View |
| stg_transactions | transactions seed | View |

The models apply appropriate casts, trim text fields and convert dates and amounts into suitable database types.

### 5.3 Intermediate Model

**int_transaction_enriched**

This model joins transactions with accounts and customers using dbt's `ref()` function.

It includes transaction, account and customer information and derives the signed transaction amount using the following logic:

- DEPOSIT: positive amount.
- PURCHASE: negative amount.
- WITHDRAWAL: negative amount.

The intermediate model is materialized as a view.

### 5.4 Mart Models

**dim_accounts**

Creates one row per account, enriched with customer information.

It includes account ID, customer ID, customer name, city, customer segment, account type, opening date and account status.

Materialization: Table.

**fct_daily_account_activity**

Creates a daily account-level analytical fact table.

Its grain is one row per account per transaction date.

It includes:

- transaction_date
- account_id
- transaction_count
- total_deposits
- total_outflows
- net_amount

Materialization: Table.

The net amount represents total deposits minus total outflows.

## 6. Data Quality Tests

Data-quality rules are defined in YAML files and a custom SQL test.

| Test | Purpose |
|---|---|
| Unique customer_id | Prevent duplicate customer identifiers |
| Not-null customer_id | Ensure customer identifiers are present |
| Unique account_id | Prevent duplicate account identifiers |
| Not-null account_id | Ensure account identifiers are present |
| Unique transaction_id | Prevent duplicate transaction identifiers |
| Not-null transaction_id | Ensure transaction identifiers are present |
| Account-to-customer relationship | Verify account ownership references |
| Transaction-to-account relationship | Verify transaction account references |
| Accepted transaction types | Allow only DEPOSIT, PURCHASE and WITHDRAWAL |
| Custom negative-amount test | Detect negative raw transaction amounts |

The custom SQL test is implemented in:

`tests/assert_nonnegative_transaction_amount.sql`

A dbt singular SQL test passes when its query returns no failing records.

## 7. Model Lineage and Dependencies

The project uses dbt's `ref()` function to declare dependencies between seeds and transformation models.

The dependency flow is:

```text
customers → stg_customers ───────┐
                                 ├→ dim_accounts
accounts → stg_accounts ─────────┘

customers → stg_customers ───────┐
accounts → stg_accounts ─────────┤
transactions → stg_transactions ─┘
                                 |
                                 v
                      int_transaction_enriched
                                 |
                                 v
                      fct_daily_account_activity
```

The custom SQL test independently checks the transactions seed for negative raw amounts.

The complete generated dbt lineage graph is saved at:

`evidence/dbt_lineage.png`

## 8. Installation and Setup

### Requirements

- Python 3.11 or 3.12
- Git
- dbt Core
- dbt DuckDB adapter

### Step 1: Create a virtual environment

From the Week 9 project directory:

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### Step 2: Install dependencies

```bash
python -m pip install -r requirements.txt
```

### Step 3: Configure the DuckDB profile

Copy the example profile:

```powershell
Copy-Item profiles.yml.example profiles.yml
```

The profile uses a local DuckDB database named `dev.duckdb`.

### Step 4: Validate the connection

```bash
dbt debug --profiles-dir .
```

### Step 5: Build the project

Load seeds:

```bash
dbt seed --profiles-dir .
```

Build all seeds, models and tests:

```bash
dbt build --profiles-dir .
```

Run data tests independently:

```bash
dbt test --profiles-dir .
```

Generate documentation:

```bash
dbt docs generate --profiles-dir .
```

Serve documentation locally:

```bash
dbt docs serve --profiles-dir .
```

## 9. Test Results

The following results were recorded during local execution.

### Seed Loading

| Seed | Records loaded |
|---|---:|
| customers | 12 |
| accounts | 15 |
| transactions | 48 |
| Total | 75 |

Result: 3 seeds passed, 0 warnings and 0 errors.

### Individual Data Tests

Command:

```bash
dbt test --profiles-dir .
```

Result:

- 12 data tests passed.
- 0 warnings.
- 0 errors.

### Complete dbt Build

Command:

```bash
dbt build --profiles-dir .
```

Recorded result:

| Resource | Passed |
|---|---:|
| Seeds | 3 |
| Views | 4 |
| Tables | 2 |
| Data tests | 12 |
| Total | 21 |

Final result: 21 passed, 0 warnings and 0 errors.

Execution time recorded: 2.48 seconds.

## 10. Documentation and CI

dbt documentation was generated successfully using:

```bash
dbt docs generate --profiles-dir .
```

The generated documentation was served locally and the complete model lineage graph was inspected and saved in the evidence directory.

The repository also includes a GitHub Actions workflow:

`.github/workflows/week9_dbt_ci.yml`

The workflow is configured to run on pull requests that modify the Week 9 project or the workflow itself.

It checks out the repository, configures Python 3.11, installs the pinned dependencies, copies the example DuckDB profile and runs:

```bash
dbt build --profiles-dir .
```


### GitHub Actions CI Result

The GitHub Actions workflow was executed successfully through Pull Request #1.

- Workflow: Week 9 dbt CI
- Job: dbt-check
- Trigger: pull_request
- Result: Successful
- Execution time: 15 seconds

The workflow installed the project dependencies, configured the DuckDB profile and successfully executed `dbt build`.


## 11. Reproducibility and Limitations

- All input datasets are synthetic.
- Original input CSV files are preserved.
- Dependency versions are pinned in requirements.txt.
- The DuckDB database is created locally and is not committed.
- The local profiles.yml file is excluded from version control.
- Generated dbt target, logs and package directories are excluded from version control.
- The project demonstrates local analytical transformations and basic CI, not production deployment.
- The current custom SQL test checks for negative numeric transaction amounts; it does not independently validate every possible malformed value.


## 12. Test Failure Investigation

A controlled negative-amount scenario was performed to verify the custom SQL data-quality test.

### Failure Simulation

- The original transaction T001 had an amount of 28.50.
- A temporary negative amount of -10.00 was introduced directly into the local DuckDB transactions table.
- The original transactions.csv seed file was preserved.
- The command `dbt test --select assert_nonnegative_transaction_amount --profiles-dir .` was executed.
- The test correctly failed and returned one failing record because the negative amount violated the data-quality rule.

### Recovery

- The temporary database value for T001 was restored to 28.50.
- The original transactions.csv file was verified to contain 48 records.
- The complete project was rebuilt using `dbt build --profiles-dir .`.
- All three seeds, six models and twelve data tests completed successfully.

### Final Recovery Result

The final dbt build reported:

- 21 resources passed.
- 0 warnings.
- 0 errors.
- Original transaction data restored.

This investigation demonstrates that the custom SQL test detects invalid financial data and that the project can be rebuilt successfully after the test database is restored.

## 13. Conclusion

This project demonstrates how dbt Core and DuckDB can organize reproducible banking analytics transformations.

It includes CSV seed loading, staging views, an intermediate enrichment model, analytical mart tables, automated data-quality tests, model documentation, lineage visualization and a basic GitHub Actions CI workflow.

The implementation is maintained as a standalone Week 9 project, separate from the original banking capstone.
