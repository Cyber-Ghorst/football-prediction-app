"""Temporary Neon staging for the active upcoming-fixture catalogue.

This table is deliberately separate from prediction_ledger. Each successful
full refresh replaces the active rolling-window set: completed, cancelled,
expired and otherwise absent fixtures are removed; rescheduled fixtures keep
the same provider fixture ID and are updated in place.
"""
from __future__ import annotations

from typing import Any
import json

import psycopg
from psycopg.types.json import Jsonb


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS upcoming_fixture_staging (
    fixture_id TEXT PRIMARY KEY,
    league_id TEXT NOT NULL,
    season_id TEXT NOT NULL,
    starting_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    competition TEXT NOT NULL,
    country TEXT,
    payload JSONB NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

UPSERT_SQL = """
INSERT INTO upcoming_fixture_staging (
    fixture_id, league_id, season_id, starting_at, status,
    home_team, away_team, competition, country, payload, collected_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
ON CONFLICT (fixture_id) DO UPDATE SET
    league_id = EXCLUDED.league_id,
    season_id = EXCLUDED.season_id,
    starting_at = EXCLUDED.starting_at,
    status = EXCLUDED.status,
    home_team = EXCLUDED.home_team,
    away_team = EXCLUDED.away_team,
    competition = EXCLUDED.competition,
    country = EXCLUDED.country,
    payload = EXCLUDED.payload,
    collected_at = NOW()
"""


def _name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("short_name") or "").strip()
    return str(value or "").strip()


def _prepare(fixture: dict[str, Any]) -> tuple[Any, ...]:
    league = fixture.get("league") if isinstance(fixture.get("league"), dict) else {}
    season = fixture.get("season") if isinstance(fixture.get("season"), dict) else {}
    participants = fixture.get("participants") or []
    home = away = None
    for participant in participants:
        if not isinstance(participant, dict):
            continue
        meta = participant.get("meta") if isinstance(participant.get("meta"), dict) else {}
        location = str(meta.get("location") or participant.get("location") or "").casefold()
        if location == "home":
            home = participant
        elif location == "away":
            away = participant
    if not home or not away:
        raise ValueError("A staged fixture must have both home and away participants.")
    kickoff = fixture.get("_collector_kickoff_utc") or fixture.get("starting_at")
    if not kickoff:
        raise ValueError("A staged fixture must have a confirmed kickoff.")
    return (
        f"sportmonks:{fixture['id']}",
        str(fixture.get("league_id") or league.get("id") or ""),
        str(fixture.get("season_id") or season.get("id") or ""),
        kickoff,
        _name(fixture.get("state") or fixture.get("status")) or str(fixture.get("state_id") or "scheduled"),
        _name(home),
        _name(away),
        _name(league) or "Unknown competition",
        _name(league.get("country")),
        Jsonb(json.loads(json.dumps(fixture, default=str))),
    )


def sync_temporary_upcoming_fixtures(
    database_url: str,
    fixtures: list[dict[str, Any]],
) -> dict[str, int]:
    """Atomically refresh Neon staging; never read, update or delete ledger rows."""
    if not database_url:
        raise ValueError("DATABASE_URL is required for temporary fixture staging.")
    if not isinstance(fixtures, list):
        raise ValueError("fixtures must be a list.")
    prepared = [_prepare(row) for row in fixtures]
    ids = [row[0] for row in prepared]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate provider fixture IDs cannot be staged.")
    with psycopg.connect(database_url, connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)
            if prepared:
                cursor.executemany(UPSERT_SQL, prepared)
                cursor.execute(
                    "DELETE FROM upcoming_fixture_staging WHERE NOT (fixture_id = ANY(%s))",
                    (ids,),
                )
            else:
                cursor.execute("DELETE FROM upcoming_fixture_staging")
            removed_count = max(0, int(cursor.rowcount or 0))
            cursor.execute("SELECT COUNT(*) FROM upcoming_fixture_staging")
            active_count = int(cursor.fetchone()[0])
    return {
        "fixtures_upserted": len(prepared),
        "fixtures_removed": removed_count,
        "active_fixtures": active_count,
        "prediction_ledger_modified": 0,
    }
