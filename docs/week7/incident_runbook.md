# Incident and Runbook Note: banking_job validation failure

Applies to the Week 7 Dagster job `banking_job` (extract -> validate -> transform -> publish). It covers runs launched manually from the Launchpad. The schedule was never enabled, so scheduled runs were not exercised.

## Symptom

A run of `banking_job` ends with status Failure. The `validate` step is red, `transform` and `publish` are not started, and `branch_summary.csv` is not written or updated.

## Detection

1. Open http://localhost:3000, go to Runs and open the failed run.
2. Open the event log of the `validate` step. The failed line has the form `validate: end, status=FAILED, N data quality check(s) failed - <check name>: <count>`. The PASS and FAIL lines above it show every check.
3. Confirm that `publish` shows as not started. Measured in scenario B (run `85c3ad91`): `1 data quality check(s) failed - Transactions referencing nonexistent accounts: 1`, and the report folder was never created.

## Likely cause

The check named in the log found bad records in the source data. In scenario B this was one transaction (T9999) that pointed to an account (A9999) that does not exist. The log gives the check and the count, but not which records are bad: that has to be looked up in the data. A failed `extract` step is a different case, for example the database file cannot be read. It is retried up to 2 times, 1 second apart, and the error is then in Dagster's event log, not in a `status=FAILED` line. A real `extract` failure was not tested.

## Recovery

1. Do not edit `database/banking.db` to make the job pass. Find the bad records for the failed check (for the orphan check, transactions whose `account_id` has no row in `account`).
2. Correct the source data through the normal pipeline, or remove the bad rows from the copy used for testing. In scenario C (run `05b1a1fb`) the orphan transaction was deleted from the copy, the copy then had 20 rows and 0 orphans.
3. Launch the job again with the same config. Scenario C succeeded in 3m32s with the same report numbers as the first successful run.

## Safe rerun

Rerunning on unchanged source data is safe. The job reads `banking.db` read-only and `publish` overwrites one report file, so a rerun cannot add rows or create a second report. Scenario D (run `4c56e671`) measured 20 source rows and 20 distinct transaction IDs before and after, report rows 3, transaction count 20, net cash flow 3384.5, and an identical report SHA-256 (`457a405dcc3cb50a2f97668d7c6c12f78535f6147016148b54417851cd2349bf`). Dagster's run history grows with every run. That is Dagster's own record, not the business data.

## Escalation and limitation

- Escalate to the data owner when a check keeps failing after the source data was corrected, or when the bad records cannot be explained.
- The schedule `banking_job_schedule` (cron `0 6 * * *`, execution time zone UTC) is defined with default status STOPPED and was never enabled. Automatic triggering was not tested, and this note covers manually launched runs only.
- The retry in scenario E was simulated with the `fail_first_attempts` config value, not caused by a real fault.
- Only `validate` writes its own `status=FAILED` line. A failure in another step shows only in Dagster's event log.
- The Spark steps are slow (scenario A: extract 1m30s, validate 3m28s, transform 38s). The cause was not determined, so a long run is not by itself a failure.
- Dagster's compute logs are not captured on Windows. The `context.log` lines still appear in the UI event log.
