# TEST RESULTS — Week 8 CDP Readiness Extension

## 1. Overview

This document records the testing and verification performed for the Week 8 CDP Readiness Extension.

The extension reuses the accepted Silver transactions from the existing Integrated Banking Capstone and produces a customer-level Customer 360 Gold data product. It also exposes customer summaries through a read-only local HTTP API.

**Test environment:**
- Language: Python 3.11.3
- Database: SQLite
- Testing framework: pytest 9.1.1
- API: Python built-in `http.server`
- API host: `127.0.0.1`
- API port: `8765`

## 2. Customer 360 Build Verification

**Test scenario:** Build the Customer 360 data product using the synthetic customer and account reference files and existing Week 8 Silver transactions.

| Metric | Expected | Actual | Result |
|---|---:|---:|---|
| Customers loaded | 7 | 7 | PASS |
| Valid accounts loaded | 11 | 11 | PASS |
| Silver transactions | 23 | 23 | PASS |
| Customer 360 Gold rows | 7 | 7 | PASS |
| Exception records | 17 | 17 | PASS |
| Mapped Silver transactions | 23 | 23 | PASS |
| Unmapped Silver transactions | 0 | 0 | PASS |
| Gold transaction count | 23 | 23 | PASS |
| Gold transaction amount | 5436.00 | 5436.00 | PASS |

**Evidence:** Successful execution of:

```bash
python -m src.customer360.build_customer360
```

The build generated:
- `output/customer360/customer_360.csv`
- `output/customer360/customer360_exceptions.csv`
- A SQLite database backup under `output/customer360/backups/`

## 3. Customer 360 Output Verification

The Gold output contains one row per customer.

| Customer ID | Customer name | Account count | Transaction count | Total amount | Last transaction date |
|---|---|---:|---:|---:|---|
| C001 | Maya Patel | 2 | 5 | 870.50 | 2026-09-08 |
| C002 | Daniel Kim | 1 | 2 | 315.00 | 2026-09-07 |
| C003 | Grace Lee | 1 | 0 | 0.00 | NULL |
| C004 | Sofia Martinez | 2 | 5 | 1570.00 | 2026-09-07 |
| C005 | Noah Williams | 1 | 3 | 150.00 | 2026-09-09 |
| C006 | Ava Thompson | 2 | 4 | 1910.00 | 2026-09-10 |
| C007 | Ethan Brown | 2 | 4 | 620.50 | 2026-09-07 |

**Result: PASS**

The C003 scenario confirms that a customer with an account but no transactions remains in the Customer 360 output.

Its transaction count and total amount are zero, while its last transaction date is NULL.

This verifies the intended LEFT JOIN behaviour.

## 4. Data Quality and Exception Verification

**Test scenario:** Validate customer and account references and preserve rejected transaction evidence.

The supplied account fixture contains an orphan account:

```csv
A9999,C999,BR001,CHECKING,ACTIVE
```

Customer C999 does not exist in the customer reference file.

**Actual results:**

| Entity type | Exception count |
|---|---:|
| ACCOUNT | 1 |
| TRANSACTION | 16 |
| **Total** | **17** |

The orphan account was rejected with the reason:

`customer_id not found in customers reference`

The 16 transaction exceptions were imported from the existing Week 8 Exceptions table, preserving their rejection reasons.

**Result: PASS for the observed input scenarios.**

Note: Separate deliberately malformed customer and account fixtures for every missing-field and duplicate-ID condition have not yet been executed.

## 5. Independent Reconciliation

The Customer 360 Gold metrics were independently compared with the Silver transactions joined to the valid extension account reference.

| Metric | Mapped Silver | Customer 360 Gold |
|---|---:|---:|
| Transaction count | 23 | 23 |
| Total amount | 5436.00 | 5436.00 |

Unmapped Silver transactions: 0.

**Result: PASS**

The transaction counts and monetary totals agree between the mapped Silver records and Customer 360 Gold.

## 6. Rerun Safety Verification

