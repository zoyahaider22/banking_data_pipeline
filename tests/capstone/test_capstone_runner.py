"""
Tests for the capstone runner (src/capstone/pipeline.py::run_pipeline).

A module-level fixture runs the pipeline four times on a small hand-made
dataset in a temporary folder: first run, same inputs again, a malformed file,
then the fixed file. Each test checks one aspect of the recorded results.
Expected values were calculated by hand. No mocks are used.
"""

import sqlite3

import pytest

from src.capstone.pipeline import run_pipeline

HEADER = "transaction_id,account_id,transaction_date,transaction_type,amount,currency\n"
ACCOUNTS = {"A1"}
F1 = "BR001_20260906_TRANSACTION.csv"
F2 = "BR002_20260906_TRANSACTION.csv"
F3 = "BR003_20260907_TRANSACTION.csv"
GOLD_HEADER = "branch_id,transaction_date,transaction_type,transaction_count,total_amount"
GOLD_SQL = ("SELECT branch_id, transaction_date, transaction_type, transaction_count, total_amount "
            "FROM gold_branch_daily_summary ORDER BY 1, 2, 3")

GOLD_1 = [
    ("BR001", "2026-09-06", "CREDIT", 1, 100.5),
    ("BR001", "2026-09-06", "DEBIT", 1, 40.0),
    ("BR002", "2026-09-06", "CREDIT", 1, 10.0),
]
GOLD_4 = GOLD_1 + [("BR003", "2026-09-07", "CREDIT", 1, 25.0)]

REASON_1 = "files loaded=2, skipped_identical=0, unrecognized=1; accepted=3, rejected=1; gold_rows=3"
REASON_2 = "files loaded=0, skipped_identical=2, unrecognized=1; accepted=0, rejected=0; gold_rows=3"
REASON_4 = "files loaded=1, skipped_identical=2, unrecognized=1; accepted=1, rejected=0; gold_rows=4"


def line(tid, acc, date, ttype, amount):
    return tid + "," + acc + "," + date + "," + ttype + "," + amount + ",USD\n"


def q(db, sql):
    con = sqlite3.connect(db)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


@pytest.fixture(scope="module")
def history(tmp_path_factory):
    base = tmp_path_factory.mktemp("runner")
    landing = base / "landing"
    landing.mkdir()
    db = base / "test.db"
    csv_path = base / "gold.csv"

    (landing / F1).write_text(
        HEADER
        + line("T1", "A1", "2026-09-06", "CREDIT", "100.50")
        + line("T2", "A1", "2026-09-06", "DEBIT", "40.00")
        + line("T3", "A9", "2026-09-06", "CREDIT", "5.00"),
        encoding="utf-8", newline="")
    (landing / F2).write_text(HEADER + line("T4", "A1", "2026-09-06", "CREDIT", "10.00"),
                              encoding="utf-8", newline="")
    (landing / "notes.txt").write_text("not a branch file", encoding="utf-8")

    def run():
        result = run_pipeline(landing, db, csv_path, ACCOUNTS)
        return {
            "result": result,
            "gold": q(db, GOLD_SQL),
            "published": q(db, "SELECT DISTINCT published_run_id FROM gold_branch_daily_summary"),
            "csv": csv_path.read_bytes() if csv_path.exists() else None,
            "bronze": q(db, "SELECT COUNT(*) FROM bronze_transactions")[0][0],
            "silver": q(db, "SELECT COUNT(*) FROM silver_transactions")[0][0],
            "exceptions": q(db, "SELECT COUNT(*) FROM exceptions")[0][0],
        }

    h = {"db": db}
    h["run1"] = run()
    h["run2"] = run()
    (landing / F3).write_text("wrong,header\nx,y\n", encoding="utf-8", newline="")
    h["run3"] = run()
    (landing / F3).write_text(HEADER + line("T5", "A1", "2026-09-07", "CREDIT", "25.00"),
                              encoding="utf-8", newline="")
    h["run4"] = run()
    return h


def test_first_run_succeeds_with_hand_calculated_summary(history):
    r = history["run1"]
    assert r["result"]["status"] == "SUCCESS"
    assert r["result"]["reason"] == REASON_1
    assert r["gold"] == GOLD_1
    assert r["csv"].decode("utf-8").splitlines() == [
        GOLD_HEADER,
        "BR001,2026-09-06,CREDIT,1,100.5",
        "BR001,2026-09-06,DEBIT,1,40.0",
        "BR002,2026-09-06,CREDIT,1,10.0",
    ]


def test_first_run_layer_counts(history):
    r = history["run1"]
    assert (r["bronze"], r["silver"], r["exceptions"]) == (4, 3, 1)


def test_rerun_changes_no_business_result(history):
    r1, r2 = history["run1"], history["run2"]
    assert r2["result"]["status"] == "SUCCESS"
    assert r2["result"]["reason"] == REASON_2
    assert r2["gold"] == r1["gold"] == GOLD_1
    assert r2["csv"] == r1["csv"]
    assert (r2["bronze"], r2["silver"], r2["exceptions"]) == (r1["bronze"], r1["silver"], r1["exceptions"])


def test_rerun_gets_a_new_run_id_and_publishes_under_it(history):
    id1, id2 = history["run1"]["result"]["run_id"], history["run2"]["result"]["run_id"]
    assert id1 != id2
    assert history["run1"]["published"] == [(id1,)]
    assert history["run2"]["published"] == [(id2,)]


def test_failed_run_reports_the_failing_step(history):
    result = history["run3"]["result"]
    assert result["status"] == "FAILED"
    assert result["reason"].startswith(
        "ingest failed: ValueError: " + F3 + ": header does not match")


def test_failed_run_leaves_previous_gold_untouched(history):
    r2, r3 = history["run2"], history["run3"]
    assert r3["gold"] == r2["gold"]
    assert r3["published"] == r2["published"]
    assert r3["csv"] == r2["csv"]
    assert (r3["bronze"], r3["silver"], r3["exceptions"]) == (r2["bronze"], r2["silver"], r2["exceptions"])


def test_failed_run_is_recorded_in_run_audit(history):
    result = history["run3"]["result"]
    row = q(history["db"],
            "SELECT status, finished_at IS NOT NULL, status_reason FROM run_audit WHERE run_id = '"
            + result["run_id"] + "'")
    assert row == [("FAILED", 1, result["reason"])]


def test_recovery_after_fixing_the_file(history):
    r = history["run4"]
    assert r["result"]["status"] == "SUCCESS"
    assert r["result"]["reason"] == REASON_4
    assert r["gold"] == GOLD_4
    assert r["csv"].decode("utf-8").splitlines()[-1] == "BR003,2026-09-07,CREDIT,1,25.0"
    assert (r["bronze"], r["silver"], r["exceptions"]) == (5, 4, 1)


def test_run_history_keeps_the_failed_run(history):
    statuses = [r[0] for r in q(history["db"], "SELECT status FROM run_audit ORDER BY rowid")]
    assert statuses == ["SUCCESS", "SUCCESS", "FAILED", "SUCCESS"]


def test_missing_landing_folder_fails_at_discover(tmp_path):
    db = tmp_path / "test.db"
    csv_path = tmp_path / "gold.csv"
    result = run_pipeline(tmp_path / "does_not_exist", db, csv_path, ACCOUNTS)
    assert result["status"] == "FAILED"
    assert result["reason"].startswith("discover failed: FileNotFoundError")
    assert not csv_path.exists()
    assert q(db, "SELECT status FROM run_audit") == [("FAILED",)]
