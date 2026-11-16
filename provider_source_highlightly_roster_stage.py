"""Stage Highlightly competition, season and standings-roster source evidence.

Only provider-native source entities are stored. This does not import fixtures,
create canonical IDs, or approve cross-provider links.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from highlightly import HighlightlyClient
from provider_roster_collection import collect_highlightly_season_roster
from provider_source_repository import store_provider_source_bundle

# Keep this collector focused on the five men's domestic top-flight
# competitions used by the provider-neutral team-scope review. International
# tournaments are intentionally excluded from club-roster evidence.
TARGETS = (
    {"name": "Premier League", "country": "England"},
    {"name": "La Liga", "country": "Spain"},
    {"name": "Serie A", "country": "Italy"},
    {"name": "Bundesliga", "country": "Germany"},
    {"name": "Ligue 1", "country": "France"},
)
SEASON_YEAR = 2026
REPORT = Path("provider-source-highlightly-roster-stage-report.json")


def _country_name(value: Any) -> str | None:
    if isinstance(value, Mapping):
        value = value.get("name") or value.get("countryName")
    return str(value).strip() if value is not None and str(value).strip() else None


def _select_competition(rows: list[dict[str, Any]], target: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str]:
    matches = []
    for row in rows:
        name = str(row.get("name") or row.get("leagueName") or "").strip()
        country = _country_name(row.get("country") or row.get("countryName"))
        if name.casefold() != str(target["name"]).casefold():
            continue
        if target.get("country") and (country or "").casefold() != str(target["country"]).casefold():
            continue
        matches.append(row)
    if len(matches) != 1:
        return None, "not_found" if not matches else "ambiguous_exact_name_country"
    return matches[0], "unique_exact_name_country"


def build_source_entities(rosters: list[Mapping[str, Any]], *, retrieved_at: str | None = None) -> list[dict[str, Any]]:
    entities: dict[tuple[str, str], dict[str, Any]] = {}
    team_competitions: dict[str, set[str]] = {}
    for roster in rosters:
        league = roster.get("league") or {}
        season = roster.get("season") or {}
        competition_id = str(league.get("id") or "").strip()
        competition_name = str(league.get("name") or "").strip()
        country = _country_name(league.get("country"))
        if not competition_id or not competition_name:
            raise ValueError("Highlightly roster lacks competition ID or name.")
        entities[("competition", competition_id)] = {
            "entity_type": "competition",
            "provider_entity_id": competition_id,
            "name": competition_name,
            "country": country,
            "competition_type": league.get("type"),
            "raw_payload": {
                "source": "Highlightly league catalogue",
                "country_from_provider": country,
                "competition_type_from_provider": league.get("type"),
                "raw_league": dict(league),
            },
        }
        native_season_id = str(season.get("id") or "").strip()
        # Highlightly season values such as "2026" are reused across competitions.
        # Scope the source row key by provider competition ID and preserve the
        # native season value separately in the provenance payload.
        season_id = f"{competition_id}:{native_season_id}" if native_season_id else ""
        if season_id:
            entities[("season", season_id)] = {
                "entity_type": "season",
                "provider_entity_id": season_id,
                "name": str(season.get("name") or season_id),
                "season_label": str(season.get("name") or season_id),
                "parent_competition_provider_id": competition_id,
                "start_date": season.get("start_date"),
                "end_date": season.get("end_date"),
                "raw_payload": {
                    "source": "Highlightly league season record",
                    "source_endpoint": "league catalogue seasons",
                    "season_label": str(season.get("name") or season.get("season") or native_season_id),
                    "source_retrieved_at": retrieved_at,
                    "provider_native_season_id": native_season_id,
                    "provider_entity_id_kind": "competition_scoped_composite",
                    "raw_season": dict(season),
                },
            }
        for team in roster.get("teams") or []:
            team_id = str(team.get("id") or "").strip()
            team_name = str(team.get("name") or "").strip()
            if not team_id or not team_name:
                continue
            team_country = _country_name(team.get("country"))
            entities[("team", team_id)] = {
                "entity_type": "team",
                "provider_entity_id": team_id,
                "name": team_name,
                "country": team_country,
                "team_type": team.get("type"),
                "gender_scope": team.get("gender") or team.get("gender_scope"),
                "raw_payload": {
                    "source": "Highlightly league-season standings",
                    "source_endpoint": "standings",
                    "season_label": str(season.get("name") or season.get("season") or native_season_id),
                    "source_retrieved_at": retrieved_at,
                    "competition_provider_id": competition_id,
                    "season_provider_id": season_id or None,
                    "provider_native_season_id": native_season_id or None,
                    "season_window": {"from": season.get("start_date"), "to": season.get("end_date")},
                    "team_evidence_method": roster.get("team_evidence_method"),
                    "roster_observation_complete": bool(roster.get("team_evidence_complete")),
                    "team_evidence_complete": False,
                    "team_country_from_provider": team_country,
                    "gender_from_provider": team.get("gender") or team.get("gender_scope"),
                    "raw_team": team.get("raw") or dict(team),
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


def collect_rosters() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not (
        os.getenv("FREE_FIXTURE_TERMS_ACK_HIGHLIGHTLY", "").strip().casefold()
        in {"1", "true", "yes", "on"}
        and os.getenv("HIGHLIGHTLY_NON_BETTING_USE_CONFIRMED", "").strip().casefold()
        in {"1", "true", "yes", "on"}
    ):
        return [], [{"status": "held", "reason": "Highlightly terms and non-betting-use acknowledgements are required."}]
    client = HighlightlyClient()
    rosters = []
    outcomes = []
    try:
        for target in TARGETS:
            try:
                params = {"leagueName": target["name"], "limit": 20, "offset": 0}
                if target.get("country"):
                    params["countryName"] = target["country"]
                rows = client.leagues(**params)
                league, selection = _select_competition(rows, target)
                if league is None:
                    outcomes.append({"target": target, "status": selection})
                    continue
                season_rows = league.get("seasons") if isinstance(league.get("seasons"), list) else []
                season = next((row for row in season_rows
                               if isinstance(row, dict)
                               and str(row.get("season")) == str(SEASON_YEAR)), None)
                if season is None:
                    outcomes.append({"target": target, "status": "season_not_listed",
                                     "competition_provider_id": league.get("id")})
                    continue
                roster = collect_highlightly_season_roster(
                    client, league=league, season=season,
                )
                if not roster.get("teams"):
                    outcomes.append({"target": target, "status": "empty_standings",
                                     "competition_provider_id": league.get("id")})
                    continue
                rosters.append(roster)
                outcomes.append({"target": target, "status": "collected",
                                 "competition_provider_id": league.get("id"),
                                 "season_provider_id": roster["season"].get("id"),
                                 "team_count": len(roster["teams"]),
                                 "rate_limit": dict(client.last_metadata)})
            except Exception as exc:
                outcomes.append({
                    "target": target, "status": "error",
                    "reason": str(exc)[:250], "rate_limit": dict(client.last_metadata),
                })
                if client.last_metadata.get("http_status") == 429:
                    outcomes.append({"status": "remaining_targets_skipped_after_http_429"})
                    break
    finally:
        client.close()
    return rosters, outcomes


def main() -> int:
    database_url = os.getenv("PROVIDER_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("PROVIDER_DATABASE_URL is not configured.")
    rosters, outcomes = collect_rosters()
    retrieved_at = datetime.now(timezone.utc).isoformat()
    entities = build_source_entities(rosters, retrieved_at=retrieved_at)
    counts = {"entities": 0, "fixtures": 0, "statistics": 0}
    if entities:
        counts = store_provider_source_bundle(
            database_url, "highlightly", entities=entities,
            write_scope="provider_source_evidence_only",
        )
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "provider": "highlightly",
        "season": SEASON_YEAR,
        "source_retrieved_at": retrieved_at,
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
