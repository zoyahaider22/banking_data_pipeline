import pytest

from src.spark.reporting import (
    REPORT_NAME,
    DataQualityError,
    raise_if_checks_failed,
    write_branch_report,
)

BRANCH_ROWS = [
    {"branch_id": "BR001", "transaction_count": 6, "gross_amount": 930.5, "net_cash_flow": 529.5},
    {"branch_id": "BR002", "transaction_count": 6, "gross_amount": 1355.0, "net_cash_flow": 1075.0},
    {"branch_id": "BR003", "transaction_count": 8, "gross_amount": 2450.0, "net_cash_flow": 1780.0},
]


def test_valid_data_passes_gate_and_report_has_known_totals(tmp_path):
    raise_if_checks_failed([("Null amounts", 0), ("Non-positive amounts", 0)])
    info = write_branch_report(BRANCH_ROWS, tmp_path)
    assert info["rows"] == 3
    assert info["transaction_count"] == 20
    assert info["net_cash_flow"] == pytest.approx(3384.5)


def test_bad_data_raises_error_naming_the_failed_check():
    results = [("Null amounts", 0), ("Transactions referencing nonexistent accounts", 1)]
    with pytest.raises(DataQualityError, match="nonexistent accounts: 1"):
        raise_if_checks_failed(results)


def test_rerun_overwrites_report_without_changing_it(tmp_path):
    write_branch_report(BRANCH_ROWS, tmp_path)
    report = tmp_path / REPORT_NAME
    first = report.read_bytes()
    write_branch_report(BRANCH_ROWS, tmp_path)
    assert report.read_bytes() == first
    assert [p.name for p in tmp_path.iterdir()] == [REPORT_NAME]
