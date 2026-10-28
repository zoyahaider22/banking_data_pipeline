"""
Tests for the capstone discover and ingest steps.
Each ingest test uses its own temporary database; expected values are written by hand.
"""

import pytest

from src.capstone.db import connect, start_run
from src.capstone.discover import discover, parse_filename
from src.capstone.ingest import ingest, read_source_rows

HEADER = "transaction_id,account_id,transaction_date,transaction_type,amount,currency\n"
NAME = "BR001_20260906_TRANSACTION.csv"
NO_MATCH = "filename does not match BR<digits>_<YYYYMMDD>_TRANSACTION.csv"
BAD_DATE = "filename date is not a real calendar date"


def write_file(folder, name, body, header=HEADER):
    path = folder / name
    path.write_text(header + body, encoding="utf-8", newline="")
    return path


def bronze_count(con):
    return con.execute("SELECT COUNT(*) FROM bronze_transactions").fetchone()[0]


def mark_processed(con, run_id):
    # stands in for the validate step, which sets PROCESSED in the real pipeline
    con.execute("UPDATE file_audit SET file_status = 'PROCESSED' WHERE run_id = ?", (run_id,))
    con.commit()


@pytest.fixture
def env(tmp_path):
    landing = tmp_path / "landing"
    landing.mkdir()
    con = connect(tmp_path / "test.db")
    yield landing, con
    con.close()


@pytest.mark.parametrize("name, expected", [
    ("BR001_20260906_TRANSACTION.csv", ("BR001", "2026-09-06", None)),
    ("BR12_20260101_TRANSACTION.csv", ("BR12", "2026-01-01", None)),
    ("BR001_20261301_TRANSACTION.csv", (None, None, BAD_DATE)),
    ("transactions_20260907.csv", (None, None, NO_MATCH)),
    ("BRabc_20260906_TRANSACTION.csv", (None, None, NO_MATCH)),
])
def test_parse_filename(name, expected):
    assert parse_filename(name) == expected


def test_discover_orders_files_and_lists_unrecognized(tmp_path):
    landing = tmp_path / "landing"
    landing.mkdir()
    for name in ["BR002_20260907_TRANSACTION.csv", "BR001_20260907_TRANSACTION.csv",
                 "BR001_20260906_TRANSACTION.csv", "notes.txt", "transactions_20260907.csv"]:
        write_file(landing, name, "")
    (landing / "subfolder").mkdir()
    recognized, unrecognized = discover(landing)
    assert [r["filename"] for r in recognized] == [
        "BR001_20260906_TRANSACTION.csv",
        "BR001_20260907_TRANSACTION.csv",
        "BR002_20260907_TRANSACTION.csv",
    ]
    assert [u["filename"] for u in unrecognized] == ["notes.txt", "transactions_20260907.csv"]


def test_discover_hash_follows_content(tmp_path):
    landing = tmp_path / "landing"
    landing.mkdir()
    write_file(landing, "BR001_20260906_TRANSACTION.csv", "T1,A1,2026-09-06,CREDIT,1.00,USD\n")
    write_file(landing, "BR002_20260906_TRANSACTION.csv", "T1,A1,2026-09-06,CREDIT,1.00,USD\n")
    write_file(landing, "BR003_20260906_TRANSACTION.csv", "T2,A1,2026-09-06,CREDIT,1.00,USD\n")
    by_name = {r["filename"]: r["sha256"] for r in discover(landing)[0]}
    assert by_name["BR001_20260906_TRANSACTION.csv"] == by_name["BR002_20260906_TRANSACTION.csv"]
    assert by_name["BR001_20260906_TRANSACTION.csv"] != by_name["BR003_20260906_TRANSACTION.csv"]


def test_ingest_keeps_raw_values_as_received(env):
    landing, con = env
    write_file(landing, NAME, "T1,A1,2026-09-06,CREDIT,100.00,USD\nT2,A2,2026-09-06,DEBIT,,USD\nT3,A3,2026-09-06,CREDIT,5,USD\n")
    results = ingest(con, start_run(con), discover(landing)[0])
    rows = con.execute("SELECT source_row_number, transaction_id, amount FROM bronze_transactions ORDER BY source_row_number").fetchall()
    assert rows == [(1, "T1", "100.00"), (2, "T2", ""), (3, "T3", "5")]
    assert results == [{"filename": NAME, "status": "LOADED", "source_rows": 3}]


def test_ingest_skips_blank_lines_in_row_numbering(env):
    landing, con = env
    write_file(landing, NAME, "T1,A1,2026-09-06,CREDIT,1.00,USD\n\nT2,A2,2026-09-06,DEBIT,2.00,USD\n")
    ingest(con, start_run(con), discover(landing)[0])
    rows = con.execute("SELECT source_row_number, transaction_id FROM bronze_transactions ORDER BY source_row_number").fetchall()
    assert rows == [(1, "T1"), (2, "T2")]


