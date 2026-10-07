# Data Lineage

## End-to-End Data Flow

```mermaid
flowchart TD

    RAW["data/raw<br/>branch CSV files (untrusted source)"] --> ING["src/ingestion<br/>extract, validate, DQ, logging"]

    ING --> VAL["data/validated<br/>valid_transactions.csv<br/>invalid_transactions.csv"]
    ING --> OUT["output/dq and output/logs<br/>DQsummary.csv, pipeline.log"]

    VAL --> BUILD["src/operational/build_database.py<br/>initial relational load"]
    REF["data/reference<br/>customers, accounts, branches"] --> BUILD

    BUILD --> BANK[("database/banking.db<br/>customer, branch, account, bank_transaction")]

    DAILY["data/daily<br/>transactions_20260907, 0908, 0909"] --> INC["src/operational/incremental_load.py<br/>UPSERT in date order"]
    INC --> BANK

    BANK --> ANA["src/analytics/build_analytics.py<br/>rebuilt from banking.db on every run"]

    ANA --> AN[("database/analytics.db<br/>dim_customer, dim_account, dim_branch,<br/>dim_date, fact_transaction")]

    AN --> SQLQ["sql/analytical_queries.sql<br/>7 business queries"]
    SQLQ --> RES["evidence/week_5<br/>analytical_query_results.txt"]
```

## Stages

1. **Ingestion and validation:** branch files in `data/raw` are read, validated and split into valid and invalid rows. Logs and the DQ summary go to `output/`.
2. **Initial load:** the valid rows and the reference files build `banking.db`.
3. **Incremental load:** each daily file is applied to `banking.db` in date order. New transaction IDs are inserted. An existing ID is a correction and is updated, unless the file is older than the one that wrote the stored row.
4. **Analytical build:** `analytics.db` is deleted and rebuilt from `banking.db` only. It never reads the raw branch files.
5. **Analysis:** the queries in `sql/analytical_queries.sql` run against `analytics.db`.

`tests/` verifies each stage, `evidence/` holds the captured proof, and `docs/` holds the diagrams.
