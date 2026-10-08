from pyspark.sql import functions as F

from src.spark.load_data import (
    get_spark,
    load_accounts,
    load_branches,
    load_customers,
    load_transactions,
)


def count_nulls(df, column):
    return df.filter(F.col(column).isNull()).count()


def count_duplicate_ids(df, column):
    return df.groupBy(column).count().filter(F.col("count") > 1).count()


def count_orphans(child, parent, key):
    # Rows in child whose key has no match in parent (left anti join).
    # Null keys are skipped here because the null checks report them.
    return (
        child.filter(F.col(key).isNotNull())
        .join(parent.select(key).distinct(), on=key, how="left_anti")
        .count()
    )


def run_checks(transactions, accounts, customers, branches):
    return [
        ("Null transaction IDs", count_nulls(transactions, "transaction_id")),
        ("Null account IDs (transactions)", count_nulls(transactions, "account_id")),
        ("Null amounts", count_nulls(transactions, "amount")),
        ("Duplicate transaction IDs", count_duplicate_ids(transactions, "transaction_id")),
        ("Transactions referencing nonexistent accounts",
         count_orphans(transactions, accounts, "account_id")),
        ("Accounts referencing nonexistent customers",
         count_orphans(accounts, customers, "customer_id")),
        ("Accounts referencing nonexistent branches",
         count_orphans(accounts, branches, "branch_id")),
    ]


def print_report(results):
    print("=== Data quality checks ===")
    for name, bad in results:
        status = "PASS" if bad == 0 else "FAIL"
        print(f"{status}  {name}: {bad} bad record(s)")
    failed = sum(1 for _, bad in results if bad > 0)
    print(f"\n{len(results) - failed} of {len(results)} checks passed")


if __name__ == "__main__":
    spark = get_spark("DataQuality")

    results = run_checks(
        load_transactions(spark),
        load_accounts(spark),
        load_customers(spark),
        load_branches(spark),
    )
    print_report(results)

    spark.stop()