def test_ingest_stores_source_metadata(env):
    landing, con = env
    write_file(landing, NAME, "T1,A1,2026-09-06,CREDIT,1.00,USD\n")
    run_id = start_run(con)
    ingest(con, run_id, discover(landing)[0])
    rows = con.execute("SELECT DISTINCT source_filename, branch_id, run_id FROM bronze_transactions").fetchall()
    assert rows == [(NAME, "BR001", run_id)]
    assert con.execute("SELECT load_timestamp FROM bronze_transactions").fetchone()[0]


def test_ingest_records_file_audit_row(env):
    landing, con = env
    write_file(landing, NAME, "T1,A1,2026-09-06,CREDIT,1.00,USD\nT2,A1,2026-09-06,DEBIT,2.00,USD\n")
    recognized = discover(landing)[0]
    ingest(con, start_run(con), recognized)
    rows = con.execute("SELECT source_filename, branch_id, file_date, file_sha256, source_rows, file_status FROM file_audit").fetchall()
    assert rows == [(NAME, "BR001", "2026-09-06", recognized[0]["sha256"], 2, "LOADED")]


def test_identical_processed_file_is_skipped(env):
    landing, con = env
    write_file(landing, NAME, "T1,A1,2026-09-06,CREDIT,1.00,USD\nT2,A1,2026-09-06,DEBIT,2.00,USD\n")
    run1 = start_run(con)
    ingest(con, run1, discover(landing)[0])
    mark_processed(con, run1)
    run2 = start_run(con)
    results = ingest(con, run2, discover(landing)[0])
    assert results == [{"filename": NAME, "status": "SKIPPED_IDENTICAL", "source_rows": 0}]
    assert bronze_count(con) == 2
    note = con.execute("SELECT note FROM file_audit WHERE run_id = ?", (run2,)).fetchone()[0]
    assert NAME in note and run1 in note


def test_loaded_but_unprocessed_file_is_loaded_again(env):
    landing, con = env
    write_file(landing, NAME, "T1,A1,2026-09-06,CREDIT,1.00,USD\nT2,A1,2026-09-06,DEBIT,2.00,USD\n")
    ingest(con, start_run(con), discover(landing)[0])
    results = ingest(con, start_run(con), discover(landing)[0])
    assert results[0]["status"] == "LOADED"
    assert bronze_count(con) == 4


def test_same_name_with_different_content_is_processed(env):
    landing, con = env
    write_file(landing, NAME, "T1,A1,2026-09-06,CREDIT,1.00,USD\n")
    run1 = start_run(con)
    ingest(con, run1, discover(landing)[0])
    mark_processed(con, run1)
    write_file(landing, NAME, "T1,A1,2026-09-06,CREDIT,9.00,USD\n")
    results = ingest(con, start_run(con), discover(landing)[0])
    assert results == [{"filename": NAME, "status": "LOADED", "source_rows": 1}]
    assert bronze_count(con) == 2


def test_wrong_header_raises_and_writes_nothing(env):
    landing, con = env
    write_file(landing, NAME, "x,y\n", header="wrong,header\n")
    with pytest.raises(ValueError, match="header does not match"):
        ingest(con, start_run(con), discover(landing)[0])
    assert bronze_count(con) == 0
    assert con.execute("SELECT COUNT(*) FROM file_audit").fetchone()[0] == 0


def test_wrong_field_count_raises_and_writes_nothing(env):
    landing, con = env
    write_file(landing, NAME, "T1,A1,2026-09-06,CREDIT,100.00\n")
    with pytest.raises(ValueError, match="has 5 fields, expected 6"):
        ingest(con, start_run(con), discover(landing)[0])
    assert bronze_count(con) == 0
    assert con.execute("SELECT COUNT(*) FROM file_audit").fetchone()[0] == 0


def test_empty_file_raises(tmp_path):
    path = tmp_path / NAME
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="file is empty"):
        read_source_rows(path)


def test_earlier_good_file_stays_loaded_when_a_later_file_is_bad(env):
    # each file is written in its own transaction, so a bad later file does not undo an earlier good one
    landing, con = env
    write_file(landing, "BR001_20260906_TRANSACTION.csv", "T1,A1,2026-09-06,CREDIT,1.00,USD\nT2,A1,2026-09-06,DEBIT,2.00,USD\n")
    write_file(landing, "BR002_20260906_TRANSACTION.csv", "x,y\n", header="wrong,header\n")
    run_id = start_run(con)
    with pytest.raises(ValueError, match="BR002_20260906_TRANSACTION.csv"):
        ingest(con, run_id, discover(landing)[0])
    assert con.execute("SELECT DISTINCT source_filename FROM bronze_transactions").fetchall() == [("BR001_20260906_TRANSACTION.csv",)]
    assert bronze_count(con) == 2
    assert con.execute("SELECT source_filename, file_status FROM file_audit WHERE run_id = ?", (run_id,)).fetchall() == [("BR001_20260906_TRANSACTION.csv", "LOADED")]
