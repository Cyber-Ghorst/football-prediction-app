"""Additive LiveScoreFootball standings evidence staging for Layer 12.

Standings observations are stored independently of provider_source_entities so
they cannot overwrite fixture-participant raw_payload rows. This module never
creates canonical identities or provider links.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from psycopg.types.json import Jsonb

from livescore_football import LiveScoreFootballClient
from provider_data_storage import _connect
from provider_roster_collection import collect_livescore_season_standings

SEASON_YEAR = 2026
TARGETS = (
    {"name": "German Bundesliga", "country": "Germany", "slug": "ger.1"},
    {"name": "French Ligue 1", "country": "France", "slug": "fra.1"},
)
REPORT = Path("livescore-standings-evidence-stage-report.json")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS provider_source_team_evidence_observations (
    provider TEXT NOT NULL,
    evidence_method TEXT NOT NULL,
    competition_provider_id TEXT NOT NULL,
    requested_season_parameter TEXT NOT NULL,
    provider_team_id TEXT NOT NULL,
    team_name TEXT NOT NULL,
    season_label TEXT NOT NULL,
    evidence_complete BOOLEAN NOT NULL DEFAULT FALSE,
    source_endpoint TEXT NOT NULL,
    source_retrieved_at TIMESTAMPTZ NOT NULL,
    provenance JSONB NOT NULL,
    raw_response JSONB NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (
        provider, evidence_method, competition_provider_id,
        requested_season_parameter, provider_team_id
    )
);
CREATE INDEX IF NOT EXISTS provider_source_team_evidence_scope_idx
    ON provider_source_team_evidence_observations
       (provider, competition_provider_id, season_label, evidence_method);
"""


