
"""
test_api_server.py

Automated integration tests for the Week 8 Customer 360 API.

Tests:
1. C001: customer with two accounts and multiple transactions.
2. C002: independent customer lookup.
3. C003: customer with no transactions.
4. C999: unknown customer returns HTTP 404.
5. POST: write requests are rejected.
6. SQL injection-like customer ID is treated as a value.
"""

import json
import threading

from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from src.customer360.api_server import (
    Customer360Handler,
    check_database,
)


@pytest.fixture(scope="module")
def api_base_url():
    """Start a temporary local HTTP server for integration tests."""

    check_database()

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        Customer360Handler,
    )

    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )

    thread.start()

    host, port = server.server_address[:2]

    yield f"http://{host}:{port}"

    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.mark.parametrize(
    "customer_id,accounts,transactions,total",
    [
        ("C001", 2, 5, 870.50),
        ("C002", 1, 2, 315.00),
        ("C003", 1, 0, 0.00),
    ],
)
def test_known_customer_summary(
    api_base_url,
    customer_id,
    accounts,
    transactions,
    total,
):
    """Known customers must return HTTP 200 and correct JSON."""

    url = f"{api_base_url}/customers/{customer_id}/summary"

    with urlopen(url, timeout=5) as response:

        assert response.status == 200

        assert response.headers[
            "Content-Type"
        ].startswith("application/json")

        payload = json.loads(
            response.read().decode("utf-8")
        )

    assert payload["customer_id"] == customer_id
    assert payload["account_count"] == accounts
    assert payload["transaction_count"] == transactions

    assert payload["total_transaction_amount"] == pytest.approx(
        total
    )


def test_unknown_customer_returns_404(api_base_url):
    """Unknown customers must return the required error JSON."""

    url = f"{api_base_url}/customers/C999/summary"

    with pytest.raises(HTTPError) as error:

        urlopen(url, timeout=5)

    assert error.value.code == 404

    payload = json.loads(
        error.value.read().decode("utf-8")
    )

    assert payload == {
        "error": "Customer not found"
    }


def test_post_request_is_rejected(api_base_url):
    """The API must not expose write operations."""

    request = Request(
        f"{api_base_url}/customers/C001/summary",
        data=b"{}",
        headers={
            "Content-Type": "application/json"
        },
        method="POST",
    )

    with pytest.raises(HTTPError) as error:

        urlopen(request, timeout=5)

    assert error.value.code == 405

    payload = json.loads(
        error.value.read().decode("utf-8")
    )

    assert payload == {
        "error": "Method not allowed"
    }


def test_customer_id_is_parameterized(api_base_url):
    """SQL-looking input must not retrieve another customer's data."""

    url = (
        f"{api_base_url}/customers/"
        "C001%27%20OR%201%3D1%20--/summary"
    )

    with pytest.raises(HTTPError) as error:

        urlopen(url, timeout=5)

    assert error.value.code == 404
