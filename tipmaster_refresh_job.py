"""Scheduled TipMaster benchmark refresh with a Neon round-trip check.

This job writes only tipmaster_benchmark_records. It never accesses the
prediction ledger or feeds benchmark shares into prediction generation.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from tipmaster_benchmark import fetch_tipmaster_consensus
from tipmaster_storage import load_tipmaster_benchmark_records, save_tipmaster_benchmark_records


def run_refresh(
    database_url: str,
    *,
    fetcher: Callable[[], Mapping[str, Any]] = fetch_tipmaster_consensus,
    loader: Callable[[str], list[dict[str, Any]]] = load_tipmaster_benchmark_records,
    saver: Callable[[str, list[dict[str, Any]]], int] = save_tipmaster_benchmark_records,
) -> dict[str, Any]:
    """Fetch, persist and reload one feed snapshot, failing on any missing IDs."""
    if not database_url:
        raise ValueError("DATABASE_URL is required.")

    feed = fetcher()
    records = feed.get("matches", []) if isinstance(feed, Mapping) else []
    if not isinstance(records, list) or not records:
        raise RuntimeError("TipMaster returned no valid benchmark records.")

    before = loader(database_url)
    saved = saver(database_url, records)
    after = loader(database_url)

    expected_ids = {
        str(row.get("source_match_id") or "")
        for row in records
        if isinstance(row, Mapping) and row.get("source_match_id")
    }
    reloaded_ids = {
        str(row.get("source_match_id") or "")
        for row in after
        if isinstance(row, Mapping) and row.get("source_match_id")
    }
    missing_ids = sorted(expected_ids - reloaded_ids)
    report = {
        "operation": "scheduled_tipmaster_refresh",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "feed_status": "connected",
        "neon_status": "connected",
        "incoming_records": len(records),
        "saved_records": saved,
        "records_before": len(before),
        "records_after": len(after),
        "round_trip_verified": not missing_ids and saved == len(records),
        "missing_reloaded_ids_count": len(missing_ids),
        "feed_counts": feed.get("counts", {}),
        "prediction_ledger_touched": False,
        "result": "passed" if not missing_ids and saved == len(records) else "round_trip_mismatch",
    }
    if report["result"] != "passed":
        raise RuntimeError(json.dumps(report, sort_keys=True))
    return report


def main() -> int:
    try:
        report = run_refresh(os.environ.get("DATABASE_URL", "").strip())
    except Exception as exc:
        report = {
            "operation": "scheduled_tipmaster_refresh",
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "result": "failed",
            "error": type(exc).__name__,
            "prediction_ledger_touched": False,
        }
        print(json.dumps(report, indent=2))
        with open(os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null"), "a", encoding="utf-8") as out:
            out.write("## Scheduled TipMaster refresh failed\\n\\n")
            out.write(f"- Error type: {type(exc).__name__}\\n")
            out.write("- Prediction ledger touched: no\\n")
        return 1

    print(json.dumps(report, indent=2))
    with open(os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null"), "a", encoding="utf-8") as out:
        out.write("## Scheduled TipMaster refresh\\n\\n")
        out.write(f"- Feed: connected ({report['incoming_records']} valid records)\\n")
        out.write(
            f"- Neon: connected ({report['records_before']} before, "
            f"{report['records_after']} after)\\n"
        )
        out.write(f"- Records saved: {report['saved_records']}\\n")
        out.write(f"- Round-trip verified: {report['round_trip_verified']}\\n")
        out.write("- Prediction ledger touched: no\\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
