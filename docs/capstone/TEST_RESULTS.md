# Test results - Week 8 integrated banking capstone

Run times in run IDs are UTC. Scenario runs used the real capstone database (`output\capstone\banking_capstone.db`) in this order: stage A, same inputs again, stage C files, stage D (malformed file), stage E (corrected file). Inputs other than the three original branch files are synthetic.

## 1. Scenarios on the real database

| # | Scenario | Result | Evidence |
|---|---|---|---|
| 1 | Normal multi-branch, multi-date input | PASS | `evidence\capstone\s1_stageA_pipeline_run.png` |
| 2 | Unknown account / invalid amount / bad date | PASS | `evidence\capstone\s1_s2_stageA_sql_check_part2.png` |
| 3 | Duplicate transaction / repeated file | PASS | `evidence\capstone\s6_rerun_same_inputs.png` |
| 4 | Late or corrected file | PASS | `evidence\capstone\s3_s4_stageC_sql_check.png` |
| 5 | Failed run / publish protection / recovery | PASS (ingest-step failure) | `evidence\capstone\s5_failed_run_protection.png` |
| 6 | Run same inputs twice | PASS | `evidence\capstone\s6_rerun_same_inputs.png` |

### Scenario 1 - normal multi-branch, multi-date input

- Expected (assignment): correct Silver counts and Gold totals, independently checked with SQL.
- Actual: stage A, run `RUN_20261024T113510_8937b7`, 6 files (BR001, BR002, BR003 for 2026-09-06 and 2026-09-07). Source rows 33 = accepted 19 + rejected 14. Per file (source/accepted/rejected): 8/3/5, 8/3/5, 8/4/4, 3/3/0, 3/3/0, 3/3/0. Gold has 12 rows. Gold count sum 19, Gold total 5056.0, and a separate SQL query on Silver gives 5056.0. The Silver ID set equals a hand-listed expected set, and the Gold rows match a hand calculation.
- Evidence: `evidence\capstone\s1_stageA_pipeline_run.png`, `evidence\capstone\s1_s2_stageA_sql_check_part1.png`, `evidence\capstone\s1_s2_stageA_sql_check_part2.png`

### Scenario 2 - unknown account, invalid amount, bad date

- Expected (assignment): row retained in Exceptions with reason; excluded from Gold.
- Actual: `T1006` (amount -50.00), `T1008` (date 2026/09/06), `T2002` (empty amount), `T2003` (amount 0.00) and `T3008` (date 2026-13-06) are in Exceptions. Each has the amount or date reason plus "account_id not found in accounts reference". None of these IDs is in Silver (count 0), so none is in Gold. Exceptions holds 14 rows after stage A.
- Evidence: `evidence\capstone\s1_s2_stageA_sql_check_part2.png`

### Scenario 3 - duplicate transaction / repeated file

- Expected (assignment): no duplicate business results; explicit duplicate evidence.
- Actual, repeated file: running the same six files again gave `skipped_identical=6, accepted=0, rejected=0`; Bronze 33 to 33, Silver 19 to 19, Exceptions 14 to 14.
- Actual, re-delivered IDs: after the stage C files, `T1001` (550.00) and `T7001` (120.00) from `BR001_20260908_TRANSACTION.csv` were rejected with "duplicate transaction_id already accepted (first accepted record wins)". The query for duplicate IDs in Silver returned an empty list. Bronze 38 = Silver 22 + Exceptions 16.
- Evidence: `evidence\capstone\s6_rerun_same_inputs.png`, `evidence\capstone\s3_s4_stageC_pipeline_run.png`, `evidence\capstone\s3_s4_stageC_sql_check.png`

### Scenario 4 - late or corrected file

- Expected (assignment): documented behavior and updated or intentionally unchanged results.
- Actual, correction (intentionally unchanged): `T1001` stays at 500.0 in Silver (from `BR001_20260906_TRANSACTION.csv`); the 550.00 re-delivery is kept in Exceptions. Policy: DESIGN_DECISIONS.md section 3.
- Actual, late row (updated): `T7104` arrives in `BR002_20260909_TRANSACTION.csv` with row date 2026-09-07 and is accepted. Gold row BR002 2026-09-07 CREDIT went from count 2 / total 360.0 to count 3 / total 425.0. Gold row BR001 2026-09-07 CREDIT stays at 2 / 395.0 because the duplicate `T7001` is not counted. After stage C: Gold 14 rows, Gold total 5226.0, Silver total 5226.0.
- Evidence: `evidence\capstone\s3_s4_stageC_pipeline_run.png`, `evidence\capstone\s3_s4_stageC_sql_check.png`

