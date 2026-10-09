from src.spark.analytics import get_transactions, summary_by_branch
from src.spark.load_data import get_spark, load_accounts, load_transactions
from src.spark.transformations import prepare_transactions

BRANCH_SQL = """
SELECT
    a.branch_id,
    COUNT(*)      AS transaction_count,
    SUM(t.amount) AS gross_amount,
    SUM(CASE WHEN t.transaction_type = 'CREDIT' THEN t.amount ELSE -t.amount END)
                  AS net_cash_flow
FROM transactions t
JOIN accounts a
  ON t.account_id = a.account_id
GROUP BY a.branch_id
ORDER BY a.branch_id
"""


def register_views(spark):
    prepare_transactions(load_transactions(spark)).createOrReplaceTempView("transactions")
    load_accounts(spark).createOrReplaceTempView("accounts")


def branch_activity_sql(spark):
    return spark.sql(BRANCH_SQL)


if __name__ == "__main__":
    spark = get_spark("SparkSQLComparison")

    register_views(spark)

    df_result = summary_by_branch(get_transactions(spark), load_accounts(spark))
    sql_result = branch_activity_sql(spark)

    print("=== DataFrame API version (summary_by_branch) ===")
    df_result.show()

    print("=== Spark SQL version (spark.sql) ===")
    print(BRANCH_SQL)
    sql_result.show()

    differences = (
        df_result.exceptAll(sql_result).count()
        + sql_result.exceptAll(df_result).count()
    )
    print("Rows that differ between the two versions:", differences)

    spark.stop()