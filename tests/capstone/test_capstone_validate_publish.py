"""
Tests for the capstone validate step (Bronze -> Silver / Exceptions) and publish.
Each test uses its own temporary database; expected values are written by hand.
"""

import sqlite3

import pytest

from src.capstone.db import connect, start_run
from src.capstone.discover import discover
from src.capstone.ingest import ingest
from src.capstone.publish import publish
from src.capstone.validate import validate

HEADER = "transaction_id,account_id,transaction_date,transaction_type,amount,currency\n"
ACCOUNTS = {"A1"}
F1 = "BR001_20260906_TRANSACTION.csv"
F2 = "BR002_20260906_TRANSACTION.csv"
F1_D7 = "BR001_20260907_TRANSACTION.csv"
F1_D8 = "BR001_20260908_TRANSACTION.csv"

UNKNOWN = "account_id not found in accounts reference"
AMOUNT = "amount must be present, numeric, and greater than 0"
DUP = "duplicate transaction_id already accepted (first accepted record wins)"

GOLD_HEADER = "branch_id,transaction_date,transaction_type,transaction_count,total_amount"


def line(tid, acc, date, ttype, amount):
    return tid + "," + acc + "," + date + "," + ttype + "," + amount + ",USD\n"


def write_file(folder, name, body):
    (folder / name).write_text(HEADER + body, encoding="utf-8", newline="")


def load(con, landing):
    run_id = start_run(con)
    ingest(con, run_id, discover(landing)[0])
    return run_id


def silver(con):
    return con.execute(
        "SELECT transaction_id, account_id, branch_id, transaction_date, transaction_type, "
        "amount, currency, source_filename, source_row_number "
        "FROM silver_transactions ORDER BY transaction_id"
    ).fetchall()


def exceptions(con):
    return con.execute(
        "SELECT source_filename, source_row_number, transaction_id, rejection_reasons "
        "FROM exceptions ORDER BY source_filename, source_row_number"
    ).fetchall()


@pytest.fixture
def env(tmp_path):
    landing = tmp_path / "landing"
    landing.mkdir()
    con = connect(tmp_path / "test.db")
    yield landing, con
    con.close()


def test_validate_accepts_and_rejects_with_reconciliation(env):
    landing, con = env
    write_file(landing, F1,
               line("T1", "A1", "2026-09-06", "CREDIT", "10.00")
               + line("T2", "A9", "2026-09-06", "CREDIT", "20.00")
               + line("T3", "A1", "2026-09-06", "CREDIT", ""))
    run_id = load(con, landing)
    result = validate(con, run_id, ACCOUNTS)
    assert result == [{"filename": F1, "source_rows": 3, "accepted_rows": 1, "rejected_rows": 2}]
    assert silver(con) == [("T1", "A1", "BR001", "2026-09-06", "CREDIT", 10.0, "USD", F1, 1)]
    assert exceptions(con) == [(F1, 2, "T2", UNKNOWN), (F1, 3, "T3", AMOUNT)]
    audit = con.execute("SELECT source_rows, accepted_rows, rejected_rows, file_status FROM file_audit").fetchall()
    assert audit == [(3, 1, 2, "PROCESSED")]


def test_duplicate_inside_one_file_first_row_wins(env):
    landing, con = env
    write_file(landing, F1,
               line("T1", "A1", "2026-09-06", "CREDIT", "10.00")
               + line("T1", "A1", "2026-09-06", "CREDIT", "99.00"))
    validate(con, load(con, landing), ACCOUNTS)
    assert [(r[0], r[5]) for r in silver(con)] == [("T1", 10.0)]
    assert exceptions(con) == [(F1, 2, "T1", DUP)]


def test_duplicate_across_runs_keeps_the_earlier_accepted_record(env):
    landing, con = env
    write_file(landing, F1, line("T1", "A1", "2026-09-06", "CREDIT", "10.00"))
    validate(con, load(con, landing), ACCOUNTS)
    write_file(landing, F1_D8,
               line("T1", "A1", "2026-09-06", "CREDIT", "99.00")
               + line("T2", "A1", "2026-09-08", "CREDIT", "5.00"))
    validate(con, load(con, landing), ACCOUNTS)
    assert [(r[0], r[5]) for r in silver(con)] == [("T1", 10.0), ("T2", 5.0)]
    assert exceptions(con) == [(F1_D8, 1, "T1", DUP)]


def test_earlier_file_date_wins_when_files_arrive_in_one_run(env):
    landing, con = env
    write_file(landing, F1_D7, line("T1", "A1", "2026-09-07", "CREDIT", "7.00"))
    write_file(landing, F2, line("T1", "A1", "2026-09-06", "CREDIT", "6.00"))
    validate(con, load(con, landing), ACCOUNTS)
    assert [(r[0], r[5], r[7]) for r in silver(con)] == [("T1", 6.0, F2)]
    assert exceptions(con) == [(F1_D7, 1, "T1", DUP)]


def test_lower_branch_id_wins_when_file_dates_are_equal(env):
    landing, con = env
    write_file(landing, F2, line("T1", "A1", "2026-09-06", "CREDIT", "6.00"))
    write_file(landing, F1, line("T1", "A1", "2026-09-06", "CREDIT", "7.00"))
    validate(con, load(con, landing), ACCOUNTS)
    assert [(r[0], r[5], r[7]) for r in silver(con)] == [("T1", 7.0, F1)]
    assert exceptions(con) == [(F2, 1, "T1", DUP)]


