from src.spark.large_data_analysis import load_generated, summary_by_type
from src.spark.load_data import get_spark, load_transactions
from src.spark.transformations import credit_transactions

if __name__ == "__main__":
    spark = get_spark("SparkConcepts")

    print("=== Partitions ===")
    bank_tx = load_transactions(spark)
    print("banking.db transactions (20 rows)  :", bank_tx.rdd.getNumPartitions())
    generated = load_generated(spark)
    print("generated CSV (100000 rows)        :", generated.rdd.getNumPartitions())
    by_type = summary_by_type(generated)
    print("generated, after groupBy (summary) :", by_type.rdd.getNumPartitions())

    print("\n=== Transformation (lazy, nothing runs yet) ===")
    credits = credit_transactions(generated)
    print("credit_transactions() -> filter() defined, result type:",
          type(credits).__name__)

    print("\n=== Action (runs the whole plan) ===")
    print("credits.count() ->", credits.count())

    print("\n=== Shuffle: physical plan of the groupBy ===")
    by_type.explain()

    spark.stop()