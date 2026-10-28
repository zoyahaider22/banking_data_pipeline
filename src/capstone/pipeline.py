"""
pipeline.py - plain Python runner: discover -> ingest -> validate -> transform -> publish.

Steps run in sequence, so a step that raises an error stops the run before any
later step (in particular before publish). The run is recorded in run_audit as
SUCCESS or FAILED with a reason that names the failing step. A rejected ROW is
not a failure (it goes to Exceptions); a failure is structural: bad header,
reconciliation mismatch, PySpark/SQL disagreement, and similar.

Command line:  python -m src.capstone.pipeline   (exit code 1 if the run failed)
"""

from src.capstone.db import DB_PATH, connect, finish_run, start_run
from src.capstone.discover import LANDING_FOLDER, discover
from src.capstone.ingest import ingest
from src.capstone.publish import GOLD_CSV, publish
from src.capstone.transform import transform
from src.capstone.validate import validate


def run_pipeline(landing_folder=LANDING_FOLDER, db_path=DB_PATH, gold_csv=GOLD_CSV, accounts=None):
    """Run all steps once. Returns a dict describing the run (never raises)."""
    con = connect(db_path)
    run_id = start_run(con)
    step = "discover"
    result = {"run_id": run_id, "status": None, "reason": None,
              "ingested": [], "validated": [], "unrecognized": [], "gold_rows": 0}
    try:
        recognized, unrecognized = discover(landing_folder)
        result["unrecognized"] = unrecognized
        step = "ingest"
        result["ingested"] = ingest(con, run_id, recognized)
        step = "validate"
        result["validated"] = validate(con, run_id, accounts)
        step = "transform"
        gold_rows = transform(con, db_path)
        step = "publish"
        result["gold_rows"] = publish(con, run_id, gold_rows, gold_csv)
    except Exception as exc:
        result["status"] = "FAILED"
        result["reason"] = step + " failed: " + type(exc).__name__ + ": " + str(exc)
    else:
        loaded = sum(1 for r in result["ingested"] if r["status"] == "LOADED")
        skipped = sum(1 for r in result["ingested"] if r["status"] == "SKIPPED_IDENTICAL")
        accepted = sum(r["accepted_rows"] for r in result["validated"])
        rejected = sum(r["rejected_rows"] for r in result["validated"])
        result["status"] = "SUCCESS"
        result["reason"] = (
            "files loaded=" + str(loaded) + ", skipped_identical=" + str(skipped)
            + ", unrecognized=" + str(len(result["unrecognized"]))
            + "; accepted=" + str(accepted) + ", rejected=" + str(rejected)
            + "; gold_rows=" + str(result["gold_rows"])
        )
    finish_run(con, run_id, result["status"], result["reason"])
    con.close()
    return result


def main():
    result = run_pipeline()
    print("run_id :", result["run_id"])
    print("status :", result["status"])
    print("reason :", result["reason"])
    for r in result["ingested"]:
        print("  ingest  ", r["filename"], r["status"], r["source_rows"])
    for r in result["validated"]:
        print("  validate", r["filename"], "source", r["source_rows"],
              "accepted", r["accepted_rows"], "rejected", r["rejected_rows"])
    for r in result["unrecognized"]:
        print("  unrecognized", r["filename"], "->", r["reason"])
    return 0 if result["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
