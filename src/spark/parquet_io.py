import shutil
from pathlib import Path

from src.spark.analytics import get_transactions
from src.spark.joins import activity_by_branch, build_joined
from src.spark.load_data import (
    get_spark,
    load_accounts,
    load_branches,
    load_customers,
)

ROOT = Path(__file__).resolve().parents[2]
PARQUET_PATH = ROOT / "output" / "spark" / "parquet" / "branch_activity"


def write_parquet(df, path=PARQUET_PATH):
    if Path(path).exists():
        shutil.rmtree(path)
    df.write.parquet(str(path))


def read_parquet(spark, path=PARQUET_PATH):
    return spark.read.parquet(str(path))


if __name__ == "__main__":
    spark = get_spark("ParquetIO")

    joined = build_joined(
        get_transactions(spark),
        load_accounts(spark),
        load_customers(spark),
        load_branches(spark),
    )
    branch_activity = activity_by_branch(joined)
    expected = branch_activity.count()
    print("Rows to write:", expected)

    try:
        write_parquet(branch_activity)
    except Exception as error:
        print("PARQUET WRITE FAILED")
        print("\n".join(str(error).splitlines()[:2]))
        print("Read-back skipped: nothing was written.")
    else:
        print("Parquet written to:", PARQUET_PATH)
        read_back = read_parquet(spark)
        actual = read_back.count()
        read_back.show(truncate=False)
        print("Rows read back:", actual)
        print("Row counts match:", actual == expected)

    spark.stop()