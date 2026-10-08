import os
import subprocess
import sys

os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

import pyspark
from pyspark.sql import SparkSession

java_info = subprocess.run(
    ["java", "-version"], capture_output=True, text=True
).stderr.splitlines()[0]

print("Python  :", sys.version.split()[0])
print("Java    :", java_info)
print("PySpark :", pyspark.__version__)

spark = (
    SparkSession.builder
    .appName("EnvironmentCheck")
    .master("local[*]")
    .getOrCreate()
)

print("Spark   :", spark.version)

df = spark.createDataFrame(
    [("T001", "CREDIT", 500.0), ("T002", "DEBIT", 100.0)],
    ["transaction_id", "transaction_type", "amount"],
)
df.show()
print("Row count:", df.count())

spark.stop()