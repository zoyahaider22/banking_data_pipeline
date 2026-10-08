import os
import sqlite3
import sys
from pathlib import Path

os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

from pyspark.sql import SparkSession

ROOT = Path(__file__).resolve().parents[2]
BANKING_DB = ROOT / "database" / "banking.db"


def get_spark(app_name="BankingSpark"):
    spark = (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def load_table(spark, table, db_path=BANKING_DB):
    con = sqlite3.connect(f"{Path(db_path).as_uri()}?mode=ro", uri=True)
    try:
        cursor = con.execute(f"SELECT * FROM {table}")
        columns = [c[0] for c in cursor.description]
        rows = cursor.fetchall()
    finally:
        con.close()
    return spark.createDataFrame(rows, columns)


def load_customers(spark):
    return load_table(spark, "customer")


def load_accounts(spark):
    return load_table(spark, "account")


def load_branches(spark):
    return load_table(spark, "branch")


def load_transactions(spark):
    return load_table(spark, "bank_transaction")


if __name__ == "__main__":
    spark = get_spark("LoadAndInspect")
    frames = {
        "customers": load_customers(spark),
        "accounts": load_accounts(spark),
        "branches": load_branches(spark),
        "transactions": load_transactions(spark),
    }
    for name, df in frames.items():
        print(f"\n=== {name} ===")
        df.show(5, truncate=False)
        df.printSchema()
        print("Row count:", df.count())
    spark.stop()