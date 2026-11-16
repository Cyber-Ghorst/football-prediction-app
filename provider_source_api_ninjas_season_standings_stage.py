"""Stage API Ninjas 2026/27 standings as provider-native evidence only.

The request parameter is not treated as proof: every standings row must carry
matching provider-returned league, season and season_label fields.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from api_ninjas import APINinjasClient
from provider_source_repository import store_provider_source_bundle

TARGETS = (
    {"league": "epl", "name": "Premier League"},
    {"league": "laliga", "name": "La Liga"},
    {"league": "bundesliga", "name": "Bundesliga"},
    {"league": "seriea", "name": "Serie A"},
    {"league": "ligue1", "name": "Ligue 1"},
)
TARGET_SEASON = 2026
ACCEPTED_LABELS = {"2026-27", "2026/27"}
REPORT = Path("provider-source-api-ninjas-season-standings-report.json")


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def validate_standings_rows(
    rows: list[Mapping[str, Any]], *, requested_league: str,
    retrieved_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Convert only explicit, internally consistent provider rows to source entities."""
    accepted: dict[str, dict[str, Any]] = {}
    held: list[dict[str, Any]] = []
    conflicted_ids: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            held.append({"row_index": index, "reason": "row_not_object"})
            continue
        team = row.get("team")
        if not isinstance(team, Mapping):
            held.append({"row_index": index, "reason": "missing_team_object"})
            continue
        league = _text(row.get("league")).casefold()
        season = row.get("season")
        label = _text(row.get("season_label"))
        team_id = _text(team.get("team_id"))
        name = _text(team.get("name"))
        reasons = []
        if league != requested_league:
            reasons.append("provider_league_missing_or_mismatched")
        if isinstance(season, bool) or not isinstance(season, int) or season != TARGET_SEASON:
            reasons.append("provider_season_missing_or_mismatched")
        if label not in ACCEPTED_LABELS:
            reasons.append("provider_season_label_missing_or_mismatched")
        if not team_id:
            reasons.append("provider_team_id_missing")
        if not name:
            reasons.append("provider_team_name_missing")
        if _text(row.get("sport")).casefold() != "soccer":
            reasons.append("provider_sport_missing_or_mismatched")
        if reasons:
            held.append({
                "row_index": index, "provider_team_id": team_id or None,
                "team_name": name or None, "provider_league": row.get("league"),
                "provider_season": season, "provider_season_label": label or None,
                "reasons": reasons,
            })
            continue
        candidate = {
            "entity_type": "team",
            "provider_entity_id": team_id,
            "name": name,
            "raw_payload": {
                "source": "API Ninjas soccerstandings",
                "source_endpoint": "/v1/soccerstandings",
                "source_retrieved_at": retrieved_at,
                "requested_league": requested_league,
                "requested_season": TARGET_SEASON,
                "provider_returned_league": league,
                "provider_returned_season": season,
                "provider_returned_season_label": label,
                "team_evidence_method": "season_scoped_standings_row",
                "promotion_allowed": False,
                "raw_standing": dict(row),
            },
        }
        if team_id in conflicted_ids:
            held.append({
                "provider_team_id": team_id,
                "reason": "team_id_already_conflicted_in_competition",
            })
            continue
        previous = accepted.get(team_id)
        if previous and previous["name"] != name:
            accepted.pop(team_id, None)
            conflicted_ids.add(team_id)
            held.append({
                "provider_team_id": team_id,
                "reason": "conflicting_duplicate_team_id_within_competition",
                "names": [previous["name"], name],
            })
        elif previous is None:
            accepted[team_id] = candidate

    return [accepted[key] for key in sorted(accepted)], held


