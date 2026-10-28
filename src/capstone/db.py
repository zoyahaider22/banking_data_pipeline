"""
db.py - shared SQLite helpers for the capstone pipeline:
connect (creating the tables if missing) and record run status.
"""

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "output" / "capstone" / "banking_capstone.db"
SCHEMA_PATH = BASE_DIR / "sql" / "capstone" / "schema.sql"


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(db_path=DB_PATH):
    """Open the capstone database and make sure all tables exist."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return con


def start_run(con):
    """Create a run_audit row with status RUNNING and return its run_id."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    run_id = "RUN_" + stamp + "_" + uuid.uuid4().hex[:6]
    con.execute(
        "INSERT INTO run_audit (run_id, started_at, status) VALUES (?, ?, 'RUNNING')",
        (run_id, utc_now()),
    )
    con.commit()
    return run_id


def finish_run(con, run_id, status, reason=None):
    """Set the final status (SUCCESS or FAILED), finish time and reason."""
    con.execute(
        "UPDATE run_audit SET finished_at = ?, status = ?, status_reason = ? WHERE run_id = ?",
        (utc_now(), status, reason, run_id),
    )
    con.commit()
