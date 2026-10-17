# Airflow and Dagster: a short conceptual comparison

This is a conceptual comparison. Airflow was not installed or run for this assignment, so the Airflow column describes the general idea and was not tested. The Dagster column describes what was built in `orchestration/banking_job.py`.

| Concept | Airflow (conceptual) | Dagster (this project) |
|---|---|---|
| DAG / job | A DAG is a set of tasks with dependencies between them, defined in Python. | A job (`banking_job`) is the unit that is launched. Its steps and dependencies come from the function body: `publish(transform(validate(extract())))`. |
| Task / op | A task is one unit of work, usually created from an operator. | An op is one unit of work (`extract`, `validate`, `transform`, `publish`). Each is a thin wrapper over existing functions in `src/spark/`. The data passed between ops (small dicts) is what creates the dependencies. |
| Scheduler / daemon | A scheduler process decides when DAG runs start. | `banking_job_schedule` (cron `0 6 * * *`, UTC) is defined in code, and the Dagster daemon, started by `dagster dev`, evaluates schedules. The schedule was never enabled here ("Schedule has never run"), so automatic triggering was not tested. |
| Retries | Retries are set per task, with a number of retries and a delay. | `RetryPolicy(max_retries=2, delay=1)` is set on `extract` only. Scenario E (run `173160f1`) used a simulated failure (`fail_first_attempts: 1`): attempt 1 failed, a retry was scheduled after 1 second, and attempt 2 succeeded. `validate` has no retry, because a data-quality failure gives the same result each time. |
| Monitoring | A web UI shows DAG runs and task status, and the logs of each task. | The Dagster UI at http://localhost:3000 shows each run, its steps, their status and durations, and the event log. The `context.log` lines (start, end, status, row counts) appear there. Compute-log capture is disabled on Windows. |
| Backfills | A backfill runs a DAG for past dates. | Dagster backfills work over partitions. No partitions or backfills were used in this project, so a backfill was not tested. |

## Main differences as seen in this project

- **How dependencies are written.** In Dagster the dependencies come from passing one op's output to the next, so the order is not written separately from the data flow.
- **What the failure stopped.** The failed `validate` step prevented `transform` and `publish` from starting (scenario B, run `85c3ad91`).
- **What Dagster stores.** Dagster keeps its run history and step outputs under `DAGSTER_HOME`. This is separate from the business data, and a growing history does not mean the banking data changed.
