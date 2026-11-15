"""Read-only Sportmonks FA Cup team pagination diagnostic.

Makes four bounded API reads (page 1/2 at per_page 25/50), records only
pagination metadata and team IDs, and never writes to any database.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from typing import Any

from sportmonks import SportmonksClient

SEASON_ID = "28020"
PER_PAGE_VALUES = (25, 50)
PAGES = (1, 2)


def inspect_response(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        data = payload.get("data")
        pagination = payload.get("pagination")
    else:
        data, pagination = payload, None
    rows = data if isinstance(data, list) else []
    ids = [
        str(row.get("id"))
        for row in rows
        if isinstance(row, dict) and row.get("id") is not None
    ]
    meta = pagination if isinstance(pagination, dict) else {}
    return {
        "row_count": len(rows),
        "team_ids": ids,
        "pagination": {
            key: meta.get(key)
            for key in ("count", "per_page", "current_page", "has_more", "next_page")
            if key in meta
        },
        "response_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
    }


def run_probe(client_factory=SportmonksClient) -> dict[str, Any]:
    results = []
    with client_factory() as client:
        for per_page in PER_PAGE_VALUES:
            for page in PAGES:
                try:
                    payload = client._get(
                        f"teams/seasons/{SEASON_ID}",
                        {"per_page": per_page, "page": page},
                    )
                    item = inspect_response(payload)
                    item.update({"per_page_requested": per_page, "page_requested": page})
                    results.append(item)
                except Exception as exc:
                    results.append({
                        "per_page_requested": per_page,
                        "page_requested": page,
                        "error_type": type(exc).__name__,
                        "error": str(exc)[:240],
                    })
    comparisons = []
    for per_page in PER_PAGE_VALUES:
        pair = [
            x for x in results
            if x.get("per_page_requested") == per_page and "team_ids" in x
        ]
        if len(pair) == 2:
            first, second = sorted(pair, key=lambda x: x["page_requested"])
            comparisons.append({
                "per_page": per_page,
                "page_1_count": first["row_count"],
                "page_2_count": second["row_count"],
                "same_id_sequence": first["team_ids"] == second["team_ids"],
                "overlap_count": len(set(first["team_ids"]) & set(second["team_ids"])),
                "pagination_has_more_page_1": first["pagination"].get("has_more"),
                "pagination_current_page_1": first["pagination"].get("current_page"),
                "pagination_current_page_2": second["pagination"].get("current_page"),
            })
    return {
        "report_name": "sportmonks_fa_cup_team_pagination_probe",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "season_id": SEASON_ID,
        "read_only": True,
        "database_accessed": False,
        "database_writes": 0,
        "fixtures_requested": 0,
        "statistics_requested": 0,
        "requests_made": len(results),
        "results": results,
        "page_comparisons": comparisons,
        "success": bool(results) and all("error" not in x for x in results),
    }


if __name__ == "__main__":
    if not os.getenv("SPORTMONKS_API_TOKEN", "").strip():
        raise SystemExit("SPORTMONKS_API_TOKEN secret is required.")
    print(json.dumps(run_probe(), sort_keys=True))