### Scenario 5 - failed run, publish protection, recovery

- Expected (assignment): failed run identified; prior trustworthy Gold output preserved; recovery without manually deleting all output.
- Actual, failure: `BR003_20260910_TRANSACTION.csv` with a wrong header. Run `RUN_20261025T071644_a68dc8` ended `FAILED` with reason "ingest failed: ValueError: BR003_20260910_TRANSACTION.csv: header does not match ...". Bronze, Silver and Exceptions stayed 38, 22, 16. Gold rows and the Gold CSV hash were identical to before, and the Gold `published_run_id` was still `RUN_20261024T151639_fc0f90`. `run_audit` went from 3 to 4 rows.
- Actual, recovery: the file was replaced with the corrected version and the pipeline rerun without deleting any output. Run `RUN_20261025T071858_18170d` ended `SUCCESS` (`files loaded=1, skipped_identical=8`). Gold went from 14 to 15 rows with the new row BR003 2026-09-10 CREDIT, count 1, total 210.0. Gold total 5436.0 = Silver total 5436.0. The `FAILED` run stays in `run_audit`.
- Scope: the failure demonstrated is at the ingest step. Failures at other steps are covered only by pytest (section 2), not on the real database.
- Evidence: `evidence\capstone\s5_failed_run_protection.png`, `evidence\capstone\s5_recovery_after_fix_part1.png`, `evidence\capstone\s5_recovery_after_fix_part2.png`

### Scenario 6 - run same inputs twice

- Expected (assignment): identical Gold business result; explain whether audit/run IDs differ.
- Actual: second run `RUN_20261024T151426_45b160` on the same six files: `skipped_identical=6`. Bronze 33 to 33, Silver 19 to 19, Exceptions 14 to 14; Gold business rows and the Gold CSV hash identical. Run IDs differ (`..._8937b7` and `..._45b160`), `run_audit` went from 1 to 2 rows, and the Gold `published_run_id` changed to the new run. So audit and run IDs differ while the business result is identical.
- Evidence: `evidence\capstone\s6_rerun_same_inputs.png`

## 2. Automated tests (pytest, `tests\capstone`)

Each test uses a temporary folder and database, with expected values calculated by hand. They do not touch the real capstone database.

| File | Tests | Result | Evidence |
|---|---|---|---|
| `test_capstone_validate_rules.py` | 18 | 18 passed in 3.87 s | `evidence\capstone\pytest_validate_rules.png` |
| `test_capstone_discover_ingest.py` | 18 | 18 passed in 0.93 s | `evidence\capstone\pytest_discover_ingest.png` |
| `test_capstone_validate_publish.py` | 13 | 13 passed in 3.00 s | `evidence\capstone\pytest_validate_publish.png` |
| `test_capstone_gold.py` | 7 | 7 passed, 1 warning in 40.49 s | `evidence\capstone\pytest_gold.png` |
| `test_capstone_runner.py` | 10 | 10 passed, 1 warning in 35.84 s | `evidence\capstone\pytest_runner.png` |
| all five files together | 66 | 66 passed, 1 warning in 58.08 s | `evidence\capstone\pytest_full_capstone_suite.png` |

- The warning is PySpark's pandas FutureWarning ("does not yet fully support pandas >= 3.0.0"). It is not a failure.
- One Gold test replaces the PySpark function with a stand-in only to force the "PySpark and SQL differ" error. All other tests use the real calculations with no mocks.
- The runner tests run the whole pipeline four times on a small hand-made dataset (first run, same inputs again, a malformed file, the fixed file).

## 3. Not covered by this evidence

- On the real database only an ingest-step failure was demonstrated. A reconciliation mismatch and a PySpark/SQL mismatch are tested only in pytest.
- Upsert is not implemented. A correction to an already accepted transaction is rejected as a duplicate by design.
- The pipeline does not count rows whose row date differs from the filename date. RUNBOOK.md section 5 query E lists them; the stage C check showed `T7104`.
- The scenarios depend on running in the order above on one database. They were run once each.
- Spark steps took between 14 and 47 seconds per run on this machine. The cause is undetermined.
- The orchestrator is the plain Python runner `src\capstone\pipeline.py`.
