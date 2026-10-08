from pyspark.sql import functions as F

from src.spark.analytics import get_transactions
from src.spark.load_data import (
    get_spark,
    load_accounts,
    load_branches,
    load_customers,
)

# Join relationships (all many-to-one, so row count stays 20):
#   bank_transaction.account_id -> account.account_id
#   account.customer_id         -> customer.customer_id
#   account.branch_id           -> branch.branch_id


def build_joined(tx, accounts, customers, branches):
    return (
        tx.join(accounts, on="account_id", how="inner")
        .join(customers, on="customer_id", how="inner")
        .join(branches, on="branch_id", how="inner")
    )


def _summarise(joined, group_cols):
    return (
        joined.groupBy(*group_cols)
        .agg(
            F.count("*").alias("transaction_count"),
            F.sum("amount").alias("gross_amount"),
            F.sum("signed_amount").alias("net_cash_flow"),
        )
        .orderBy(*group_cols)
    )


def activity_by_customer(joined):
    return _summarise(joined, ["customer_id", "customer_name", "customer_segment"])


def activity_by_branch(joined):
    return _summarise(joined, ["branch_id", "branch_name", "city"])


def activity_by_account_type(joined):
    return _summarise(joined, ["account_type"])


if __name__ == "__main__":
    spark = get_spark("Joins")

    joined = build_joined(
        get_transactions(spark),
        load_accounts(spark),
        load_customers(spark),
        load_branches(spark),
    )

    print("Joined rows:", joined.count())
    joined.printSchema()

    print("=== Activity by customer ===")
    activity_by_customer(joined).show(truncate=False)

    print("=== Activity by branch ===")
    activity_by_branch(joined).show(truncate=False)

    print("=== Activity by account type ===")
    activity_by_account_type(joined).show(truncate=False)

    spark.stop()