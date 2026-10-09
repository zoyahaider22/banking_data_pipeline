import pytest

from src.spark.analytics import summary_by_branch, summary_by_type
from src.spark.data_quality import (
    count_duplicate_ids,
    count_nulls,
    count_orphans,
    run_checks,
)
from src.spark.joins import build_joined
from src.spark.transformations import add_signed_amount


def test_type_aggregation_known_values(transactions):
    rows = {r["transaction_type"]: r for r in summary_by_type(transactions).collect()}
    assert rows["CREDIT"]["transaction_count"] == 11
    assert rows["CREDIT"]["total_amount"] == pytest.approx(4060.0)
    assert rows["DEBIT"]["transaction_count"] == 9
    assert rows["DEBIT"]["total_amount"] == pytest.approx(675.5)


def test_branch_aggregation_known_values(transactions, accounts):
    result = summary_by_branch(add_signed_amount(transactions), accounts).collect()
    rows = {r["branch_id"]: r for r in result}
    assert rows["BR001"]["transaction_count"] == 6
    assert rows["BR001"]["net_cash_flow"] == pytest.approx(529.5)
    assert rows["BR003"]["transaction_count"] == 8
    assert rows["BR003"]["gross_amount"] == pytest.approx(2450.0)
    assert sum(r["net_cash_flow"] for r in result) == pytest.approx(3384.5)


def test_no_duplicate_ids_in_real_data(transactions):
    assert count_duplicate_ids(transactions, "transaction_id") == 0


def test_duplicate_ids_are_detected(spark):
    df = spark.createDataFrame([("T1",), ("T1",), ("T2",)], "transaction_id string")
    assert count_duplicate_ids(df, "transaction_id") == 1


def test_no_nulls_in_real_data(transactions):
    for column in ("transaction_id", "account_id", "amount"):
        assert count_nulls(transactions, column) == 0


def test_nulls_are_detected(spark):
    df = spark.createDataFrame(
        [("T1", 10.0), (None, None)], "transaction_id string, amount double"
    )
    assert count_nulls(df, "transaction_id") == 1
    assert count_nulls(df, "amount") == 1


def test_join_keeps_every_transaction(transactions, accounts, customers, branches):
    joined = build_joined(transactions, accounts, customers, branches)
    assert joined.count() == transactions.count() == 20


def test_no_orphans_in_real_data(transactions, accounts, customers, branches):
    assert count_orphans(transactions, accounts, "account_id") == 0
    assert count_orphans(accounts, customers, "customer_id") == 0
    assert count_orphans(accounts, branches, "branch_id") == 0


def test_orphans_are_detected(spark, accounts):
    df = spark.createDataFrame(
        [("T1", "A1001"), ("T2", "A9999")], "transaction_id string, account_id string"
    )
    assert count_orphans(df, accounts, "account_id") == 1


def test_all_data_quality_checks_pass(transactions, accounts, customers, branches):
    results = run_checks(transactions, accounts, customers, branches)
    assert len(results) == 7
    assert all(bad_count == 0 for _, bad_count in results)