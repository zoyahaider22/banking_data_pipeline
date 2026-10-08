from pyspark.sql import functions as F

from src.spark.load_data import get_spark, load_transactions

HIGH_VALUE_THRESHOLD = 500.0


def prepare_transactions(df):
    return df.withColumn("transaction_date", F.to_date("transaction_date", "yyyy-MM-dd"))


def credit_transactions(df):
    return df.filter(F.col("transaction_type") == "CREDIT")


def high_value_transactions(df, threshold=HIGH_VALUE_THRESHOLD):
    return df.filter(F.col("amount") >= threshold)


def reporting_columns(df):
    return df.select(
        "transaction_id", "account_id", "transaction_date",
        "transaction_type", "amount",
    )


def add_signed_amount(df):
    return df.withColumn(
        "signed_amount",
        F.when(F.col("transaction_type") == "CREDIT", F.col("amount"))
         .otherwise(-F.col("amount")),
    )


if __name__ == "__main__":
    spark = get_spark("Transformations")

    tx = prepare_transactions(load_transactions(spark))
    credits = credit_transactions(tx)
    high_value = high_value_transactions(tx)

    tx.printSchema()
    print("Transactions           :", tx.count())
    print("CREDIT rows            :", credits.count())
    print(f"High value (>= {HIGH_VALUE_THRESHOLD}):", high_value.count())
    print("Gross amount           :", tx.agg(F.sum("amount")).first()[0])
    print("Net cash flow          :",
          add_signed_amount(tx).agg(F.sum("signed_amount")).first()[0])

    print("\nReporting columns + derived signed_amount:")
    add_signed_amount(reporting_columns(tx)).orderBy("transaction_id").show(30)

    spark.stop()