"""Autonomous, read-only OpenScores authentication and response-shape check."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from openscores import OpenScoresClient


def run_check(client_factory: Callable[[], OpenScoresClient] = OpenScoresClient) -> dict:
    """Make one authenticated list_leagues request and return credential-safe diagnostics."""
    report = {
        "operation": "openscores_connection_check",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "openscores",
        "status": "fail",
        "authenticated": False,
        "league_count_returned": None,
        "league_collection_found": False,
        "league_collection_path": None,
        "response_shape": None,
        "provider_retrieved_at_utc": None,
        "read_only": True,
        "prediction_ledger_touched": False,
        "fixtures_imported": False,
    }
    try:
        with client_factory() as client:
            result = client.test_connection()
        report.update({
            "status": "pass",
            "authenticated": True,
            "league_count_returned": result.get("league_count_returned"),
            "league_collection_found": result.get("league_collection_found", False),
            "league_collection_path": result.get("league_collection_path"),
            "response_shape": result.get("response_shape"),
            "provider_retrieved_at_utc": result.get("retrieved_at_utc"),
        })
    except Exception as exc:
        # Never print exception text: provider/network exceptions can contain
        # request details. The exception class is sufficient for diagnosis.
        report["error_type"] = type(exc).__name__
    return report


def main() -> int:
    report = run_check()
    serialized = json.dumps(report, indent=2)
    Path("openscores-connection-report.json").write_text(
        serialized + "\n", encoding="utf-8"
    )
    print(serialized)
    try:
        with open(__import__("os").environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write("## OpenScores autonomous connection check\n\n")
            summary.write(f"- Status: **{report['status']}**\n")
            summary.write(f"- Authenticated: {report['authenticated']}\n")
            summary.write(f"- Leagues returned: {report['league_count_returned']}\n")
            summary.write(f"- League collection found: {report['league_collection_found']}\n")
            summary.write(f"- Response root type: {(report.get('response_shape') or {}).get('root_type')}\n")
            summary.write(f"- League collection path: {report['league_collection_path']}\n")
            summary.write(f"- Checked (UTC): {report['checked_at_utc']}\n")
            summary.write("- Read-only: yes; fixtures imported: no; prediction ledger touched: no\n")
            if report.get("error_type"):
                summary.write(f"- Diagnostic category: {report['error_type']}\n")
    except KeyError:
        pass
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
