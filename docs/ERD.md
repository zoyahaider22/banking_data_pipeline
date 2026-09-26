# Entity Relationship Diagram

## Banking Database ERD

```mermaid
erDiagram

    CUSTOMER ||--o{ ACCOUNT : owns
    BRANCH ||--o{ ACCOUNT : operates
    ACCOUNT ||--o{ BANK_TRANSACTION : contains

    CUSTOMER {
        TEXT customer_id PK
        TEXT customer_name
        TEXT email
        TEXT customer_segment
    }

    BRANCH {
        TEXT branch_id PK
        TEXT branch_name
        TEXT city
        TEXT state
    }

    ACCOUNT {
        TEXT account_id PK
        TEXT customer_id FK
        TEXT branch_id FK
        TEXT account_type
        TEXT account_status
    }

    BANK_TRANSACTION {
        TEXT transaction_id PK
        TEXT account_id FK
        TEXT transaction_date
        TEXT transaction_type
        REAL amount
        TEXT currency
        TEXT source_file
    }