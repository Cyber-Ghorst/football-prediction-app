"""Read-only Sportmonks FA Cup roster endpoint diagnostic.

Compares direct team-season pagination/order variants with the documented
season-by-ID include=teams endpoint. Records IDs and counts only; no DB writes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from typing import Any

from sportmonks import SportmonksClient

SEASON_ID = "28020"


def _team_ids(rows: Any) -> list[str]:
    if not isinstance(rows, list):
        return []
    return [
        str(row.get("id"))
        for row in rows
        if isinstance(row, dict) and row.get("id") is not None
    ]


def inspect_response(payload: Any) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload, dict) else payload
    rows = data if isinstance(data, list) else []
    pagination = payload.get("pagination") if isinstance(payload, dict) else None
    meta = pagination if isinstance(pagination, dict) else {}
    return {
        "row_count": len(rows),
        "team_ids": _team_ids(rows),
        "pagination": {
            key: meta.get(key)
            for key in ("count", "per_page", "current_page", "has_more", "next_page")
            if key in meta
        },
        "response_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
    }


def inspect_season_include(payload: Any) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload, dict) else None
    season = data if isinstance(data, dict) else {}
    teams = season.get("teams")
    if isinstance(teams, dict):
        teams = teams.get("data")
    ids = _team_ids(teams)
    return {
        "season_id_returned": str(season.get("id")) if season.get("id") is not None else None,
        "league_id_returned": str(season.get("league_id")) if season.get("league_id") is not None else None,
        "teams_count": len(teams) if isinstance(teams, list) else None,
        "team_ids": ids,
        "teams_include_present": isinstance(teams, list),
        "response_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
    }


def run_probe(client_factory=SportmonksClient) -> dict[str, Any]:
    results = []
    with client_factory() as client:
        requests = [
            ("teams_page_1_per_25", "teams/seasons/" + SEASON_ID, {"per_page": 25, "page": 1}),
            ("teams_page_2_per_25", "teams/seasons/" + SEASON_ID, {"per_page": 25, "page": 2}),
            ("teams_page_1_per_50", "teams/seasons/" + SEASON_ID, {"per_page": 50, "page": 1}),
            ("teams_page_2_per_50", "teams/seasons/" + SEASON_ID, {"per_page": 50, "page": 2}),
            ("teams_order_asc", "teams/seasons/" + SEASON_ID, {"per_page": 50, "page": 1, "order": "asc"}),
            ("teams_order_desc", "teams/seasons/" + SEASON_ID, {"per_page": 50, "page": 1, "order": "desc"}),
            ("season_include_teams", "seasons/" + SEASON_ID, {"include": "teams"}),
        ]
        for label, path, params in requests:
            try:
                payload = client._get(path, params)
                item = (
                    inspect_season_include(payload)
                    if label == "season_include_teams"
                    else inspect_response(payload)
                )
                item.update({"request_label": label, "request_path": path})
                results.append(item)
            except Exception as exc:
                results.append({
                    "request_label": label,
                    "request_path": path,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:240],
                })

    by_label = {item.get("request_label"): item for item in results}
    asc = by_label.get("teams_order_asc", {}).get("team_ids", [])
    desc = by_label.get("teams_order_desc", {}).get("team_ids", [])
    included = by_label.get("season_include_teams", {}).get("team_ids", [])
    direct_ids = by_label.get("teams_page_1_per_50", {}).get("team_ids", [])
    return {
        "report_name": "sportmonks_fa_cup_alternate_roster_endpoint_probe",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "season_id": SEASON_ID,
        "read_only": True,
        "database_accessed": False,
        "database_writes": 0,
        "fixtures_requested": 0,
        "statistics_requested": 0,
        "requests_made": len(results),
        "results": results,
        "comparisons": {
            "order_asc_desc_same_id_set": bool(asc or desc) and set(asc) == set(desc),
            "order_asc_desc_counts": [len(asc), len(desc)],
            "direct_page_1_vs_season_include_same_id_set": bool(direct_ids or included) and set(direct_ids) == set(included),
            "direct_page_1_count": len(direct_ids),
            "season_include_team_count": len(included),
        },
        "success": bool(results) and all("error" not in item for item in results),
    }


if __name__ == "__main__":
    if not os.getenv("SPORTMONKS_API_TOKEN", "").strip():
        raise SystemExit("SPORTMONKS_API_TOKEN secret is required.")
    print(json.dumps(run_probe(), sort_keys=True))
