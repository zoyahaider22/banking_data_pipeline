"""
transform.py - the "transform" step: build Gold from accepted Silver rows only.

Gold = one row per branch_id + transaction_date + transaction_type with
transaction_count and total_amount.

The same aggregation is computed twice:
  - in SQLite (plain GROUP BY) - the SQL equivalent
  - in PySpark (groupBy + agg), reading Silver with the Week 7 load_table helper
Amounts are rounded to 2 decimals on both sides. If the two results differ the
step raises ValueError. This step writes nothing; publish does that.
"""

from src.capstone.db import DB_PATH
from src.spark.load_data import get_spark, load_table

SQL_GOLD = """
SELECT branch_id, transaction_date, transaction_type,
       COUNT(*) AS transaction_count,
       ROUND(SUM(amount), 2) AS total_amount
FROM silver_transactions
GROUP BY branch_id, transaction_date, transaction_type
ORDER BY branch_id, transaction_date, transaction_type
"""


def gold_with_sql(con):
    """Gold rows from SQLite as (branch_id, date, type, count, total)."""
    return [
        (b, d, t, int(c), round(float(s), 2))
        for b, d, t, c, s in con.execute(SQL_GOLD).fetchall()
    ]


def gold_with_pyspark(spark, db_path):
    """Gold rows from PySpark, in the same shape and order as gold_with_sql."""
    from pyspark.sql import functions as F

    silver = load_table(spark, "silver_transactions", db_path)
    gold = (
        silver.groupBy("branch_id", "transaction_date", "transaction_type")
        .agg(
            F.count("*").alias("transaction_count"),
            F.round(F.sum("amount"), 2).alias("total_amount"),
        )
        .orderBy("branch_id", "transaction_date", "transaction_type")
    )
    return [
        (r["branch_id"], r["transaction_date"], r["transaction_type"],
         int(r["transaction_count"]), round(float(r["total_amount"]), 2))
        for r in gold.collect()
    ]


def transform(con, db_path=DB_PATH, spark=None):
    """Return the verified Gold rows, or raise ValueError if PySpark and SQL differ."""
    sql_rows = gold_with_sql(con)
    if not sql_rows:
        # Silver is empty: nothing to aggregate (load_table cannot build a
        # DataFrame from zero rows, so Spark is skipped in this case).
        return []

    own_session = spark is None
    if own_session:
        spark = get_spark("CapstoneGold")
    try:
        spark_rows = gold_with_pyspark(spark, db_path)
    finally:
        if own_session:
            spark.stop()

    if spark_rows != sql_rows:
        raise ValueError(
            "PySpark and SQL Gold results differ: spark=" + repr(spark_rows)
            + " sql=" + repr(sql_rows)
        )
    return spark_rows
