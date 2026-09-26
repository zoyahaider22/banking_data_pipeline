# Week 4 - Relational Banking Database

## Overview

This project extends the Week 3 branch transaction pipeline by moving validated transaction data into a relational SQLite banking database.

The Week 3 pipeline produced 24 transaction records, of which 10 were valid and 14 were rejected. Week 4 uses only the 10 validated transactions and combines them with the supplied customer, account, and branch reference data.

The database is designed to preserve relationships between customers, accounts, branches, and transactions while using database constraints to protect data integrity.

The project also includes SQL analysis, automated database integrity tests, deliberate constraint-failure evidence, and an `EXPLAIN QUERY PLAN` investigation.

---

## Project Objectives

The main objectives of this project are:

- Build a normalized relational banking database using SQLite.
- Load the supplied customer, branch, account, and Week 3 valid transaction data.
- Preserve Customer -> Account, Branch -> Account, and Account -> Transaction relationships.
- Enforce primary-key, foreign-key, `NOT NULL`, and `CHECK` constraints.
- Make the database build process safe to rerun.
- Demonstrate database integrity failures using deliberate invalid inserts.
- Perform meaningful SQL analysis using JOINs, aggregations, CASE expressions, CTEs, and window functions.
- Investigate SQLite query plans before and after creating an index.
- Automate important database behavior using pytest.
- Produce evidence that demonstrates the database works as designed.

---

## Technologies Used

- Python 3.11
- SQLite
- Python `sqlite3`
- SQL
- pytest
- CSV files
- Markdown documentation

No external database server is required.

---

## Architecture and Data Flow

The project follows this flow:

```text
Week 3 Valid Transactions
        |
        v
valid_transactions.csv
        |
        +------------------+
        |                  |
        v                  v
customers.csv        branches.csv
        |                  |
        +--------+---------+
                 |
                 v
           accounts.csv
                 |
                 v
          SQLite Database
            banking.db
                 |
       +---------+---------+
       |         |         |
       v         v         v
   Customer   Branch    Account
                           |
                           v
                    Bank Transaction
                           |
                           v
                     SQL Analysis
                           |
                           v
                 Query Plan / Index
                           |
                           v
                       Evidence
```

The database loading order is:

```text
Customer
   |
   v
Account
   |
   v
Transaction

Branch
   |
   v
Account
```

This loading order ensures that referenced parent records exist before dependent records are inserted.

---

## Relational Database Design

The database contains four main entities:

```text
CUSTOMER
    |
    | 1-to-many
    v
ACCOUNT
    ^
    | many-to-1
    |
BRANCH

ACCOUNT
    |
    | 1-to-many
    v
BANK_TRANSACTION
```

### Tables

#### Customer

Stores customer master information.

| Column | Type | Constraint |
|---|---|---|
| `customer_id` | TEXT | PRIMARY KEY |
| `customer_name` | TEXT | NOT NULL |
| `email` | TEXT | NOT NULL |
| `customer_segment` | TEXT | NOT NULL |

#### Branch

Stores bank branch information.

| Column | Type | Constraint |
|---|---|---|
| `branch_id` | TEXT | PRIMARY KEY |
| `branch_name` | TEXT | NOT NULL |
| `city` | TEXT | NOT NULL |
| `state` | TEXT | NOT NULL |

#### Account

Stores account information and connects customers to branches.

| Column | Type | Constraint |
|---|---|---|
| `account_id` | TEXT | PRIMARY KEY |
| `customer_id` | TEXT | NOT NULL, FOREIGN KEY |
| `branch_id` | TEXT | NOT NULL, FOREIGN KEY |
| `account_type` | TEXT | NOT NULL |
| `account_status` | TEXT | NOT NULL |

Relationships:

```text
account.customer_id -> customer.customer_id
account.branch_id   -> branch.branch_id
```

#### Bank Transaction

Stores validated Week 3 transactions.

