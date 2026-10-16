from dagster import (
    Config,
    DefaultScheduleStatus,
    Definitions,
    RetryPolicy,
    ScheduleDefinition,
    in_process_executor,
    job,
    op,
)

from src.spark.analytics import get_transactions, summary_by_branch
from src.spark.data_quality import run_checks
from src.spark.load_data import (
    BANKING_DB,
    get_spark,
    load_accounts,
    load_branches,
    load_customers,
    load_transactions,
)
from src.spark.reporting import (
    REPORT_DIR,
    DataQualityError,
    raise_if_checks_failed,
    summary_to_rows,
    write_branch_report,
)


class ExtractConfig(Config):
    db_path: str = str(BANKING_DB)
    fail_first_attempts: int = 0


class PublishConfig(Config):
    output_dir: str = str(REPORT_DIR)


@op(retry_policy=RetryPolicy(max_retries=2, delay=1))
def extract(context, config: ExtractConfig) -> dict:
    context.log.info("extract: start")
    if context.retry_number < config.fail_first_attempts:
        raise RuntimeError(f"Simulated transient failure on attempt {context.retry_number + 1}")
    spark = get_spark("BankingOrchestration")
    counts = {
        "transactions": load_transactions(spark, config.db_path).count(),
        "accounts": load_accounts(spark, config.db_path).count(),
    }
    context.log.info(f"extract: end, status=OK, rows={counts}")
    return {"db_path": config.db_path, **counts}


@op
def validate(context, extracted: dict) -> dict:
    context.log.info("validate: start")
    spark = get_spark("BankingOrchestration")
    db_path = extracted["db_path"]
    results = run_checks(
        load_transactions(spark, db_path),
        load_accounts(spark, db_path),
        load_customers(spark, db_path),
        load_branches(spark, db_path),
    )
    for name, bad in results:
        context.log.info(f"validate: {'PASS' if bad == 0 else 'FAIL'} {name}: {bad}")
    try:
        raise_if_checks_failed(results)
    except DataQualityError as error:
        context.log.error(f"validate: end, status=FAILED, {error}")
        raise
    context.log.info(f"validate: end, status=OK, {len(results)} checks passed")
    return {"db_path": db_path}


@op
def transform(context, validated: dict) -> dict:
    context.log.info("transform: start")
    spark = get_spark("BankingOrchestration")
    db_path = validated["db_path"]
    summary = summary_by_branch(get_transactions(spark, db_path), load_accounts(spark, db_path))
    rows = summary_to_rows(summary)
    context.log.info(f"transform: end, status=OK, branch rows={len(rows)}")
    return {"rows": rows}


@op
def publish(context, config: PublishConfig, transformed: dict) -> dict:
    context.log.info("publish: start")
    info = write_branch_report(transformed["rows"], config.output_dir)
    context.log.info(f"publish: end, status=OK, {info}")
    return info


@job(executor_def=in_process_executor)
def banking_job():
    publish(transform(validate(extract())))


daily_banking_schedule = ScheduleDefinition(
    job=banking_job,
    cron_schedule="0 6 * * *",
    default_status=DefaultScheduleStatus.STOPPED,
)

defs = Definitions(jobs=[banking_job], schedules=[daily_banking_schedule])
