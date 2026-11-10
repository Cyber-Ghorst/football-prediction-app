"""Stage normalized OpenScores fixtures and reconcile only verified identities.

This store never inserts into or updates canonical football_fixtures. It only
writes provider observations and, when uniquely matched through explicit entity
crosswalks, records an OpenScores fixture crosswalk.
"""
from __future__ import annotations

import uuid
from typing import Any

from psycopg.types.json import Jsonb

from provider_data_storage import _connect


CREATE_OPENSCORES_OBSERVATIONS_SQL = """
CREATE TABLE IF NOT EXISTS provider_fixture_observations (
    observation_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_fixture_id TEXT NOT NULL,
    provider_league_id TEXT NOT NULL,
    provider_season_id TEXT NOT NULL,
    provider_home_team_id TEXT NOT NULL,
    provider_away_team_id TEXT NOT NULL,
    home_team_name TEXT NOT NULL,
    away_team_name TEXT NOT NULL,
    kickoff_utc TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    home_goals INTEGER,
    away_goals INTEGER,
    source_ids JSONB NOT NULL DEFAULT '{}'::JSONB,
    retrieved_at_utc TIMESTAMPTZ,
    raw_payload JSONB NOT NULL,
    reconciliation_status TEXT NOT NULL DEFAULT 'pending_entity_mapping',
    canonical_fixture_id TEXT,
    reconciliation_note TEXT,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, provider_fixture_id)
);
CREATE INDEX IF NOT EXISTS provider_fixture_observations_status_idx
    ON provider_fixture_observations (provider, reconciliation_status, kickoff_utc);
"""


def ensure_observation_store(database_url: str) -> None:
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required")
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            for statement in CREATE_OPENSCORES_OBSERVATIONS_SQL.split(";"):
                if statement.strip():
                    cursor.execute(statement)


