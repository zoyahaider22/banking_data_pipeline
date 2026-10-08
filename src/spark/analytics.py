from pyspark.sql import functions as F

from src.spark.load_data import get_spark, load_accounts, load_transactions
from src.spark.transformations import add_signed_amount, prepare_transactions


def get_transactions(spark):
    return add_signed_amount(prepare_transactions(load_transactions(spark)))


def summary_by_type(tx):
    return (
        tx.groupBy("transaction_type")
        .agg(
            F.count("*").alias("transaction_count"),
            F.sum("amount").alias("total_amount"),
            F.round(F.avg("amount"), 2).alias("avg_amount"),
        )
        .orderBy("transaction_type")
    )


def summary_by_account(tx):
    return (
        tx.groupBy("account_id")
        .agg(
            F.count("*").alias("transaction_count"),
            F.sum("amount").alias("gross_amount"),
            F.sum("signed_amount").alias("net_cash_flow"),
        )
        .orderBy("account_id")
    )


def summary_by_branch(tx, accounts):
    return (
        tx.join(accounts.select("account_id", "branch_id"), on="account_id", how="inner")
        .groupBy("branch_id")
        .agg(
            F.count("*").alias("transaction_count"),
            F.sum("amount").alias("gross_amount"),
            F.sum("signed_amount").alias("net_cash_flow"),
        )
        .orderBy("branch_id")
    )


if __name__ == "__main__":
    spark = get_spark("Aggregations")
    tx = get_transactions(spark)

    print("=== By transaction type ===")
    summary_by_type(tx).show()

    print("=== By account ===")
    summary_by_account(tx).show()

    print("=== By branch ===")
    summary_by_branch(tx, load_accounts(spark)).show()

    spark.stop()