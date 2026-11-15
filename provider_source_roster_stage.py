"""Stage season-window LiveScore roster observations as provider source evidence.

Only competition and team source entities are stored. No fixtures, season IDs,
canonical entities, cross-provider links, predictions, or ledger rows are written.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from livescore_football import LiveScoreFootballClient
from provider_roster_collection import collect_livescore_season_participants
from provider_source_repository import store_provider_source_bundle

SEASON_YEAR = 2026
SEASON_START = "2026-08-01"
SEASON_END = "2027-05-31"
TARGETS = (
    {"name": "German Bundesliga", "country": "Germany", "slug": "ger.1"},
    {"name": "French Ligue 1", "country": "France", "slug": "fra.1"},
)
REPORT = Path("provider-source-roster-stage-report.json")


def build_source_entities(rosters: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Convert observed catalogue/roster records into provider-native source rows."""
    entities: dict[tuple[str, str], dict[str, Any]] = {}
    team_competitions: dict[str, set[str]] = {}
    for roster in rosters:
        league = roster.get("league") or {}
        season = roster.get("season") or {}
        competition_id = str(league.get("id") or "").strip()
        competition_name = str(league.get("name") or "").strip()
        country = str(league.get("country") or "").strip()
        if not competition_id or not competition_name or not country:
            raise ValueError("Roster lacks exact competition ID, name or country.")
        entities[("competition", competition_id)] = {
            "entity_type": "competition",
            "provider_entity_id": competition_id,
            "name": competition_name,
            "country": country,
            "competition_type": league.get("type") or "league",
            "raw_payload": {
                "source": "LiveScoreFootball competition catalogue",
                "season_window": {"year": SEASON_YEAR, "from": SEASON_START, "to": SEASON_END},
            },
        }
        for team in roster.get("teams") or []:
            team_id = str(team.get("id") or "").strip()
            team_name = str(team.get("name") or "").strip()
            if not team_id or not team_name:
                continue
            # Do not substitute competition country for missing team country.
            team_country = str(team.get("country") or "").strip() or None
            entities[("team", team_id)] = {
                "entity_type": "team",
                "provider_entity_id": team_id,
                "name": team_name,
                "country": team_country,
                "raw_payload": {
                    "source": "LiveScoreFootball season-window fixture participants",
                    "competition_provider_ids": [],
                    "season_window": {"year": SEASON_YEAR, "from": SEASON_START, "to": SEASON_END},
                    "team_evidence_method": roster.get("team_evidence_method"),
                    "team_evidence_complete": False,
                    "team_type": team.get("type"),
                    "team_country_from_provider": team_country,
                    "raw_team": team.get("raw") or team,
                },
            }
            team_competitions.setdefault(team_id, set()).add(competition_id)
    output = []
    for (kind, entity_id), row in entities.items():
        if kind == "team":
            row["raw_payload"]["competition_provider_ids"] = sorted(team_competitions.get(entity_id, set()))
        output.append(row)
    return output


def collect_rosters() -> list[dict[str, Any]]:
    client = LiveScoreFootballClient()
    rosters = []
    try:
        catalogue = client.leagues(kind="all", available=False)
        for target in TARGETS:
            matches = [
                row for row in catalogue
                if str(row.get("slug") or "") == target["slug"]
                and str(row.get("name") or "").casefold() == target["name"].casefold()
                and str(row.get("country") or "").casefold() == target["country"].casefold()
                and row.get("active") is True
                and (row.get("coverage") or {}).get("hasData") is True
            ]
            if len(matches) != 1:
                raise RuntimeError(
                    f"Expected one active data-backed catalogue match for {target['slug']}; found {len(matches)}."
                )
            roster = collect_livescore_season_participants(
                client, league=matches[0], season={"year": SEASON_YEAR},
                date_from=SEASON_START, date_to=SEASON_END,
            )
            if not roster.get("teams"):
                raise RuntimeError(f"No team participants returned for {target['slug']}.")
            rosters.append(roster)
    finally:
        client.close()
    return rosters


def main() -> int:
    database_url = os.getenv("PROVIDER_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("PROVIDER_DATABASE_URL is not configured.")
    rosters = collect_rosters()
    entities = build_source_entities(rosters)
    counts = store_provider_source_bundle(
        database_url, "livescore_football", entities=entities,
        write_scope="provider_source_evidence_only",
    )
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "provider": "livescore_football",
        "season_window": {"year": SEASON_YEAR, "from": SEASON_START, "to": SEASON_END},
        "competition_count": len(rosters),
        "observed_team_counts": {
            str((row.get("league") or {}).get("id")): len(row.get("teams") or [])
            for row in rosters
        },
        "source_entities_written": counts["entities"],
        "source_fixtures_written": counts["fixtures"],
        "source_statistics_written": counts["statistics"],
        "canonical_entities_written": 0,
        "provider_links_written": 0,
        "legacy_repository_rows_changed": 0,
        "prediction_model_modified": False,
        "prediction_ledger_touched": False,
        "team_evidence_complete": False,
        "country_inferred_from_competition": False,
        "highlightly_skipped_reason": "Recent Highlightly calls returned HTTP 429; no stale or cached roster was substituted.",
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
