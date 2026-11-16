"""Stage API-Football catalogue and team roster as provider source evidence.

This uses only competition, season and team catalogue endpoints. It never
imports fixtures/statistics, assigns canonical IDs, or creates cross-provider links.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from api_football import APIFootballClient
from provider_source_repository import store_provider_source_bundle

CATALOGUE_REFERENCE_SEASON = 2026
TARGETS = (
    {"name": "Premier League", "country": "England"},
    {"name": "La Liga", "country": "Spain"},
    {"name": "Serie A", "country": "Italy"},
    {"name": "Bundesliga", "country": "Germany"},
    {"name": "Ligue 1", "country": "France"},
    {"name": "World Cup", "country": "World"},
)
REPORT = Path("provider-source-api-football-roster-stage-report.json")


def _country_name(value: Any) -> str | None:
    if isinstance(value, Mapping):
        value = value.get("name")
    return str(value).strip() if value is not None and str(value).strip() else None


def _select_competition(rows: list[dict[str, Any]], target: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str]:
    matches = []
    for row in rows:
        league = row.get("league") if isinstance(row.get("league"), Mapping) else {}
        country = _country_name(row.get("country"))
        if str(league.get("name") or "").strip().casefold() != str(target["name"]).casefold():
            continue
        if (country or "").casefold() != str(target["country"]).casefold():
            continue
        matches.append(row)
    if len(matches) != 1:
        return None, "not_found" if not matches else "ambiguous_exact_name_country"
    return matches[0], "unique_exact_name_country"


def build_source_entities(competitions: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    entities: dict[tuple[str, str], dict[str, Any]] = {}
    team_competitions: dict[str, set[str]] = {}
    for item in competitions:
        league = item.get("league") if isinstance(item.get("league"), Mapping) else {}
        country = _country_name(item.get("country"))
        competition_id = str(league.get("id") or "").strip()
        competition_name = str(league.get("name") or "").strip()
        if not competition_id or not competition_name:
            raise ValueError("API-Football competition lacks provider ID or name.")
        entities[("competition", competition_id)] = {
            "entity_type": "competition",
            "provider_entity_id": competition_id,
            "name": competition_name,
            "country": country,
            "competition_type": league.get("type"),
            "raw_payload": {
                "source": "API-Football leagues catalogue",
                "country_from_provider": country,
                "competition_type_from_provider": league.get("type"),
                "raw_league": dict(league),
            },
        }
        season = next((row for row in item.get("seasons", [])
                       if isinstance(row, Mapping)
                       and str(row.get("year")) == str(CATALOGUE_REFERENCE_SEASON)), None)
        if season is None:
            continue
        native_season_id = str(season.get("year"))
        # API-Football season years repeat across competitions; retain a scoped key.
        season_id = f"{competition_id}:{native_season_id}"
        entities[("season", season_id)] = {
            "entity_type": "season",
            "provider_entity_id": season_id,
            "name": native_season_id,
            "season_label": native_season_id,
            "parent_competition_provider_id": competition_id,
            "start_date": season.get("start"),
            "end_date": season.get("end"),
            "raw_payload": {
                "source": "API-Football league season catalogue",
                "provider_native_season_year": season.get("year"),
                "provider_entity_id_kind": "competition_scoped_composite",
                "raw_season": dict(season),
            },
        }
        for team_row in item.get("teams") or []:
            team = team_row.get("team") if isinstance(team_row, Mapping) and isinstance(team_row.get("team"), Mapping) else {}
            team_id = str(team.get("id") or "").strip()
            team_name = str(team.get("name") or "").strip()
            if not team_id or not team_name:
                continue
            team_country = _country_name(team.get("country"))
            national_flag = team.get("national")
            team_type = "national_team" if national_flag is True else (
                "club" if national_flag is False else None
            )
            entities[("team", team_id)] = {
                "entity_type": "team",
                "provider_entity_id": team_id,
                "name": team_name,
                "country": team_country,
                "team_type": team_type,
                "raw_payload": {
                    "source": "API-Football league-season teams endpoint",
                    "team_evidence_method": "provider_league_season_team_catalogue",
                    "catalogue_reference_season": CATALOGUE_REFERENCE_SEASON,
                    "team_evidence_complete": False,
                    "team_national_flag_from_provider": national_flag,
                    "team_country_from_provider": team_country,
                    "competition_provider_ids": [],
                    "raw_team": dict(team),
                },
            }
            team_competitions.setdefault(team_id, set()).add(competition_id)
    output = []
    for (kind, entity_id), row in entities.items():
        if kind == "team":
            row["raw_payload"]["competition_provider_ids"] = sorted(
                team_competitions.get(entity_id, set())
            )
        output.append(row)
    return output


def collect_competitions() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    client = APIFootballClient()
    outcomes = []
    collected = []
    try:
        rows = client.leagues(season=CATALOGUE_REFERENCE_SEASON)
        for target in TARGETS:
            selected, status = _select_competition(rows, target)
            if selected is None:
                outcomes.append({"target": target, "status": status})
                continue
            league = selected.get("league") or {}
            season = next((row for row in selected.get("seasons", [])
                           if isinstance(row, Mapping)
                           and str(row.get("year")) == str(CATALOGUE_REFERENCE_SEASON)), None)
            if season is None:
                outcomes.append({"target": target, "status": "season_not_listed",
                                 "competition_provider_id": league.get("id")})
                continue
            try:
                team_rows = client.teams(int(league["id"]), CATALOGUE_REFERENCE_SEASON)
            except Exception as exc:
                outcomes.append({"target": target, "status": "team_roster_error",
                                 "competition_provider_id": league.get("id"),
                                 "reason": str(exc)[:250]})
                continue
            collected.append({**selected, "teams": team_rows})
            outcomes.append({"target": target, "status": "collected",
                             "competition_provider_id": league.get("id"),
                             "season_year": CATALOGUE_REFERENCE_SEASON,
                             "team_count": len(team_rows)})
    finally:
        client.session.close()
    return collected, outcomes


def main() -> int:
    database_url = os.getenv("PROVIDER_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("PROVIDER_DATABASE_URL is not configured.")
    try:
        competitions, outcomes = collect_competitions()
    except Exception as exc:
        competitions, outcomes = [], [{"status": "provider_error", "reason": str(exc)[:250]}]
    entities = build_source_entities(competitions)
    counts = {"entities": 0, "fixtures": 0, "statistics": 0}
    if entities:
        counts = store_provider_source_bundle(
            database_url, "api_football", entities=entities,
            write_scope="provider_source_evidence_only",
        )
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "provider": "api_football",
        "season_year": CATALOGUE_REFERENCE_SEASON,
        "competition_outcomes": outcomes,
        "source_entities_written": counts["entities"],
        "source_fixtures_written": counts["fixtures"],
        "source_statistics_written": counts["statistics"],
        "canonical_entities_written": 0,
        "provider_links_written": 0,
        "fixtures_ingested": 0,
        "prediction_model_modified": False,
        "prediction_ledger_touched": False,
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
