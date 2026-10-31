# Privacy and Design Decisions
## Week 8 — CDP Readiness Extension

## 1. Purpose

This document explains the identity, data modelling, privacy, validation and security decisions made while developing the Week 8 CDP Readiness Extension.

The extension builds a Customer 360 data product using synthetic customer and account references and accepted Silver transactions from the existing Integrated Banking Capstone.

The objective is to provide a unified customer-level view while preserving data quality, traceability and privacy.

## 2. Customer Identity and Matching Rule

The extension uses `customer_id` as the primary customer identity key.

The following rules apply:

- Each customer has one unique `customer_id`.
- Each account has one unique `account_id`.
- Every accepted account must reference an existing customer.
- Transactions are associated with customers through `account_id`.
- Customer records are not merged merely because their names or other descriptive attributes match.

The Week 8 extension uses synthetic customer identifiers C001 through C007.

The customer and account reference fixtures explicitly define the customer-account relationships. Existing synthetic account identifiers and accepted Silver transactions are reused.

The mapping between the original Week 8 customer identifiers and extension customer identifiers is maintained explicitly in the extension's synthetic reference data.

No fuzzy matching, name-based matching or automatic identity merging is performed.

In a real banking environment, identity resolution would require an approved customer master or governed identity-matching process.

## 3. Data Model and Customer-Level Grain

Customer 360 uses the following relationships:

`Customers → Accounts → Transactions`

The grain of each entity is:

| Entity | Grain | Primary key |
|---|---|---|
| Customers | One row per customer | customer_id |
| Accounts | One row per account | account_id |
| Silver transactions | One row per accepted transaction | transaction_id |
| Customer 360 Gold | One row per customer | customer_id |
| Customer 360 exceptions | One row per rejected record | exception_id |

The Customer 360 Gold view contains:

- `customer_id`
- `customer_name`
- `account_count`
- `transaction_count`
- `total_transaction_amount`
- `last_transaction_date`

The output contains exactly one row per valid customer.

### Customers Without Transactions

Customers without transaction activity must remain in the Customer 360 result.

The implementation uses `LEFT JOIN` and `COALESCE()` to retain these customers.

For example, synthetic customer C003 has one account but no transactions.

Its expected profile is:

| Attribute | Value |
|---|---|
| customer_id | C003 |
| account_count | 1 |
| transaction_count | 0 |
| total_transaction_amount | 0.00 |
| last_transaction_date | NULL |

## 4. Join Fanout Prevention

A customer may own multiple accounts, and each account may have multiple transactions.

Joining all three tables without controlling the aggregation grain can multiply rows and inflate account counts and transaction totals.

To prevent this:

1. Account counts are calculated independently at customer grain.
2. Transaction metrics are calculated separately by joining accounts to Silver transactions.
3. The two aggregated results are joined to the customer reference table.

This ensures that account counts and monetary totals are not inflated by one-to-many joins.

The implementation uses `COUNT(transaction_id)`, `SUM(amount)` and `MAX(transaction_date)` for the transaction metrics.

## 5. Duplicate and Referential Integrity Policies

### Customer IDs

Duplicate customer identifiers are rejected. The first valid occurrence is retained.

### Account IDs

Duplicate account identifiers are rejected. The first valid occurrence is retained.

An account whose `customer_id` does not exist in the accepted customer reference is rejected.

The synthetic account A9999 references C999, which is deliberately absent from the customer file. It is retained in the exception evidence rather than inserted into the accepted accounts table.

### Transaction IDs

The existing Week 8 Silver transaction table uses `transaction_id` as its primary key.

The Week 8 validation process applies a first-accepted-record-wins duplicate policy. Previously accepted duplicate transaction IDs are rejected and retained in the Week 8 Exceptions table.

The Customer 360 extension imports rejected Week 8 transaction evidence into its own exception output.

The original Silver table is not modified by the extension.

## 6. Exception Management

Invalid reference records and relevant transaction exceptions are retained in `customer360_exceptions`.

The exception structure contains:

- Exception identifier.
- Entity type.
- Source filename.
- Source row number.
- Customer ID, when known.
- Account ID, when known.
- Transaction ID, when applicable.
- Raw record representation.
- Rejection reasons.
- Recorded timestamp.

The exception table intentionally does not impose foreign keys on rejected customer and account identifiers. This allows orphan records to be retained for investigation.

Exceptions are exported to:

`output/customer360/customer360_exceptions.csv`

The extension also preserves the original Week 8 Exceptions table.

