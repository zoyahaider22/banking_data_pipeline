import shutil
import sqlite3

import pytest

from orchestration.banking_job import banking_job
from src.spark.load_data import BANKING_DB
from src.spark.reporting import REPORT_NAME


def make_run_config(db_path, output_dir):
    return {
        "ops": {
            "extract": {"config": {"db_path": str(db_path), "fail_first_attempts": 0}},
            "publish": {"config": {"output_dir": str(output_dir)}},
        }
    }


@pytest.fixture
def good_db(tmp_path):
    path = tmp_path / "good.db"
    shutil.copy2(BANKING_DB, path)
    return path


@pytest.fixture
def bad_db(tmp_path):
    path = tmp_path / "bad.db"
    shutil.copy2(BANKING_DB, path)
    con = sqlite3.connect(path)
    con.execute(
        "INSERT INTO bank_transaction (transaction_id, account_id, transaction_date, transaction_type, amount, currency, source_file) "
        "VALUES ('T9999', 'A9999', '2024-01-15', 'CREDIT', 10.0, 'USD', 'test_bad.csv')"
    )
    con.commit()
    con.close()
    return path


def test_job_succeeds_on_isolated_copy_and_publishes_report(good_db, tmp_path):
    output_dir = tmp_path / "reports"
    result = banking_job.execute_in_process(run_config=make_run_config(good_db, output_dir))
    assert result.success
    info = result.output_for_node("publish")
    assert info["rows"] == 3
    assert info["transaction_count"] == 20
    assert info["net_cash_flow"] == pytest.approx(3384.5)
    assert (output_dir / REPORT_NAME).exists()


def test_validation_failure_blocks_publish(bad_db, tmp_path):
    output_dir = tmp_path / "reports"
    result = banking_job.execute_in_process(
        run_config=make_run_config(bad_db, output_dir), raise_on_error=False
    )
    assert not result.success
    assert [e.step_key for e in result.get_step_failure_events()] == ["validate"]
    assert [e.step_key for e in result.get_step_success_events()] == ["extract"]
    assert not output_dir.exists()