**Test scenario:** Execute the Customer 360 build twice using unchanged source data.

Execution command:

```bash
python -m src.customer360.build_customer360
```

The first Gold CSV was saved as:

`customer_360_before_rerun.csv`

After running the build again, SHA-256 hashes were calculated for both files.

**Observed result:**

```text
Before:
1A0C139D5EE1A10D4F339CFB80A105E4FF0FB2C5708BD9E22D5FE1D3BCF736AC

After:
1A0C139D5EE1A10D4F339CFB80A105E4FF0FB2C5708BD9E22D5FE1D3BCF736AC

PASS: Customer 360 is identical after rerun.
```

**Result: PASS**

The identical hashes demonstrate that unchanged inputs produce a byte-for-byte identical Gold CSV.

The build also creates a database backup before rebuilding extension-owned records.

Exception audit IDs and timestamps may differ between runs; these are not part of the Gold business-result comparison.

## 7. API Integration Test Results

The API uses Python's built-in `http.server` library and exposes:

`GET /customers/<customer_id>/summary`

Server configuration:

```text
Host: 127.0.0.1
Port: 8765
```

Automated test command:

```bash
python -m pytest tests/customer360/test_api_server.py -v
```

**Actual pytest result:**

```text
6 passed in 0.75s
```

| Test scenario | Expected result | Actual result | Status |
|---|---|---|---|
| C001 — Maya Patel | HTTP 200 | HTTP 200 | PASS |
| C002 — Daniel Kim | HTTP 200 | HTTP 200 | PASS |
| C003 — Grace Lee | HTTP 200 | HTTP 200 | PASS |
| C999 — Unknown customer | HTTP 404 | HTTP 404 | PASS |
| POST request | HTTP 405 | HTTP 405 | PASS |
| SQL injection-like customer ID | HTTP 404 | HTTP 404 | PASS |

The automated tests also verify the returned JSON values for the three known customers and the required error JSON for C999.

**Result: 6/6 automated API tests passed.**

## 8. Privacy and Security Checks

The following controls are implemented and verified through code inspection and API tests:

- The API binds exclusively to `127.0.0.1`.
- SQLite connections use read-only mode.
- `PRAGMA query_only = ON` prevents database modifications through the API connection.
- Customer ID lookups use parameterized SQL.
- POST, PUT, PATCH and DELETE requests are rejected.
- The API exposes approved customer summary metrics rather than full transaction histories.
- Email addresses are excluded from the Customer 360 Gold output and API response.

Authentication, authorization, production audit logging, consent management and rate limiting are not implemented. These remain production requirements.

## 9. Known Limitations and Remaining Tests

The following scenarios require additional deliberate testing or documentation:

1. Separate fixtures for missing essential customer and account fields.
2. Duplicate customer ID and duplicate account ID input scenarios.
3. A dedicated extension-level duplicate transaction fixture with independent exception verification.
4. Operational recovery after a failed build or export.
5. Production authentication, authorization, privacy and rate-limiting controls.

The current results demonstrate the successful build, observed reference-data rejection, independent reconciliation, rerun safety and API integration tests. They do not claim that every possible data-quality or production failure scenario has been exercised.

## 10. Overall Test Summary

| Component | Result |
|---|---|
| Customer reference loading | PASS |
| Account reference loading | PASS |
| Customer 360 Gold generation | PASS |
| Zero-transaction customer handling | PASS |
| Observed orphan-account handling | PASS |
| Independent Silver–Gold reconciliation | PASS |
| Gold rerun safety | PASS |
| API integration tests | 6/6 PASS |
| Remaining edge-case and recovery tests | Pending |

**Conclusion:** The Week 8 CDP Readiness Extension successfully builds a customer-level Gold data product from the existing banking capstone Silver data and exposes approved customer summaries through a read-only local HTTP API. The implemented build and API tests passed their recorded verification scenarios. Additional edge-case testing and operational documentation remain necessary before the extension can be considered fully demonstrated.