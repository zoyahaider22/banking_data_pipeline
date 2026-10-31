
"""
api_server.py

Week 8 CDP Readiness Extension.

A read-only HTTP API exposing approved Customer 360 summaries.

Endpoint:
    GET /customers/<customer_id>/summary

Examples:
    GET /customers/C001/summary
    GET /customers/C002/summary
    GET /customers/C003/summary
    GET /customers/C999/summary

Known customer: HTTP 200
Unknown customer: HTTP 404

Run:
    python -m src.customer360.api_server

The server binds exclusively to 127.0.0.1.
No write endpoints are provided.
"""

import json
import re
import sqlite3

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

from src.capstone.db import DB_PATH


# ------------------------------------------------------------
# 1. SERVER CONFIGURATION
# ------------------------------------------------------------

HOST = "127.0.0.1"
PORT = 8765

ENDPOINT_PATTERN = re.compile(
    r"^/customers/([^/]+)/summary$"
)


# ------------------------------------------------------------
# 2. READ-ONLY DATABASE CONNECTION
# ------------------------------------------------------------

def get_readonly_connection():
    """Open the existing SQLite database in read-only mode."""

    database_uri = (
        DB_PATH.resolve().as_uri() + "?mode=ro"
    )

    connection = sqlite3.connect(
        database_uri,
        uri=True,
        timeout=5
    )

    connection.row_factory = sqlite3.Row

    # Additional protection against database writes.
    connection.execute("PRAGMA query_only = ON")

    return connection


# ------------------------------------------------------------
# 3. DATABASE LOOKUP
# ------------------------------------------------------------

def get_customer_summary(customer_id):
    """Retrieve one approved customer summary using a bound parameter."""

    connection = get_readonly_connection()

    try:
        row = connection.execute(
            """
            SELECT
                customer_id,
                account_count,
                transaction_count,
                total_transaction_amount
            FROM customer_360
            WHERE customer_id = ?
            """,
            (customer_id,)
        ).fetchone()

        if row is None:
            return None

        return {
            "customer_id": row["customer_id"],
            "account_count": row["account_count"],
            "transaction_count": row["transaction_count"],
            "total_transaction_amount": row[
                "total_transaction_amount"
            ]
        }

    finally:
        connection.close()


# ------------------------------------------------------------
# 4. HTTP REQUEST HANDLER
# ------------------------------------------------------------

class Customer360Handler(BaseHTTPRequestHandler):
    """Handle read-only Customer 360 HTTP requests."""

    def send_json(self, status_code, payload):
        """Send a properly formatted JSON HTTP response."""

        response = json.dumps(
            payload,
            ensure_ascii=False
        ).encode("utf-8")

        self.send_response(status_code)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(response))
        )

        self.send_header(
            "Cache-Control",
            "no-store"
        )

        self.end_headers()

        self.wfile.write(response)

    def do_GET(self):
        """Process GET /customers/<customer_id>/summary."""

        request_path = urlsplit(self.path).path

        match = ENDPOINT_PATTERN.fullmatch(request_path)

        if not match:
            self.send_json(
                404,
                {"error": "Endpoint not found"}
            )
            return

        customer_id = unquote(match.group(1)).strip()

        if not customer_id:
            self.send_json(
                400,
                {"error": "Customer ID is required"}
            )
            return

        try:
            customer = get_customer_summary(customer_id)

        except sqlite3.Error:
            self.log_error(
                "SQLite query failed while retrieving a customer summary."
            )

            self.send_json(
                500,
                {"error": "Internal server error"}
            )
            return

        if customer is None:
            self.send_json(
                404,
                {"error": "Customer not found"}
            )
            return

        self.send_json(
            200,
            customer
        )

    def reject_write_request(self):
        """Reject every HTTP method that could modify resources."""

        self.send_json(
            405,
            {"error": "Method not allowed"}
        )

    do_POST = reject_write_request
    do_PUT = reject_write_request
    do_PATCH = reject_write_request
    do_DELETE = reject_write_request


# ------------------------------------------------------------
# 5. DATABASE READINESS CHECK
# ------------------------------------------------------------

def check_database():
    """Verify that the existing Customer 360 Gold view is available."""

    connection = get_readonly_connection()

    try:
        connection.execute(
            """
            SELECT
                customer_id,
                account_count,
                transaction_count,
                total_transaction_amount
            FROM customer_360
            LIMIT 0
            """
        )

    finally:
        connection.close()


# ------------------------------------------------------------
# 6. START LOCAL HTTP SERVER
# ------------------------------------------------------------

def run_server(host=HOST, port=PORT):
    """Start the Customer 360 read-only API."""

    if not DB_PATH.is_file():
        raise FileNotFoundError(
            f"Customer 360 database not found: {DB_PATH}"
        )

    check_database()

    server = ThreadingHTTPServer(
        (host, port),
        Customer360Handler
    )

    print("\nCUSTOMER 360 API STARTED")
    print("------------------------")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Database: {DB_PATH}")
    print("\nAvailable endpoint:")
    print(
        f"http://{host}:{port}/customers/C001/summary"
    )
    print("\nPress Ctrl+C to stop the server.")

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print("\nCustomer 360 API stopped.")

    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
