"""
Tests for the capstone transform step (Gold).

Silver is built through the real discover -> ingest -> validate steps in a
temporary database; the expected Gold values were calculated by hand.
One test replaces the PySpark function with a stand-in (monkeypatch) only to
force the "results differ" error path; every other test uses the real
PySpark and SQL calculations with no mocks.
"""

import pytest

from src.capstone import transform as transform_module
from src.capstone.db import connect, start_run
from src.capstone.discover import discover
from src.capstone.ingest import ingest
from src.capstone.transform import gold_with_pyspark, gold_with_sql, transform
from src.capstone.validate import validate
from src.spark.load_data import get_spark

HEADER = "transaction_id,account_id,transaction_date,transaction_type,amount,currency\n"
ACCOUNTS = {"A1"}

EXPECTED_GOLD = [
    ("BR001", "2026-09-06", "CREDIT", 2, 300.75),
    ("BR001", "2026-09-06", "DEBIT", 1, 50.0),
    ("BR002", "2026-09-06", "CREDIT", 1, 10.0),
    ("BR002", "2026-09-07", "DEBIT", 2, 0.3),
]


def line(tid, acc, date, ttype, amount):
    return tid + "," + acc + "," + date + "," + ttype + "," + amount + ",USD\n"


@pytest.fixture(scope="module")
def spark():
    session = get_spark("CapstoneGoldTests")
    yield session
    session.stop()


@pytest.fixture
def silver_db(tmp_path):
    landing = tmp_path / "landing"
    landing.mkdir()
    (landing / "BR001_20260906_TRANSACTION.csv").write_text(
        HEADER
        + line("T1", "A1", "2026-09-06", "CREDIT", "100.50")
        + line("T2", "A1", "2026-09-06", "CREDIT", "200.25")
        + line("T3", "A1", "2026-09-06", "DEBIT", "50.00")
        + line("T4", "A9", "2026-09-06", "CREDIT", "999.00"),
        encoding="utf-8", newline="")
    (landing / "BR002_20260906_TRANSACTION.csv").write_text(
        HEADER
        + line("T5", "A1", "2026-09-06", "CREDIT", "10.00")
        + line("T6", "A1", "2026-09-07", "DEBIT", "0.10")
        + line("T7", "A1", "2026-09-07", "DEBIT", "0.20"),
        encoding="utf-8", newline="")
    db = tmp_path / "test.db"
    con = connect(db)
    run_id = start_run(con)
    ingest(con, run_id, discover(landing)[0])
    validate(con, run_id, ACCOUNTS)
    yield con, db
    con.close()


def test_silver_holds_only_the_accepted_rows(silver_db):
    con, db = silver_db
    ids = [r[0] for r in con.execute("SELECT transaction_id FROM silver_transactions ORDER BY transaction_id")]
    assert ids == ["T1", "T2", "T3", "T5", "T6", "T7"]


def test_sql_gold_matches_hand_calculated_values(silver_db):
    con, db = silver_db
    assert gold_with_sql(con) == EXPECTED_GOLD


def test_pyspark_gold_matches_hand_calculated_values(silver_db, spark):
    con, db = silver_db
    assert gold_with_pyspark(spark, db) == EXPECTED_GOLD


def test_transform_returns_verified_gold(silver_db, spark):
    con, db = silver_db
    assert transform(con, db, spark) == EXPECTED_GOLD


def test_rejected_rows_never_reach_gold(silver_db, spark):
    con, db = silver_db
    gold = transform(con, db, spark)
    assert sum(r[3] for r in gold) == 6
    assert sum(r[4] for r in gold) == pytest.approx(361.05)


def test_transform_raises_when_pyspark_and_sql_differ(silver_db, spark, monkeypatch):
    # forced disagreement: the PySpark function is replaced to exercise the error path only
    con, db = silver_db
    monkeypatch.setattr(transform_module, "gold_with_pyspark",
                        lambda spark_session, db_path: [("BR001", "2026-09-06", "CREDIT", 99, 1.0)])
    with pytest.raises(ValueError, match="PySpark and SQL Gold results differ"):
        transform(con, db, spark)


def test_transform_returns_empty_list_for_empty_silver(tmp_path):
    db = tmp_path / "test.db"
    con = connect(db)
    assert transform(con, db) == []
    con.close()