## 7. Privacy and Sensitive Fields Excluded

All customer and account records used in this demonstration are synthetic, as required by the assignment.

The extension's customer reference fixture contains:

- customer_id
- customer_name
- customer_segment

The original Week 8 customer reference included email addresses, but email is deliberately excluded from the Customer 360 extension input and published output.

The Customer 360 Gold CSV does not include:

- Email addresses.
- Phone numbers.
- Full transaction histories.
- Credentials or authentication information.

The read-only API exposes only the approved customer summary metrics:

- customer_id
- account_count
- transaction_count
- total_transaction_amount

Individual account identifiers and transaction-level records are not returned through the API.

Rejected transaction details remain restricted to the extension's exception evidence and are not exposed through the customer summary endpoint.

No real customer information should be used in this demonstration.

## 8. Data Freshness and Provenance

Customer 360 is rebuilt from:

1. The current accepted Week 8 Silver transaction records.
2. `data/customer360/customers.csv`.
3. `data/customer360/accounts.csv`.

Data freshness depends on the latest successful Customer 360 build.

The extension currently uses an on-demand Python build process rather than a scheduled or continuously running refresh.

When the source references or Silver transactions change, the builder must be executed again to refresh the Customer 360 view and CSV snapshot.

### Provenance

Week 8 Silver transactions retain source metadata, including:

- Source filename.
- Source row number.
- Bronze record identifier.
- Pipeline run identifier.

The Customer 360 transformation uses the account relationship to associate transactions with customers.

The extension's exceptions also preserve source filenames and row numbers where available.

The Gold profile does not contain a separate per-transaction lineage list. Transaction-level provenance remains available through the underlying Week 8 Silver data.

## 9. Rerun Safety and Data Preservation

The extension rebuilds its own customer and account reference tables and exception records from the supplied inputs.

Before rebuilding, it creates a SQLite database backup.

The extension does not delete or update:

- Week 8 Bronze transactions.
- Week 8 Silver transactions.
- Week 8 Exceptions.
- Week 8 branch-level Gold summaries.

Customer 360 metrics are recalculated from the current reference data and Silver transactions.

Rerun safety was demonstrated by rebuilding the data product with unchanged inputs and comparing the SHA-256 hashes of the Gold CSV before and after execution.

The hashes were identical.

The database transaction and CSV file exports are not one combined atomic operation; exported files must be verified after a successful build.

## 10. API Security Design

The Customer 360 API is implemented using Python's built-in `http.server` library.

Its security-related design decisions include:

- Binding to `127.0.0.1` only.
- Providing only a read-only GET endpoint.
- Using parameterized SQL for customer ID lookups.
- Opening SQLite connections in read-only mode.
- Enabling SQLite query-only mode.
- Rejecting POST, PUT, PATCH and DELETE methods.
- Returning HTTP 404 for unknown customers.
- Avoiding exposure of full transaction histories and email addresses.

The API is intended for a local demonstration and is not a production banking service.

## 11. Production Controls Not Implemented

A real banking Customer Data Platform or customer-facing API would require additional controls.

| Production control | Status in this extension |
|---|---|
| Authentication | Not implemented |
| Role-based authorization | Not implemented |
| Customer consent management | Not implemented |
| Production privacy and retention policies | Not implemented |
| API audit logging | Not implemented |
| Rate limiting | Not implemented |
| HTTPS and secure deployment | Not implemented |
| Production monitoring and alerting | Not implemented |

The current localhost-only API reduces network exposure during the demonstration but does not replace these production controls.

## 12. Design Limitations

The implementation demonstrates Customer 360 readiness using a small synthetic dataset.

Current limitations include:

- Only a limited set of customer and account attributes is modelled.
- Identity resolution uses an explicit customer ID rather than advanced cross-system matching.
- Data refresh is manual.
- The API does not provide authentication or authorization.
- The extension does not implement historical customer attribute tracking using SCD Type 2.
- The extension is designed for local execution rather than distributed production workloads.

These limitations should be addressed before adapting the design to a real banking environment.

## 13. Conclusion

The Week 8 CDP Readiness Extension demonstrates a controlled approach to building a unified customer-level data product from trusted banking transactions.

Explicit customer identity keys, validated account relationships, separate aggregation stages, exception retention, privacy-conscious outputs, independent reconciliation and rerun safety help establish a reliable foundation.

The read-only API demonstrates how an approved Customer 360 summary can be exposed without providing direct database access.

The implementation is a local CDP-readiness demonstration and not a complete production Customer Data Platform.