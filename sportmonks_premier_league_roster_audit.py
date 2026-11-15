"""Read-only Sportmonks roster export for manual identity verification.

Fetches the Premier League 2026/27 team catalogue only. It does not connect
to CockroachDB, write provider links, fetch fixtures, or touch predictions.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from sportmonks import SportmonksClient

LEAGUE_ID = "8"
SEASON_ID = "28083"


def safe_team(row: dict[str, Any]) -> dict[str, Any]:
    country = row.get("country")
    if isinstance(country, dict):
        country = {"id": country.get("id"), "name": country.get("name")}
    else:
        country = None
    return {
        "sportmonks_team_id": str(row.get("id") or ""),
        "name": row.get("name"),
        "short_code": row.get("short_code"),
        "country": country,
        "nationality": row.get("nationality"),
        "founded": row.get("founded"),
        "venue_id": str(row.get("venue_id")) if row.get("venue_id") is not None else None,
    }


def build_report(client_factory=SportmonksClient) -> dict[str, Any]:
    report: dict[str, Any] = {
        "report_name": "premier_league_2026_27_read_only_team_roster",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "sportmonks",
        "league_id": LEAGUE_ID,
        "season_id": SEASON_ID,
        "read_only": True,
        "database_touched": False,
        "provider_links_written": 0,
        "fixtures_requested": 0,
        "prediction_ledger_touched": False,
        "status": "error",
        "teams": [],
        "errors": [],
    }
    try:
        with client_factory() as client:
            rows = client.teams_by_season(SEASON_ID, per_page=50)
            teams = [safe_team(row) for row in rows]
            teams.sort(key=lambda item: (str(item.get("name") or "").casefold(), item["sportmonks_team_id"]))
            ids = [item["sportmonks_team_id"] for item in teams]
            duplicate_ids = sorted({item for item in ids if ids.count(item) > 1})
            missing_ids = [item.get("name") for item in teams if not item["sportmonks_team_id"]]
            report.update({
                "status": "pass" if teams and not duplicate_ids and not missing_ids else "review_required",
                "teams_returned": len(teams),
                "unique_team_ids": len(set(ids)),
                "duplicate_team_ids": duplicate_ids,
                "teams_missing_ids": missing_ids,
                "last_request_metadata": dict(client.last_metadata),
                "teams": teams,
            })
    except Exception as exc:
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)[:300]})
    return report


def main() -> int:
    if not (os.getenv("SPORTMONKS_API_TOKEN") or os.getenv("SPORTMONKS_API_KEY")):
        report = {
            "report_name": "premier_league_2026_27_read_only_team_roster",
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "provider": "sportmonks",
            "league_id": LEAGUE_ID,
            "season_id": SEASON_ID,
            "read_only": True,
            "database_touched": False,
            "provider_links_written": 0,
            "fixtures_requested": 0,
            "prediction_ledger_touched": False,
            "status": "error",
            "teams": [],
            "errors": [{"type": "ConfigurationError", "message": "SPORTMONKS_API_TOKEN secret is missing."}],
        }
    else:
        report = build_report()
    print(json.dumps(report, sort_keys=True))
    return 0 if report.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
