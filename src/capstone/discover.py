"""
discover.py - the "discover" step of the capstone pipeline.

Looks in the landing folder (not subfolders) and splits the files into:
  - recognized:   names like BR001_20260906_TRANSACTION.csv
  - unrecognized: everything else, listed with a reason (never silently ignored)

For recognized files it reads branch_id and file_date from the filename and
computes a SHA-256 hash of the content. Files are only read, never changed.
"""

import hashlib
import re
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LANDING_FOLDER = BASE_DIR / "data" / "capstone" / "landing"

FILENAME_REGEX = re.compile(r"^(BR\d+)_(\d{8})_TRANSACTION\.csv$")


def file_sha256(path):
    """SHA-256 fingerprint of the file content."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_filename(name):
    """Return (branch_id, file_date as YYYY-MM-DD, None) or (None, None, reason)."""
    match = FILENAME_REGEX.match(name)
    if not match:
        return None, None, "filename does not match BR<digits>_<YYYYMMDD>_TRANSACTION.csv"
    branch_id, date_text = match.groups()
    try:
        file_date = datetime.strptime(date_text, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return None, None, "filename date is not a real calendar date"
    return branch_id, file_date, None


def discover(landing_folder=LANDING_FOLDER):
    """Return (recognized, unrecognized) for the files in the landing folder."""
    recognized = []
    unrecognized = []
    for path in Path(landing_folder).iterdir():
        if not path.is_file():
            continue
        branch_id, file_date, reason = parse_filename(path.name)
        if reason:
            unrecognized.append({"filename": path.name, "reason": reason})
        else:
            recognized.append({
                "path": str(path),
                "filename": path.name,
                "branch_id": branch_id,
                "file_date": file_date,
                "sha256": file_sha256(path),
            })
    recognized.sort(key=lambda f: (f["file_date"], f["branch_id"], f["filename"]))
    unrecognized.sort(key=lambda f: f["filename"])
    return recognized, unrecognized
