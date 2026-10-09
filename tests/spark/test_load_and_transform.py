import pytest
from pyspark.sql import functions as F

from src.spark.transformations import (
    add_signed_amount,
    credit_transactions,
    high_value_transactions,
    reporting_columns,
)


def test_input_row_counts(transactions, accounts, customers, branches):
    assert transactions.count() == 20
    assert accounts.count() == 10
    assert customers.count() == 6
    assert branches.count() == 3


def test_credit_count(transactions):
    assert credit_transactions(transactions).count() == 11


def test_credit_dataset_only_contains_credit(transactions):
    types = credit_transactions(transactions).select("transaction_type").distinct().collect()
    assert [row[0] for row in types] == ["CREDIT"]


def test_high_value_threshold(transactions):
    high = high_value_transactions(transactions)
    assert high.count() == 3
    assert high.agg(F.min("amount")).first()[0] >= 500.0


def test_week5_corrections_are_present(transactions):
    rows = transactions.filter(F.col("transaction_id").isin("T1001", "T4002")).collect()
    assert {row["transaction_id"]: row["amount"] for row in rows} == {
        "T1001": 550.0,
        "T4002": 55.0,
    }


def test_reporting_columns(transactions):
    assert reporting_columns(transactions).columns == [
        "transaction_id", "account_id", "transaction_date",
        "transaction_type", "amount",
    ]


def test_signed_amount_totals(transactions):
    totals = add_signed_amount(transactions).agg(
        F.sum("amount").alias("gross"),
        F.sum("signed_amount").alias("net"),
    ).first()
    assert totals["gross"] == pytest.approx(4735.5)
    assert totals["net"] == pytest.approx(3384.5)