def build_source_entities(
    competition_rows: list[tuple[str, list[Mapping[str, Any]]]],
    *, retrieved_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    entities: dict[tuple[str, str], dict[str, Any]] = {}
    held_all: list[dict[str, Any]] = []
    for league, rows in competition_rows:
        target = next((item for item in TARGETS if item["league"] == league), None)
        if target is None:
            held_all.append({"requested_league": league, "reason": "unexpected_competition"})
            continue
        competition_id = league
        teams, held = validate_standings_rows(
            rows, requested_league=league, retrieved_at=retrieved_at,
        )
        held_all.extend({"requested_league": league, **item} for item in held)
        # Empty, failed, or wholly unverified responses must not create even
        # a provisional competition record.
        if not teams:
            continue
        entities[("competition", competition_id)] = {
            "entity_type": "competition",
            "provider_entity_id": competition_id,
            "name": target["name"],
            "raw_payload": {
                "source": "API Ninjas soccerstandings",
                "source_endpoint": "/v1/soccerstandings",
                "source_retrieved_at": retrieved_at,
                "requested_league": league,
                "competition_evidence_method": "validated_season_standings_rows",
                "promotion_allowed": False,
            },
        }
        season_id = f"{league}:{TARGET_SEASON}"
        entities[("season", season_id)] = {
            "entity_type": "season",
            "provider_entity_id": season_id,
            "name": "2026/27",
            "season_label": "2026/27",
            "parent_competition_provider_id": competition_id,
            "raw_payload": {
                "source": "API Ninjas soccerstandings",
                "source_endpoint": "/v1/soccerstandings",
                "source_retrieved_at": retrieved_at,
                "requested_league": league,
                "requested_season": TARGET_SEASON,
                "provider_returned_season_values": sorted({
                    _text(row.get("season_label")) for row in rows
                    if isinstance(row, Mapping) and row.get("season") == TARGET_SEASON
                    and _text(row.get("season_label")) in ACCEPTED_LABELS
                }),
                "season_evidence_is_row_validated": True,
                "promotion_allowed": False,
            },
        }
        for team in teams:
            raw_provider_team_id = team["provider_entity_id"]
            # The source repository primary key is provider + entity_type +
            # provider_entity_id. Namespace the persisted key by competition
            # while retaining the exact provider ID in provenance.
            team["provider_entity_id"] = f"{league}:{raw_provider_team_id}"
            team["raw_payload"]["provider_team_id"] = raw_provider_team_id
            team["raw_payload"]["competition_provider_id"] = competition_id
            team["raw_payload"]["season_provider_id"] = season_id
            entities[("team", team["provider_entity_id"])] = team
    return list(entities.values()), held_all


def collect_standings(client_factory=APINinjasClient):
    client = client_factory()
    collected = []
    outcomes = []
    try:
        for target in TARGETS:
            try:
                rows = client.standings(
                    league=target["league"], season=TARGET_SEASON,
                )
                collected.append((target["league"], rows))
                outcomes.append({
                    "league": target["league"], "status": "collected" if rows else "empty",
                    "rows_received": len(rows), "request_season": TARGET_SEASON,
                    "rate_limit": dict(client.last_metadata),
                })
            except Exception as exc:
                outcomes.append({
                    "league": target["league"], "status": "provider_error",
                    "reason": str(exc)[:300],
                    "request_season": TARGET_SEASON,
                    "rate_limit": dict(client.last_metadata),
                })
    finally:
        client.close()
    return collected, outcomes


def stage_api_ninjas_season_standings(
    database_url: str, client_factory=APINinjasClient,
) -> dict[str, Any]:
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    retrieved_at = datetime.now(timezone.utc).isoformat()
    collected, outcomes = collect_standings(client_factory)
    entities, held = build_source_entities(collected, retrieved_at=retrieved_at)
    counts = store_provider_source_bundle(
        database_url, "api_ninjas", entities=entities,
        write_scope="provider_source_evidence_only",
    ) if entities else {"entities": 0, "fixtures": 0, "statistics": 0}
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "provider": "api_ninjas",
        "endpoint": "/v1/soccerstandings",
        "request_season": TARGET_SEASON,
        "season_label_acceptance": sorted(ACCEPTED_LABELS),
        "competition_outcomes": outcomes,
        "source_entities_written": counts["entities"],
        "valid_team_candidates": sum(1 for row in entities if row["entity_type"] == "team"),
        "held_rows": len(held),
        "held_samples": held[:50],
        "canonical_entities_written": 0,
        "provider_links_written": 0,
        "fixtures_written": 0,
        "predictions_written": 0,
        "prediction_ledger_touched": False,
        "automatic_promotion": False,
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


def main() -> int:
    stage_api_ninjas_season_standings(
        os.getenv("PROVIDER_DATABASE_URL", "").strip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
