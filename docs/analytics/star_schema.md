# Star Schema

## Analytics Database Star Schema

Grain of `fact_transaction`: **one row = one banking transaction.**

```mermaid
erDiagram

    DIM_CUSTOMER ||--o{ FACT_TRANSACTION : describes
    DIM_ACCOUNT ||--o{ FACT_TRANSACTION : describes
    DIM_BRANCH ||--o{ FACT_TRANSACTION : describes
    DIM_DATE ||--o{ FACT_TRANSACTION : describes

    FACT_TRANSACTION {
        TEXT transaction_id PK
        TEXT account_id FK
        TEXT customer_id FK
        TEXT branch_id FK
        INTEGER date_key FK
        TEXT transaction_type
        REAL amount
        TEXT currency
    }

    DIM_CUSTOMER {
        TEXT customer_id PK
        TEXT customer_name
        TEXT email
        TEXT customer_segment
    }

    DIM_ACCOUNT {
        TEXT account_id PK
        TEXT account_type
        TEXT account_status
    }

    DIM_BRANCH {
        TEXT branch_id PK
        TEXT branch_name
        TEXT city
        TEXT state
    }

    DIM_DATE {
        INTEGER date_key PK
        TEXT full_date
        INTEGER year
        INTEGER month
        INTEGER day
        TEXT day_name
    }
```

## Notes

- **Fact:** `fact_transaction` holds the measurable event (`amount`) and the keys that point to each dimension. `transaction_id` is the primary key, so the grain is enforced by the database.
- **Dimensions:** `dim_customer`, `dim_account`, `dim_branch` and `dim_date` describe who, which account, where and when.
- **Natural keys:** the dimensions use the business keys from `banking.db` (no surrogate keys, no history tracking), as the assignment scope requires.
- **Customer and branch** are carried on the fact row. They come from the transaction's account in `banking.db`.
- **`amount` is always positive.** `transaction_type` says whether it is money in (CREDIT) or out (DEBIT), so net cash flow is credits minus debits, not `SUM(amount)`.