def upsert_openscores_observations(
    database_url: str, fixtures: list[dict[str, Any]]
) -> dict[str, int]:
    """Persist normalized provider observations only; no canonical writes."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required")
    if not isinstance(fixtures, list):
        raise ValueError("fixtures must be a list")
    ensure_observation_store(database_url)
    rows: dict[str, tuple[Any, ...]] = {}
    for fixture in fixtures:
        if not isinstance(fixture, dict) or fixture.get("provider") != "openscores":
            continue
        required = (
            "provider_fixture_id", "provider_league_id", "provider_season_id",
            "provider_home_team_id", "provider_away_team_id", "home_team_name",
            "away_team_name", "kickoff_utc", "status",
        )
        if any(fixture.get(key) in (None, "") for key in required):
            continue
        provider_fixture_id = str(fixture["provider_fixture_id"])
        observation_id = str(uuid.uuid5(
            uuid.NAMESPACE_URL, f"openscores:fixture-observation:{provider_fixture_id}"
        ))
        rows[provider_fixture_id] = (
            observation_id, "openscores", provider_fixture_id,
            str(fixture["provider_league_id"]), str(fixture["provider_season_id"]),
            str(fixture["provider_home_team_id"]), str(fixture["provider_away_team_id"]),
            str(fixture["home_team_name"]), str(fixture["away_team_name"]),
            fixture["kickoff_utc"], str(fixture["status"]),
            fixture.get("home_goals"), fixture.get("away_goals"),
            Jsonb(fixture.get("source_ids") or {}),
            fixture.get("retrieved_at_utc"), Jsonb(fixture.get("raw_payload") or {}),
            str(fixture.get("reconciliation_status") or "pending_entity_mapping"),
        )

    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            for row in rows.values():
                cursor.execute(
                    """
                    INSERT INTO provider_fixture_observations (
                        observation_id, provider, provider_fixture_id,
                        provider_league_id, provider_season_id,
                        provider_home_team_id, provider_away_team_id,
                        home_team_name, away_team_name, kickoff_utc, status,
                        home_goals, away_goals, source_ids, retrieved_at_utc,
                        raw_payload, reconciliation_status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (provider, provider_fixture_id) DO UPDATE SET
                        provider_league_id = excluded.provider_league_id,
                        provider_season_id = excluded.provider_season_id,
                        provider_home_team_id = excluded.provider_home_team_id,
                        provider_away_team_id = excluded.provider_away_team_id,
                        home_team_name = excluded.home_team_name,
                        away_team_name = excluded.away_team_name,
                        kickoff_utc = excluded.kickoff_utc,
                        status = excluded.status,
                        home_goals = excluded.home_goals,
                        away_goals = excluded.away_goals,
                        source_ids = excluded.source_ids,
                        retrieved_at_utc = excluded.retrieved_at_utc,
                        raw_payload = excluded.raw_payload,
                        reconciliation_status = CASE
                            WHEN provider_fixture_observations.canonical_fixture_id IS NOT NULL
                            THEN provider_fixture_observations.reconciliation_status
                            ELSE excluded.reconciliation_status
                        END,
                        last_seen_at = NOW()
                    """,
                    row,
                )
    return {"observations_upserted": len(rows), "canonical_fixtures_written": 0}


def reconcile_openscores_observations(
    database_url: str, *, kickoff_tolerance_seconds: int = 300,
    limit: int = 1000,
) -> dict[str, int]:
    """Match observations only via verified entity crosswalks and exact fixture fingerprint."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required")
    if isinstance(kickoff_tolerance_seconds, bool) or not isinstance(kickoff_tolerance_seconds, int) or kickoff_tolerance_seconds < 0:
        raise ValueError("kickoff_tolerance_seconds must be a non-negative integer")
    safe_limit = max(1, min(int(limit), 5000))
    counts = {
        "observations_checked": 0,
        "matched": 0,
        "pending_entity_mapping": 0,
        "no_canonical_fixture_match": 0,
        "ambiguous_canonical_fixture_match": 0,
        "fixture_crosswalk_conflict": 0,
    }
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT observation_id, provider_fixture_id, provider_league_id,
                       provider_season_id, provider_home_team_id, provider_away_team_id,
                       kickoff_utc
                FROM provider_fixture_observations
                WHERE provider = 'openscores'
                  AND reconciliation_status NOT IN ('matched')
                ORDER BY kickoff_utc
                LIMIT %s
                """,
                (safe_limit,),
            )
            observations = cursor.fetchall()

            for row in observations:
                (observation_id, provider_fixture_id, league_pid, season_pid,
                 home_pid, away_pid, kickoff) = row
                counts["observations_checked"] += 1
                cursor.execute(
                    """
                    SELECT entity_type, provider_entity_id, canonical_entity_id
                    FROM provider_entity_links
                    WHERE provider = 'openscores'
                      AND (entity_type, provider_entity_id) IN (
                        ('league', %s), ('season', %s), ('team', %s), ('team', %s)
                      )
                    """,
                    (str(league_pid), str(season_pid), str(home_pid), str(away_pid)),
                )
                links = {(item[0], str(item[1])): str(item[2]) for item in cursor.fetchall()}
                league_id = links.get(("league", str(league_pid)))
                season_id = links.get(("season", str(season_pid)))
                home_id = links.get(("team", str(home_pid)))
                away_id = links.get(("team", str(away_pid)))
                if not all((league_id, season_id, home_id, away_id)):
                    cursor.execute(
                        """
                        UPDATE provider_fixture_observations
                        SET reconciliation_status = 'pending_entity_mapping',
                            canonical_fixture_id = NULL,
                            reconciliation_note = 'One or more verified entity crosswalks are missing'
                        WHERE observation_id = %s
                        """,
                        (observation_id,),
                    )
                    counts["pending_entity_mapping"] += 1
                    continue

                cursor.execute(
                    """
                    SELECT fixture_id
                    FROM football_fixtures
                    WHERE league_id = %s AND season_id = %s
                      AND home_team_id = %s AND away_team_id = %s
                      AND starting_at IS NOT NULL
                      AND ABS(EXTRACT(EPOCH FROM (starting_at - %s))) <= %s
                    ORDER BY ABS(EXTRACT(EPOCH FROM (starting_at - %s)))
                    LIMIT 2
                    """,
                    (league_id, season_id, home_id, away_id, kickoff,
                     kickoff_tolerance_seconds, kickoff),
                )
                matches = [str(item[0]) for item in cursor.fetchall()]
                if len(matches) == 0:
                    status, note = "no_canonical_fixture_match", "No canonical fixture matched verified IDs and kickoff tolerance"
                    counts["no_canonical_fixture_match"] += 1
                elif len(matches) > 1:
                    status, note = "ambiguous_canonical_fixture_match", "More than one canonical fixture matched the fingerprint"
                    counts["ambiguous_canonical_fixture_match"] += 1
                else:
                    canonical_fixture_id = matches[0]
                    cursor.execute(
                        """
                        SELECT canonical_entity_id
                        FROM provider_entity_links
                        WHERE provider = 'openscores' AND entity_type = 'fixture'
                          AND provider_entity_id = %s
                        """,
                        (str(provider_fixture_id),),
                    )
                    existing = cursor.fetchone()
                    if existing and str(existing[0]) != canonical_fixture_id:
                        status, note = "fixture_crosswalk_conflict", "Existing fixture crosswalk points to a different canonical fixture"
                        counts["fixture_crosswalk_conflict"] += 1
                    else:
                        link_id = str(uuid.uuid5(
                            uuid.NAMESPACE_URL, f"openscores:fixture:{provider_fixture_id}"
                        ))
                        cursor.execute(
                            """
                            INSERT INTO provider_entity_links (
                                link_id, provider, entity_type, provider_entity_id,
                                canonical_entity_id
                            ) VALUES (%s, 'openscores', 'fixture', %s, %s)
                            ON CONFLICT (provider, entity_type, provider_entity_id)
                            DO UPDATE SET last_seen_at = NOW()
                            """,
                            (link_id, str(provider_fixture_id), canonical_fixture_id),
                        )
                        status, note = "matched", "Unique canonical fixture matched via verified entity IDs and kickoff"
                        counts["matched"] += 1
                        cursor.execute(
                            """
                            UPDATE provider_fixture_observations
                            SET reconciliation_status = %s, canonical_fixture_id = %s,
                                reconciliation_note = %s
                            WHERE observation_id = %s
                            """,
                            (status, canonical_fixture_id, note, observation_id),
                        )
                        continue

                cursor.execute(
                    """
                    UPDATE provider_fixture_observations
                    SET reconciliation_status = %s, canonical_fixture_id = NULL,
                        reconciliation_note = %s
                    WHERE observation_id = %s
                    """,
                    (status, note, observation_id),
                )
    return counts