def test_repeated_id_that_was_never_accepted_is_not_a_duplicate(env):
    landing, con = env
    write_file(landing, F1, line("T5", "A9", "2026-09-06", "DEBIT", "75.00"))
    write_file(landing, F2, line("T5", "A9", "2026-09-06", "DEBIT", "75.00"))
    validate(con, load(con, landing), ACCOUNTS)
    assert silver(con) == []
    assert exceptions(con) == [(F1, 1, "T5", UNKNOWN), (F2, 1, "T5", UNKNOWN)]


def test_reconciliation_mismatch_raises_and_rolls_back(env):
    landing, con = env
    write_file(landing, F1,
               line("T1", "A1", "2026-09-06", "CREDIT", "10.00")
               + line("T2", "A1", "2026-09-06", "CREDIT", "20.00"))
    run_id = load(con, landing)
    con.execute("DELETE FROM bronze_transactions WHERE source_row_number = 2")
    con.commit()
    with pytest.raises(ValueError, match="reconciliation failed"):
        validate(con, run_id, ACCOUNTS)
    assert silver(con) == []
    assert exceptions(con) == []
    assert con.execute("SELECT file_status FROM file_audit").fetchall() == [("LOADED",)]


def test_only_files_loaded_in_the_current_run_are_validated(env):
    landing, con = env
    write_file(landing, F1, line("T1", "A1", "2026-09-06", "CREDIT", "10.00"))
    run1 = load(con, landing)
    run2 = load(con, landing)
    validate(con, run2, ACCOUNTS)
    assert [(r[0], r[5]) for r in silver(con)] == [("T1", 10.0)]
    assert con.execute("SELECT run_id FROM silver_transactions").fetchall() == [(run2,)]
    statuses = con.execute("SELECT run_id, file_status FROM file_audit ORDER BY rowid").fetchall()
    assert statuses == [(run1, "LOADED"), (run2, "PROCESSED")]


def test_validate_returns_empty_when_nothing_was_loaded(env):
    landing, con = env
    assert validate(con, start_run(con), ACCOUNTS) == []


def gold_table(con):
    return con.execute(
        "SELECT branch_id, transaction_date, transaction_type, transaction_count, total_amount "
        "FROM gold_branch_daily_summary ORDER BY branch_id, transaction_date, transaction_type"
    ).fetchall()


def test_publish_writes_table_and_csv(tmp_path):
    con = connect(tmp_path / "test.db")
    csv_path = tmp_path / "gold.csv"
    rows = [("BR001", "2026-09-06", "CREDIT", 1, 500.0), ("BR002", "2026-09-06", "DEBIT", 1, 60.0)]
    assert publish(con, "RUN_TEST_1", rows, csv_path) == 2
    assert gold_table(con) == rows
    assert con.execute("SELECT DISTINCT published_run_id FROM gold_branch_daily_summary").fetchall() == [("RUN_TEST_1",)]
    assert csv_path.read_text(encoding="utf-8").splitlines() == [
        GOLD_HEADER, "BR001,2026-09-06,CREDIT,1,500.0", "BR002,2026-09-06,DEBIT,1,60.0"]
    con.close()


def test_publish_replaces_the_previous_rows(tmp_path):
    con = connect(tmp_path / "test.db")
    csv_path = tmp_path / "gold.csv"
    publish(con, "RUN_TEST_1", [("BR001", "2026-09-06", "CREDIT", 1, 500.0)], csv_path)
    publish(con, "RUN_TEST_2", [("BR003", "2026-09-07", "CREDIT", 2, 90.0)], csv_path)
    assert gold_table(con) == [("BR003", "2026-09-07", "CREDIT", 2, 90.0)]
    assert csv_path.read_text(encoding="utf-8").splitlines() == [GOLD_HEADER, "BR003,2026-09-07,CREDIT,2,90.0"]
    con.close()


def test_failed_publish_keeps_previous_table_and_csv(tmp_path):
    con = connect(tmp_path / "test.db")
    csv_path = tmp_path / "gold.csv"
    publish(con, "RUN_TEST_1", [("BR001", "2026-09-06", "CREDIT", 1, 500.0)], csv_path)
    table_before = gold_table(con)
    csv_before = csv_path.read_bytes()
    with pytest.raises(sqlite3.IntegrityError):
        publish(con, "RUN_TEST_2", [("BR009", "2026-09-06", "CREDIT", 1, None)], csv_path)
    assert gold_table(con) == table_before
    assert csv_path.read_bytes() == csv_before
    assert not (tmp_path / "gold.csv.tmp").exists()
    con.close()


def test_publishing_empty_gold_replaces_the_old_gold(tmp_path):
    con = connect(tmp_path / "test.db")
    csv_path = tmp_path / "gold.csv"
    publish(con, "RUN_TEST_1", [("BR001", "2026-09-06", "CREDIT", 1, 500.0)], csv_path)
    assert publish(con, "RUN_TEST_2", [], csv_path) == 0
    assert gold_table(con) == []
    assert csv_path.read_text(encoding="utf-8").splitlines() == [GOLD_HEADER]
    con.close()
