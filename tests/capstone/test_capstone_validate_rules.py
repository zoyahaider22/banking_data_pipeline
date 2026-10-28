"""
Tests for the capstone validation rules (src/capstone/validate.py::row_reasons).

Expected reason texts are written out by hand here, not imported from the code.
Fixed context: known accounts {"A1", "A2"}; already accepted transaction_ids {"T1"}.
Row layout: (transaction_id, account_id, transaction_date, transaction_type, amount, currency)
"""

import pytest

from src.capstone.validate import row_reasons

ACCOUNTS = {"A1", "A2"}
ACCEPTED = {"T1"}

R_TID_MISSING = "transaction_id is missing"
R_ACC_MISSING = "account_id is missing"
R_DATE = "transaction_date must be a valid date in YYYY-MM-DD format"
R_TYPE = "transaction_type must be CREDIT or DEBIT"
R_AMOUNT = "amount must be present, numeric, and greater than 0"
R_CURRENCY = "currency must be USD"
R_UNKNOWN = "account_id not found in accounts reference"
R_DUP = "duplicate transaction_id already accepted (first accepted record wins)"

CASES = [
    ("valid_row", ("T9", "A1", "2026-09-06", "CREDIT", "10.00", "USD"), []),
    ("valid_integer_amount", ("T9", "A2", "2026-09-07", "DEBIT", "120", "USD"), []),
    ("unknown_account", ("T9", "A9", "2026-09-06", "CREDIT", "10.00", "USD"), [R_UNKNOWN]),
    ("missing_account", ("T9", "", "2026-09-06", "CREDIT", "10.00", "USD"), [R_ACC_MISSING]),
    ("whitespace_account", ("T9", "   ", "2026-09-06", "CREDIT", "10.00", "USD"), [R_ACC_MISSING]),
    ("missing_amount", ("T9", "A1", "2026-09-06", "DEBIT", "", "USD"), [R_AMOUNT]),
    ("zero_amount", ("T9", "A1", "2026-09-06", "DEBIT", "0.00", "USD"), [R_AMOUNT]),
    ("negative_amount", ("T9", "A1", "2026-09-06", "CREDIT", "-50.00", "USD"), [R_AMOUNT]),
    ("date_month_13", ("T9", "A1", "2026-13-06", "CREDIT", "10.00", "USD"), [R_DATE]),
    ("date_with_slashes", ("T9", "A1", "2026/09/06", "CREDIT", "10.00", "USD"), [R_DATE]),
    ("unsupported_type", ("T9", "A1", "2026-09-06", "TRANSFER", "10.00", "USD"), [R_TYPE]),
    ("unsupported_currency", ("T9", "A1", "2026-09-06", "CREDIT", "10.00", "EUR"), [R_CURRENCY]),
    ("missing_account_and_bad_type", ("T9", "", "2026-09-06", "PIZZA", "80.00", "USD"), [R_ACC_MISSING, R_TYPE]),
    ("duplicate_of_accepted_id", ("T1", "A1", "2026-09-06", "CREDIT", "10.00", "USD"), [R_DUP]),
    ("duplicate_and_unknown_account", ("T1", "A9", "2026-09-06", "CREDIT", "10.00", "USD"), [R_UNKNOWN, R_DUP]),
    ("missing_transaction_id", ("", "A1", "2026-09-06", "CREDIT", "10.00", "USD"), [R_TID_MISSING]),
    ("missing_id_and_unknown_account", ("", "A9", "2026-09-06", "DEBIT", "45.00", "USD"), [R_TID_MISSING, R_UNKNOWN]),
    ("repeated_id_never_accepted_is_not_duplicate", ("T5", "A9", "2026-09-06", "DEBIT", "75.00", "USD"), [R_UNKNOWN]),
]


@pytest.mark.parametrize("values, expected", [(c[1], c[2]) for c in CASES], ids=[c[0] for c in CASES])
def test_row_reasons(values, expected):
    assert row_reasons(values, ACCOUNTS, ACCEPTED) == expected
