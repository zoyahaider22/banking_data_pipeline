from pyspark.sql import functions as F
from pyspark.sql.types import (
    DateType,
    DoubleType,
    StringType,
    StructField,
    StructType,
)

from src.spark.generate_transactions import OUTPUT_PATH
from src.spark.load_data import get_spark, load_accounts
from src.spark.transformations import add_signed_amount, high_value_transactions

SCHEMA = StructType([
    StructField("transaction_id", StringType()),
    StructField("account_id", StringType()),
    StructField("transaction_date", DateType()),
    StructField("transaction_type", StringType()),
    StructField("amount", DoubleType()),
    StructField("currency", StringType()),
])


def load_generated(spark, path=OUTPUT_PATH):
    return spark.read.csv(str(path), header=True, schema=SCHEMA)


def summary_by_type(df):
    return (
        df.groupBy("transaction_type")
        .agg(
            F.count("*").alias("transaction_count"),
            F.round(F.sum("amount"), 2).alias("total_amount"),
            F.round(F.avg("amount"), 2).alias("avg_amount"),
        )
        .orderBy("transaction_type")
    )


def branch_activity(df, accounts):
    return (
        add_signed_amount(df)
        .join(accounts.select("account_id", "branch_id"), on="account_id", how="inner")
        .groupBy("branch_id")
        .agg(
            F.count("*").alias("transaction_count"),
            F.round(F.sum("amount"), 2).alias("gross_amount"),
            F.round(F.sum("signed_amount"), 2).alias("net_cash_flow"),
        )
        .orderBy("branch_id")
    )


if __name__ == "__main__":
    spark = get_spark("LargeDataAnalysis")

    df = load_generated(spark)
    print("Rows loaded:", df.count())
    df.printSchema()

    print("High value (>= 500.0):", high_value_transactions(df).count())

    print("=== By transaction type ===")
    summary_by_type(df).show()

    branches = branch_activity(df, load_accounts(spark))
    print("=== By branch (join to account) ===")
    branches.show()
    print("Branch counts add up to:",
          branches.agg(F.sum("transaction_count")).first()[0])

    spark.stop()