def build_standings_observation_rows(
    observation: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Expand a validated standings observation into one row per provider team."""
    if observation.get("provider") != "livescore_football":
        raise ValueError("Only LiveScoreFootball standings observations are accepted.")
    if observation.get("team_evidence_method") != "season_standings":
        return []
    league = observation.get("league") or {}
    returned = observation.get("provider_returned_season") or {}
    season = str(observation.get("season") or "")
    competition_id = str(league.get("id") or "")
    requested = str(observation.get("requested_season_parameter") or "")
    endpoint = str(observation.get("source_endpoint") or "")
    retrieved_at = str(observation.get("source_retrieved_at") or "")
    payload = observation.get("provider_payload")
    if not all((competition_id, season, requested, endpoint, retrieved_at)):
        raise ValueError("Standings provenance is incomplete.")
    if requested != str(SEASON_YEAR) or season != requested:
        raise ValueError("Only explicitly requested 2026/27 standings evidence may be staged.")
    if not isinstance(payload, Mapping):
        raise ValueError("Original LiveScoreFootball response is missing.")
    if observation.get("status") != "collected" or observation.get("team_evidence_complete") is not True:
        return []
    child_id = returned.get("child_id")
    child_label = returned.get("child_label")
    competition_season = returned.get("competition_season")
    standings_season = returned.get("standings_season")
    expected_labels = (f"{SEASON_YEAR}/{str(SEASON_YEAR + 1)[-2:]}", f"{SEASON_YEAR}-{str(SEASON_YEAR + 1)[-2:]}")
    if (
        child_id is None or not child_label
        or str(competition_season) != requested
        or str(standings_season) != requested
        or not any(label in str(child_label) for label in expected_labels)
    ):
        raise ValueError("Returned competition, unique child label and standings season provenance must agree.")
    # Re-validate the retained raw response rather than trusting detached metadata.
    if payload.get("season") is None or str(payload.get("season")) != requested:
        raise ValueError("Original response top-level season does not match the requested season.")
    children = payload.get("children")
    if not isinstance(children, list):
        raise ValueError("Original response has no competition-season children.")
    matching_children = []
    expected_labels = (f"{SEASON_YEAR}/{str(SEASON_YEAR + 1)[-2:]}", f"{SEASON_YEAR}-{str(SEASON_YEAR + 1)[-2:]}")
    for child in children:
        if not isinstance(child, Mapping) or str(child.get("id")) != str(child_id):
            continue
        child_label_raw = " ".join(str(child.get(key) or "") for key in ("name", "abbreviation"))
        standings_raw = child.get("standings")
        if (
            any(label in child_label_raw for label in expected_labels)
            and isinstance(standings_raw, Mapping)
            and str(standings_raw.get("season")) == requested
        ):
            matching_children.append((child, standings_raw))
    if len(matching_children) != 1:
        raise ValueError("Original response must contain exactly one matching season child.")
    raw_entries = matching_children[0][1].get("entries")
    if not isinstance(raw_entries, list):
        raise ValueError("Original response standings entries are missing.")
    raw_teams = []
    for entry in raw_entries:
        if not isinstance(entry, Mapping):
            continue
        team = entry.get("team")
        if isinstance(team, Mapping):
            raw_teams.append({
                "id": str(team.get("id") or ""),
                "name": str(team.get("name") or "").strip().casefold(),
            })
    teams = observation.get("teams") or []
    if len(teams) != 18:
        raise ValueError("Expected exactly 18 unique standings teams for each target competition.")
    ids = [str(team.get("id") or "") for team in teams]
    names = [str(team.get("name") or "").strip().casefold() for team in teams]
    if any(not value for value in ids + names) or len(set(ids)) != 18 or len(set(names)) != 18:
        raise ValueError("Standings roster contains missing or duplicate team identities.")
    raw_ids = [team["id"] for team in raw_teams]
    raw_names = [team["name"] for team in raw_teams]
    if (
        len(raw_teams) != 18
        or len(set(raw_ids)) != 18
        or len(set(raw_names)) != 18
        or set(raw_ids) != set(ids)
        or set(raw_names) != set(names)
    ):
        raise ValueError("Expanded team rows do not match the 18 teams in the preserved raw response.")
    provenance = {
        "provider_competition_id": competition_id,
        "provider_competition_slug": str(league.get("id") or ""),
        "requested_season_parameter": requested,
        "returned_competition_season": competition_season,
        "unique_child_id": child_id,
        "unique_child_label": child_label,
        "nested_standings_season": standings_season,
        "source_endpoint": endpoint,
        "source_retrieved_at": retrieved_at,
        "competition_name": league.get("name"),
        "country": league.get("country"),
        "evidence_method": "season_standings",
        "evidence_complete": True,
    }
    return [{
        "provider": "livescore_football",
        "evidence_method": "season_standings",
        "competition_provider_id": competition_id,
        "requested_season_parameter": requested,
        "provider_team_id": str(team["id"]),
        "team_name": str(team["name"]).strip(),
        "season_label": f"{requested}/{str(int(requested) + 1)[-2:]}",
        "evidence_complete": True,
        "source_endpoint": endpoint,
        "source_retrieved_at": retrieved_at,
        "provenance": {**provenance, "team_raw": team.get("raw") or team},
        "raw_response": payload,
    } for team in teams]


def store_standings_observations(database_url: str, rows: list[Mapping[str, Any]]) -> int:
    """Write only the additive observation table; legacy team rows are never updated."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            for statement in CREATE_TABLE_SQL.split(";"):
                if statement.strip():
                    cursor.execute(statement.strip())
            for row in rows:
                cursor.execute(
                    """INSERT INTO provider_source_team_evidence_observations (
                           provider, evidence_method, competition_provider_id,
                           requested_season_parameter, provider_team_id, team_name,
                           season_label, evidence_complete, source_endpoint,
                           source_retrieved_at, provenance, raw_response
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (
                           provider, evidence_method, competition_provider_id,
                           requested_season_parameter, provider_team_id
                       ) DO UPDATE SET
                           team_name = EXCLUDED.team_name,
                           season_label = EXCLUDED.season_label,
                           evidence_complete = EXCLUDED.evidence_complete,
                           source_endpoint = EXCLUDED.source_endpoint,
                           source_retrieved_at = EXCLUDED.source_retrieved_at,
                           provenance = EXCLUDED.provenance,
                           raw_response = EXCLUDED.raw_response,
                           last_seen_at = NOW()""",
                    (
                        row["provider"], row["evidence_method"], row["competition_provider_id"],
                        row["requested_season_parameter"], row["provider_team_id"], row["team_name"],
                        row["season_label"], row["evidence_complete"], row["source_endpoint"],
                        datetime.fromisoformat(str(row["source_retrieved_at"]).replace("Z", "+00:00")),
                        Jsonb(row["provenance"]), Jsonb(row["raw_response"]),
                    ),
                )
    return len(rows)


def collect_and_stage(database_url: str) -> dict[str, Any]:
    """Fetch both official competition standings and persist only complete observations."""
    client = LiveScoreFootballClient()
    all_rows: list[dict[str, Any]] = []
    competition_counts: dict[str, int] = {}
    try:
        retrieved_at = datetime.now(timezone.utc).isoformat()
        for target in TARGETS:
            observation = collect_livescore_season_standings(
                client, league=target, season_year=SEASON_YEAR, retrieved_at=retrieved_at
            )
            rows = build_standings_observation_rows(observation)
            if len(rows) != 18:
                raise RuntimeError(
                    f"{target['slug']} standings evidence did not validate as 18 unique teams: "
                    f"{observation.get('status')}"
                )
            competition_counts[target["slug"]] = len(rows)
            all_rows.extend(rows)
    finally:
        client.close()
    written = store_standings_observations(database_url, all_rows)
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "provider": "livescore_football",
        "season": "2026/27",
        "evidence_method": "season_standings",
        "competition_team_counts": competition_counts,
        "evidence_rows_upserted": written,
        "fixture_participant_rows_modified": 0,
        "provider_source_entities_modified": 0,
        "canonical_ids_assigned": 0,
        "provider_links_created": 0,
        "promotion_allowed": False,
        "prediction_ledger_touched": False,
        "report": str(REPORT),
    }


def main() -> int:
    report = collect_and_stage(os.getenv("PROVIDER_DATABASE_URL", "").strip())
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