| Column | Type | Constraint |
|---|---|---|
| `transaction_id` | TEXT | PRIMARY KEY |
| `account_id` | TEXT | NOT NULL, FOREIGN KEY |
| `transaction_date` | TEXT | NOT NULL |
| `transaction_type` | TEXT | NOT NULL |
| `amount` | REAL | NOT NULL, CHECK(amount > 0) |
| `currency` | TEXT | NOT NULL |
| `source_file` | TEXT | NOT NULL |

Relationship:

```text
bank_transaction.account_id -> account.account_id
```

The table is named `bank_transaction` rather than `transaction` to avoid ambiguity with SQL transaction terminology.

---

## Why the Database Is Normalized

Customer information is not repeated on every transaction.

For example, a customer's name and email are stored once in the `customer` table rather than being copied into every transaction row.

The transaction stores only the `account_id`. The account identifies the customer through the foreign-key relationship.

This reduces:
- duplicate data
- inconsistent customer information
- update anomalies
- unnecessary storage

The same principle applies to branch information. Branch details are stored once in the `branch` table and referenced through `account.branch_id`.

The relational design therefore separates master data from transaction data while preserving the relationships between them.

---

## Supplied Data

The project uses the supplied reference datasets:

```text
data/
├── customers.csv
├── branches.csv
├── accounts.csv
└── valid_transactions.csv
```

The Week 3 valid transaction output contains:

```text
Total Week 3 transactions: 24
Valid transactions:        10
Invalid transactions:      14
```

Only the 10 valid transactions are loaded into the database.

The invalid Week 3 transactions are not loaded as production transactions.

---

## Project Structure

```text
week4_banking_database/
│
├── data/
│   ├── customers.csv
│   ├── branches.csv
│   ├── accounts.csv
│   └── valid_transactions.csv
│
├── docs/
│   └── ERD.md
│
├── evidence/
│   ├── capture_integrity_evidence.py
│   ├── capture_sql_analysis.py
│   ├── query_plan_analysis.py
│   ├── integrity_failures.txt
│   ├── sql_analysis_results.txt
│   └── query_plan_results.txt
│
├── sql/
│   └── analysis_queries.sql
│
├── src/
│   ├── analysis.py
│   ├── config.py
│   ├── database.py
│   ├── loader.py
│   └── schema.py
│
├── tests/
│   └── test_database_integrity.py
│
├── banking.db
├── build_database.py
├── .gitignore
└── README.md
```

---

## Database Build and Load

The complete database can be rebuilt using:

```bash
py build_database.py
```

The build process:

1. Removes the existing database when rebuilding.
2. Creates `banking.db`.
3. Enables SQLite foreign-key enforcement.
4. Creates the database schema.
5. Loads customers.
6. Loads branches.
7. Loads accounts.
8. Loads the 10 valid Week 3 transactions.
9. Commits the data.
10. Reports the final row counts.

Expected loaded data:

```text
Customers loaded: 6
Branches loaded: 3
Accounts loaded: 10
Transactions loaded: 10
```

The database can therefore be rebuilt from the supplied input files instead of depending on manually inserted records.

---

## Safe Rerun Behavior

The database build process removes the existing `banking.db` before rebuilding it.

This means running:

```bash
py build_database.py
```

again creates a clean database instead of silently appending duplicate business records.

The expected counts remain:

```text
customer:          6
branch:            3
account:          10
bank_transaction: 10
```

---

## Data Integrity Strategy

Data integrity is protected at two levels.

### 1. Python / Pipeline Validation

The Week 3 pipeline validates transaction data before it reaches the database.

This prevents invalid transaction records from being treated as valid production data.

The Week 4 database then provides a second layer of protection.

### 2. Database Constraints

SQLite enforces:
- `PRIMARY KEY`
- `FOREIGN KEY`
- `NOT NULL`
- `CHECK`

For example:

```sql
CHECK(amount > 0)
```

prevents negative or zero transaction amounts from being inserted.

Foreign keys prevent accounts from referencing nonexistent customers and transactions from referencing nonexistent accounts.

This provides defense in depth: Python validates incoming data, while the database protects the stored relational data.

---

## Integrity Failure Evidence

The project deliberately attempts invalid operations to demonstrate that SQLite protects the database.

The following scenarios are tested:

### 1. Nonexistent Account

