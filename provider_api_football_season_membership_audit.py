"""Read-only verification of API-Football team membership for a requested season.

This audit checks the live /teams?league=...&season=... response against the
21 held team IDs. It does not connect to the database or write provider links.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from api_football import APIFootballClient

SEASON = 2026
REPORT = Path("provider-api-football-season-membership-audit.json")
TARGETS = (
    {"name": "Premier League", "league_id": "39", "suspects": (
        ("46", "Leicester"), ("41", "Southampton"),
        ("48", "West Ham"), ("39", "Wolves"),
    )},
    {"name": "La Liga", "league_id": "140", "suspects": (
        ("547", "Girona"), ("534", "Las Palmas"), ("537", "Leganes"),
        ("798", "Mallorca"), ("720", "Valladolid"),
    )},
    {"name": "Serie A", "league_id": "135", "suspects": (
        ("511", "Empoli"), ("504", "Hellas Verona"),
    )},
    {"name": "Bundesliga", "league_id": "78", "suspects": (
        ("180", "1. FC Heidenheim"), ("186", "FC St. Pauli"),
        ("191", "Holstein Kiel"), ("176", "VfL Bochum"),
        ("161", "VfL Wolfsburg"),
    )},
    {"name": "Ligue 1", "league_id": "61", "suspects": (
        ("112", "Metz"), ("82", "Montpellier"), ("83", "Nantes"),
        ("93", "Reims"), ("1063", "Saint Etienne"),
    )},
)


def _team(row: Mapping[str, Any]) -> Mapping[str, Any]:
    value = row.get("team")
    return value if isinstance(value, Mapping) else row


def build_season_membership_report(
    responses: Mapping[str, list[Mapping[str, Any]]],
    errors: Mapping[str, str] | None = None,
    season: int = SEASON,
) -> dict[str, Any]:
    errors = dict(errors or {})
    competitions = []
    total_returned = 0
    total_missing = 0
    total_confirmed = 0
    for target in TARGETS:
        league_id = target["league_id"]
        rows = responses.get(league_id, [])
        returned_ids = {
            str(_team(row).get("id") or "").strip()
            for row in rows if isinstance(row, Mapping)
        }
        returned_ids.discard("")
        suspect_records = [
            {
                "provider_entity_id": team_id,
                "name": name,
                "returned_by_requested_season_endpoint": team_id in returned_ids,
            }
            for team_id, name in target["suspects"]
        ]
        returned = [row for row in suspect_records if row["returned_by_requested_season_endpoint"]]
        missing = [row for row in suspect_records if not row["returned_by_requested_season_endpoint"]]
        error = errors.get(league_id)
        total_returned += len(returned)
        total_missing += len(missing) if not error else 0
        total_confirmed += len(suspect_records)
        competitions.append({
            "competition": target["name"],
            "league_provider_id": league_id,
            "requested_parameters": {"league": int(league_id), "season": int(season)},
            "provider_team_rows_returned": len(rows),
            "suspect_team_rows_expected": len(suspect_records),
            "suspect_ids_returned": returned,
            "suspect_ids_absent_from_response": missing if not error else [],
            "status": (
                "provider_request_error" if error else
                "suspect_records_returned_by_requested_season_endpoint" if returned else
                "suspect_records_absent_from_requested_season_endpoint"
            ),
            "error": error,
        })
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "provider": "api_football",
        "operation": "provider_api_football_season_membership_audit",
        "read_only": True,
        "database_writes": False,
        "canonical_ids_assigned": 0,
        "provider_links_created": 0,
        "provider_scope_fields_updated": 0,
        "requested_season_year": int(season),
        "request_endpoint": "/teams",
        "suspect_records_examined": total_confirmed,
        "suspect_records_returned_by_provider": total_returned,
        "suspect_records_absent_from_successful_responses": total_missing,
        "competitions": competitions,
        "interpretation": (
            "A returned suspect ID means the live API-Football season-filtered endpoint "
            "still associates that team with the requested top-flight competition. An absent "
            "ID means the stored source row may be stale. Neither outcome creates or approves "
            "an identity link; compare with official competition evidence before changing scope."
        ),
    }


def audit_live_api_football_season_membership(
    client_factory=APIFootballClient,
    season: int = SEASON,
) -> dict[str, Any]:
    client = client_factory()
    responses: dict[str, list[Mapping[str, Any]]] = {}
    errors: dict[str, str] = {}
    try:
        for target in TARGETS:
            league_id = target["league_id"]
            try:
                responses[league_id] = client.teams(int(league_id), int(season))
            except Exception as exc:
                errors[league_id] = f"{type(exc).__name__}: {str(exc)[:240]}"
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    return build_season_membership_report(responses, errors, season)


def main() -> int:
    if not (os.getenv("APISPORTS_API_KEY") or os.getenv("API_FOOTBALL_KEY")):
        raise SystemExit("API-Football credential is not configured.")
    report = audit_live_api_football_season_membership()
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        key: report[key] for key in (
            "checked_at", "read_only", "requested_season_year",
            "suspect_records_examined", "suspect_records_returned_by_provider",
            "suspect_records_absent_from_successful_responses",
            "provider_links_created", "provider_scope_fields_updated",
        )
    } | {"competitions": [
        {
            key: row.get(key) for key in (
                "competition", "league_provider_id", "provider_team_rows_returned",
                "suspect_team_rows_expected", "suspect_ids_returned",
                "suspect_ids_absent_from_response", "status", "error",
            )
        } for row in report["competitions"]
    ]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
