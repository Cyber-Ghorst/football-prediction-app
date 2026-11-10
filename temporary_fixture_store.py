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
    home_team_id TEXT NOT NULL,
    away_team_id TEXT NOT NULL,
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
    home_team_id, away_team_id, home_team, away_team, competition, country, payload, collected_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
ON CONFLICT (fixture_id) DO UPDATE SET
    league_id = EXCLUDED.league_id,
    season_id = EXCLUDED.season_id,
    starting_at = EXCLUDED.starting_at,
    status = EXCLUDED.status,
    home_team_id = EXCLUDED.home_team_id,
    away_team_id = EXCLUDED.away_team_id,
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
        str(home.get("id")),
        str(away.get("id")),
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


def search_temporary_upcoming_fixtures(
    database_url: str,
    *,
    search_term: str = "",
    league_id: str | None = None,
    season_id: str | None = None,
    window_days: int = 7,
    limit: int = 300,
) -> list[dict[str, Any]]:
    """Search only the active Neon staging catalogue within a strict 1–7 day window."""
    if not database_url:
        raise ValueError("DATABASE_URL is required.")
    if isinstance(window_days, bool) or not isinstance(window_days, int) or not 1 <= window_days <= 7:
        raise ValueError("window_days must be an integer from 1 through 7.")
    safe_limit = max(1, min(int(limit), 500))
    clauses = [
        "starting_at > NOW()",
        f"starting_at <= NOW() + INTERVAL '{window_days} days'",
        "LOWER(status) IN ('ns', 'not started', 'scheduled', 'to be played', "
        "'fixture not started', 'not played', 'tbd', '1', "
        "'postponed', 'postponed fixture', 'pst', 'ppd')",
    ]
    params: list[Any] = []
    if league_id:
        clauses.append("league_id = %s")
        params.append(str(league_id))
    if season_id:
        clauses.append("season_id = %s")
        params.append(str(season_id))
    term = str(search_term or "").strip()
    if term:
        clauses.append(
            "(home_team ILIKE %s OR away_team ILIKE %s OR competition ILIKE %s "
            "OR COALESCE(country, '') ILIKE %s)"
        )
        pattern = f"%{term}%"
        params.extend((pattern, pattern, pattern, pattern))
    params.append(safe_limit)
    with psycopg.connect(database_url, connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            # The app may be the first process to touch Neon after deployment,
            # or the collector may not yet have completed its first refresh.
            # Ensure the staging table exists before querying it so an empty
            # catalogue is reported as empty rather than as UndefinedTable.
            cursor.execute(CREATE_TABLE_SQL)
            cursor.execute(
                f"""
                SELECT fixture_id, season_id, league_id, home_team_id, away_team_id,
                       home_team, away_team, competition, country, starting_at,
                       status, payload->>'venue' AS venue, 'sportmonks' AS source_provider,
                       payload->>'updated_at' AS provider_updated_at
                FROM upcoming_fixture_staging
                WHERE {" AND ".join(clauses)}
                ORDER BY starting_at ASC, fixture_id ASC
                LIMIT %s
                """,
                tuple(params),
            )
            rows = cursor.fetchall()
            columns = (
                "fixture_id", "season_id", "league_id", "home_team_id", "away_team_id",
                "home_team", "away_team", "competition", "country", "starting_at",
                "status", "venue", "source_provider", "provider_updated_at",
            )
            return [dict(zip(columns, row)) for row in rows]