A transaction is inserted with an account ID that does not exist.

**Expected result:**
```text
FOREIGN KEY constraint failed
```

### 2. Nonexistent Customer

An account is inserted with a customer ID that does not exist.

**Expected result:**
```text
FOREIGN KEY constraint failed
```

### 3. Duplicate Primary Key

A customer is inserted using an existing customer ID.

**Expected result:**
```text
UNIQUE constraint failed: customer.customer_id
```

### 4. Negative Transaction Amount

A transaction is inserted with an amount of -50.

**Expected result:**
```text
CHECK constraint failed: amount > 0
```

### 5. Missing Required Customer Name

A customer is inserted with `customer_name = NULL`.

**Expected result:**
```text
NOT NULL constraint failed: customer.customer_name
```

The captured evidence is stored in:

```text
evidence/integrity_failures.txt
```

---

## SQL Analysis

The SQL analysis is stored in:

```text
sql/analysis_queries.sql
```

The project contains 15 SQL analysis queries.

The queries cover the required categories:

### JOINs

Queries connect transactions with:
- accounts
- customers
- branches

This allows transaction-level data to be analyzed together with related banking information.

### Aggregations

Queries calculate:
- transaction counts
- transaction totals
- customer totals
- branch totals
- transaction-type totals

### CASE

`CASE` expressions classify transaction amounts into meaningful amount bands.

For example: Small / Medium / Large

This allows transaction distributions to be analyzed using business-friendly categories.

### CTE

Common Table Expressions are used to create derived results that can then be filtered or analyzed.

### Window Functions

The analysis includes window-function queries such as ranking transactions within groups and calculating running totals.

### Original Business Question

The project also includes a business-oriented question using SQL rather than only reproducing basic table queries.

The complete query results are captured in:

```text
evidence/sql_analysis_results.txt
```

Run the SQL analysis with:

```bash
py -m src.analysis
```

---

## Query Plan and Index Investigation

The project investigates the query plan for a transaction-to-account-to-customer join.

The query uses `bank_transaction.account_id` as a join key, so an index was created:

```sql
CREATE INDEX IF NOT EXISTS idx_bank_transaction_account_id
ON bank_transaction(account_id);
```

The query plan was captured both before and after the index.

The investigation can be run with:

```bash
py -m evidence.query_plan_analysis
```

Evidence is stored in:

```text
evidence/query_plan_results.txt
```

### Important Observation

The database contains only 10 transaction rows.

After adding the index, SQLite's query plan for this particular query still reported a scan of the transaction table.

Therefore, this project does not claim that the index produced a measurable runtime improvement.

The purpose of the investigation is to demonstrate how `EXPLAIN QUERY PLAN` can be used to understand SQLite's access strategy and reason about appropriate indexing.

A query plan describes the strategy SQLite chooses; it does not by itself prove a measurable performance improvement.

---

## Automated Testing

Database behavior is tested using pytest.

The automated test suite currently contains 8 meaningful database tests covering:

- foreign-key rejection for nonexistent accounts
- foreign-key rejection for nonexistent customers
- duplicate primary-key rejection
- CHECK constraint rejection for negative transaction amounts
- NOT NULL constraint rejection
- expected database tables
- foreign-key enforcement
- expected row counts loaded through the production `load_all_data()` function

The tests use isolated SQLite in-memory databases where appropriate and verify actual database behavior.

Run the complete test suite with:

```bash
py -m pytest -q

---

## Evidence Files

The project stores supporting evidence separately from source code.

```text
evidence/
├── integrity_failures.txt
├── sql_analysis_results.txt
└── query_plan_results.txt
```

These files provide evidence for:
- database integrity failures
- SQL query results
- before/after query-plan investigation

---

## How to Run the Project

### 1. Activate the virtual environment

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Build the database

```bash
py build_database.py
```

### 3. Check database analysis and row counts

```bash
py -m src.analysis
```

### 4. Run integrity tests

```bash
py -m pytest -v
```

### 5. Generate integrity-failure evidence

```bash
py -m evidence.capture_integrity_evidence
```

### 6. Generate SQL analysis evidence

```bash
py -m evidence.capture_sql_analysis
```

### 7. Generate query-plan evidence

```bash
py -m evidence.query_plan_analysis
```

---

## Conceptual Questions

### 1. Why should customer information not be repeated on every transaction?

Customer information should be stored in the `customer` table and referenced through the account relationship.

Repeating customer information on every transaction creates duplicate data and can cause inconsistencies. For example, if a customer's email changes, many transaction rows would need to be updated.

Storing customer information once reduces duplication and makes updates more reliable.

### 2. What is the difference between Python validation and a database constraint?

Python validation checks data before it is loaded into the database.

For example, the Week 3 pipeline determines whether a transaction is valid before loading it.

A database constraint is enforced by SQLite itself when data is inserted or updated.

For example:

```sql
CHECK(amount > 0)
```

prevents an invalid amount from being stored even if application-level validation is bypassed.

Therefore, Python validation helps prevent bad data from reaching the database, while database constraints protect the database itself.

### 3. What could happen if foreign-key enforcement were disabled?

If foreign-key enforcement were disabled, SQLite could allow records that reference nonexistent parent records.

For example, a transaction could contain:

```text
account_id = A9999
```

even if account `A9999` does not exist.

This would create broken relationships and make joins and downstream analysis less reliable.

The project therefore explicitly enables foreign-key enforcement.

### 4. Why might adding indexes to every column be a bad idea?

Indexes can improve lookup and join performance, but they also require storage and maintenance.

When rows are inserted, updated, or deleted, related indexes may also need to be maintained.

Adding unnecessary indexes can therefore increase storage and write overhead without providing a useful benefit.

Indexes should be created for columns that are frequently used for meaningful lookups, joins, filtering, or ordering.

### 5. What is one difference between this relational banking database and an analytical data warehouse?

This SQLite database is designed around relational banking entities such as customers, accounts, branches, and transactions.

It is suitable for transactional-style relational storage and integrity enforcement.

An analytical data warehouse is generally designed for large-scale analytical queries, reporting, historical analysis, and aggregations, often using a different modeling and storage strategy.

The main focus of this project is maintaining relational structure and data integrity while supporting useful SQL analysis.

---

## Assumptions

The following assumptions were made:

- The supplied CSV files are the authoritative reference data for customers, branches, and accounts.
- Only the 10 valid transactions produced by the Week 3 pipeline are loaded.
- Transaction amounts are stored as SQLite REAL values.
- Transaction dates are stored as text using the `YYYY-MM-DD` format inherited from the validated Week 3 output.
- Transaction currency is expected to be USD based on the Week 3 validation rules and supplied data.
- Customer, branch, account, and transaction identifiers are treated as stable business keys.
- SQLite is sufficient for this local assignment and does not require a separate database server.

---

## Known Limitations and Future Improvements

### Limitations

**Small dataset**

The database contains only a small number of records. Because of this, query execution time is not representative of a production banking workload.

The query-plan investigation therefore focuses on SQLite's chosen access strategy rather than claiming measurable performance gains.

**SQLite scale**

SQLite is appropriate for this local assignment, but a production banking system would require stronger operational infrastructure, concurrency management, security controls, backup strategies, and monitoring.

### Future Improvements

Possible future improvements include:
- adding more realistic transaction history
- adding indexes based on real production query patterns
- adding additional database-level validation rules
- introducing database migrations
- adding more comprehensive automated SQL-result tests
- measuring query performance using a significantly larger dataset

---

## Week 4 Engineering Summary

Week 4 extends the validated Week 3 ETL pipeline into a relational database layer.

The main engineering principles demonstrated are:

```text
Validate first
     ↓
Store relationally
     ↓
Protect with constraints
     ↓
Test actual database behavior
     ↓
Analyze with SQL
     ↓
Investigate query plans
     ↓
Document evidence
```

The final database contains:
- 6 customers
- 3 branches
- 10 accounts
- 10 valid transactions

The project demonstrates not only that the database can be built, but also that its relationships, constraints, SQL analysis, and indexing decisions can be tested and supported with evidence.