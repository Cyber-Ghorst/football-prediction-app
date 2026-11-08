"""Canonical football data repository schema for CockroachDB.

This module is intentionally isolated from the prediction engine and Neon
prediction ledger. Provider snapshots remain the immutable raw archive;
these tables hold normalized, queryable football entities.
"""
from __future__ import annotations

from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from provider_data_storage import _connect


CREATE_FOOTBALL_REPOSITORY_SQL = """
CREATE TABLE IF NOT EXISTS football_leagues (
    league_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT,
    competition_type TEXT,
    logo_url TEXT,
    source_provider TEXT NOT NULL,
    provider_updated_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload JSONB
);

CREATE TABLE IF NOT EXISTS football_seasons (
    season_id TEXT PRIMARY KEY,
    league_id TEXT NOT NULL,
    name TEXT,
    start_date DATE,
    end_date DATE,
    is_current BOOLEAN,
    source_provider TEXT NOT NULL,
    provider_updated_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload JSONB
);
CREATE INDEX IF NOT EXISTS football_seasons_league_idx
    ON football_seasons (league_id, start_date DESC);

CREATE TABLE IF NOT EXISTS football_teams (
    team_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    short_name TEXT,
    country TEXT,
    logo_url TEXT,
    source_provider TEXT NOT NULL,
    provider_updated_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload JSONB
);
CREATE INDEX IF NOT EXISTS football_teams_name_idx
    ON football_teams (name);

CREATE TABLE IF NOT EXISTS football_fixtures (
    fixture_id TEXT PRIMARY KEY,
    season_id TEXT NOT NULL,
    league_id TEXT NOT NULL,
    home_team_id TEXT NOT NULL,
    away_team_id TEXT NOT NULL,
    starting_at TIMESTAMPTZ,
    status TEXT,
    home_goals INTEGER,
    away_goals INTEGER,
    venue TEXT,
    source_provider TEXT NOT NULL,
    provider_updated_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload JSONB
);
CREATE INDEX IF NOT EXISTS football_fixtures_season_kickoff_idx
    ON football_fixtures (season_id, starting_at);
CREATE INDEX IF NOT EXISTS football_fixtures_home_team_idx
    ON football_fixtures (home_team_id, starting_at DESC);
CREATE INDEX IF NOT EXISTS football_fixtures_away_team_idx
    ON football_fixtures (away_team_id, starting_at DESC);
CREATE INDEX IF NOT EXISTS football_fixtures_league_idx
    ON football_fixtures (league_id, starting_at DESC);

CREATE TABLE IF NOT EXISTS football_fixture_statistics (
    statistic_id TEXT PRIMARY KEY,
    fixture_id TEXT NOT NULL,
    team_id TEXT,
    statistic_type TEXT NOT NULL,
    statistic_value JSONB,
    source_provider TEXT NOT NULL,
    provider_statistic_id TEXT,
    provider_updated_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload JSONB
);
CREATE INDEX IF NOT EXISTS football_fixture_statistics_fixture_idx
    ON football_fixture_statistics (fixture_id, team_id);
CREATE INDEX IF NOT EXISTS football_fixture_statistics_type_idx
    ON football_fixture_statistics (statistic_type);

CREATE TABLE IF NOT EXISTS provider_entity_links (
    link_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    provider_entity_id TEXT NOT NULL,
    canonical_entity_id TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, entity_type, provider_entity_id)
);
CREATE INDEX IF NOT EXISTS provider_entity_links_canonical_idx
    ON provider_entity_links (entity_type, canonical_entity_id);

CREATE TABLE IF NOT EXISTS football_repository_sync_state (
    sync_key TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    last_attempted_at TIMESTAMPTZ,
    last_succeeded_at TIMESTAMPTZ,
    records_received INTEGER NOT NULL DEFAULT 0,
    records_upserted INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'never_run',
    last_error TEXT
);
CREATE INDEX IF NOT EXISTS football_repository_sync_provider_idx
    ON football_repository_sync_state (provider, resource_type, status);
"""


def ensure_football_repository(database_url: str) -> dict[str, Any]:
    """Create the normalized repository tables and return a simple readiness report."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    statements = [
        statement.strip()
        for statement in CREATE_FOOTBALL_REPOSITORY_SQL.split(";")
        if statement.strip()
    ]
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = current_schema()
                  AND table_name IN (
                    'football_leagues',
                    'football_seasons',
                    'football_teams',
                    'football_fixtures',
                    'football_fixture_statistics',
                    'provider_entity_links',
                    'football_repository_sync_state'
                  )
                ORDER BY table_name
                """
            )
            tables = [row[0] for row in cursor.fetchall()]
    expected = 7
    if len(tables) != expected:
        raise RuntimeError(
            f"Football repository schema is incomplete: found {len(tables)} of {expected} tables."
        )
    return {
        "success": True,
        "tables_created_or_verified": tables,
        "table_count": len(tables),
        "note": "Schema is ready; no provider records were imported or modified.",
    }


def repository_table_counts(database_url: str) -> dict[str, int]:
    """Return record counts for canonical tables without exposing stored payloads."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    table_names = (
        "football_leagues",
        "football_seasons",
        "football_teams",
        "football_fixtures",
        "football_fixture_statistics",
        "provider_entity_links",
        "football_repository_sync_state",
    )
    counts: dict[str, int] = {}
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            for table_name in table_names:
                # Table names are a fixed internal allowlist, not user input.
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                counts[table_name] = int(cursor.fetchone()[0])
    return counts



def _provider_id(value: Any) -> str:
    if value is None or str(value).strip() == "":
        raise ValueError("A provider entity ID is required.")
    return f"sportmonks:{str(value).strip()}"


def _nested_name(value: Any) -> str | None:
    if isinstance(value, dict):
        return str(value.get("name") or "").strip() or None
    return str(value).strip() or None if value is not None else None


def _provider_updated_at(row: dict[str, Any]):
    from datetime import datetime
    value = row.get("updated_at")
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _entity_link(cursor, entity_type: str, provider_id: Any, canonical_id: str) -> None:
    import uuid
    provider_entity_id = str(provider_id)
    link_id = str(uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"sportmonks:{entity_type}:{provider_entity_id}",
    ))
    cursor.execute(
        """
        INSERT INTO provider_entity_links
            (link_id, provider, entity_type, provider_entity_id, canonical_entity_id)
        VALUES (%s, 'sportmonks', %s, %s, %s)
        ON CONFLICT (provider, entity_type, provider_entity_id)
        DO UPDATE SET canonical_entity_id = excluded.canonical_entity_id,
                      last_seen_at = NOW()
        """,
        (link_id, entity_type, provider_entity_id, canonical_id),
    )


def _sync_result(cursor, resource_type: str, received: int, upserted: int,
                 status: str = "success", error: str | None = None) -> None:
    sync_key = f"sportmonks:{resource_type}"
    cursor.execute(
        """
        INSERT INTO football_repository_sync_state
            (sync_key, provider, resource_type, last_attempted_at,
             last_succeeded_at, records_received, records_upserted, status, last_error)
        VALUES (%s, 'sportmonks', %s, NOW(),
                CASE WHEN %s = 'success' THEN NOW() ELSE NULL END,
                %s, %s, %s, %s)
        ON CONFLICT (sync_key) DO UPDATE SET
            last_attempted_at = NOW(),
            last_succeeded_at = CASE WHEN excluded.status = 'success'
                                     THEN NOW()
                                     ELSE football_repository_sync_state.last_succeeded_at END,
            records_received = excluded.records_received,
            records_upserted = excluded.records_upserted,
            status = excluded.status,
            last_error = excluded.last_error
        """,
        (sync_key, resource_type, status, received, upserted, status, error),
    )


def import_sportmonks_season(
    database_url: str,
    *,
    league: dict[str, Any],
    season: dict[str, Any],
    teams: list[dict[str, Any]],
    fixtures: list[dict[str, Any]],
) -> dict[str, Any]:
    """Idempotently import one Sportmonks competition season into canonical tables.

    Raw provider snapshots are maintained separately by provider_data_storage.
    This importer writes only to CockroachDB and never accesses the Neon ledger.
    """
    from psycopg.types.json import Jsonb

    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    league_id = _provider_id(league.get("id"))
    season_id = _provider_id(season.get("id"))
    if str(season.get("league_id")) != str(league.get("id")):
        raise ValueError("Selected Sportmonks season does not belong to the selected league.")

    counts = {"leagues": 0, "seasons": 0, "teams": 0, "fixtures": 0, "skipped_fixtures": 0}
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO football_leagues
                    (league_id, name, country, competition_type, logo_url,
                     source_provider, provider_updated_at, raw_payload)
                VALUES (%s, %s, %s, %s, %s, 'sportmonks', %s, %s)
                ON CONFLICT (league_id) DO UPDATE SET
                    name = excluded.name, country = excluded.country,
                    competition_type = excluded.competition_type,
                    logo_url = excluded.logo_url, source_provider = excluded.source_provider,
                    provider_updated_at = excluded.provider_updated_at,
                    collected_at = NOW(), raw_payload = excluded.raw_payload
                """,
                (league_id, str(league.get("name") or "Unknown league"),
                 _nested_name(league.get("country")),
                 _nested_name(league.get("type") or league.get("competition_type")),
                 league.get("image_path") or league.get("logo"),
                 _provider_updated_at(league), Jsonb(league)),
            )
            _entity_link(cursor, "league", league.get("id"), league_id)
            counts["leagues"] = 1

            cursor.execute(
                """
                INSERT INTO football_seasons
                    (season_id, league_id, name, start_date, end_date, is_current,
                     source_provider, provider_updated_at, raw_payload)
                VALUES (%s, %s, %s, %s, %s, %s, 'sportmonks', %s, %s)
                ON CONFLICT (season_id) DO UPDATE SET
                    league_id = excluded.league_id, name = excluded.name,
                    start_date = excluded.start_date, end_date = excluded.end_date,
                    is_current = excluded.is_current, source_provider = excluded.source_provider,
                    provider_updated_at = excluded.provider_updated_at,
                    collected_at = NOW(), raw_payload = excluded.raw_payload
                """,
                (season_id, league_id, str(season.get("name") or ""),
                 season.get("starting_at") or None, season.get("ending_at") or None,
                 season.get("is_current"), _provider_updated_at(season), Jsonb(season)),
            )
            _entity_link(cursor, "season", season.get("id"), season_id)
            counts["seasons"] = 1

            for team in teams:
                if team.get("id") is None or not team.get("name"):
                    continue
                team_id = _provider_id(team["id"])
                cursor.execute(
                    """
                    INSERT INTO football_teams
                        (team_id, name, short_name, country, logo_url,
                         source_provider, provider_updated_at, raw_payload)
                    VALUES (%s, %s, %s, %s, %s, 'sportmonks', %s, %s)
                    ON CONFLICT (team_id) DO UPDATE SET
                        name = excluded.name, short_name = excluded.short_name,
                        country = excluded.country, logo_url = excluded.logo_url,
                        source_provider = excluded.source_provider,
                        provider_updated_at = excluded.provider_updated_at,
                        collected_at = NOW(), raw_payload = excluded.raw_payload
                    """,
                    (team_id, str(team["name"]), team.get("short_code") or team.get("short_name"),
                     _nested_name(team.get("country")), team.get("image_path") or team.get("logo"),
                     _provider_updated_at(team), Jsonb(team)),
                )
                _entity_link(cursor, "team", team["id"], team_id)
                counts["teams"] += 1

            for fixture in fixtures:
                participants = fixture.get("participants")
                if not isinstance(participants, list):
                    participants = []
                home = away = None
                for participant in participants:
                    meta = participant.get("meta") if isinstance(participant, dict) else {}
                    location = str((meta or {}).get("location") or "").lower()
                    if location == "home":
                        home = participant
                    elif location == "away":
                        away = participant
                if (
                    fixture.get("id") is None or not home or not away
                    or home.get("id") is None or away.get("id") is None
                ):
                    counts["skipped_fixtures"] += 1
                    continue
                fixture_season_id = _provider_id(fixture.get("season_id") or season.get("id"))
                fixture_league_id = _provider_id(fixture.get("league_id") or league.get("id"))
                if fixture_season_id != season_id or fixture_league_id != league_id:
                    counts["skipped_fixtures"] += 1
                    continue
                home_id = _provider_id(home.get("id"))
                away_id = _provider_id(away.get("id"))
                if home_id == away_id:
                    counts["skipped_fixtures"] += 1
                    continue
                state = fixture.get("state")
                status = _nested_name(state) or (str(fixture.get("state_id")) if fixture.get("state_id") is not None else None)
                venue = fixture.get("venue")
                scores = fixture.get("scores") if isinstance(fixture.get("scores"), list) else []
                preferred_score_group = None
                for preferred_code in ("CURRENT", "2ND_HALF"):
                    candidates = []
                    for score in scores:
                        if not isinstance(score, dict):
                            continue
                        description = str(score.get("description") or "").upper()
                        score_type = score.get("type") if isinstance(score.get("type"), dict) else {}
                        type_code = str(score_type.get("code") or "").upper()
                        if description == preferred_code or type_code == preferred_code:
                            candidates.append(score)
                    if candidates:
                        preferred_score_group = candidates
                        break
                home_goals = away_goals = None
                if preferred_score_group:
                    by_participant = {}
                    for score in preferred_score_group:
                        value = score.get("score")
                        value = value.get("goals") if isinstance(value, dict) else value
                        try:
                            by_participant[str(score.get("participant_id"))] = int(value)
                        except (TypeError, ValueError):
                            continue
                    home_goals = by_participant.get(str(home.get("id")))
                    away_goals = by_participant.get(str(away.get("id")))
                cursor.execute(
                    """
                    INSERT INTO football_fixtures
                        (fixture_id, season_id, league_id, home_team_id, away_team_id,
                         starting_at, status, home_goals, away_goals, venue,
                         source_provider, provider_updated_at, raw_payload)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            'sportmonks', %s, %s)
                    ON CONFLICT (fixture_id) DO UPDATE SET
                        season_id = excluded.season_id, league_id = excluded.league_id,
                        home_team_id = excluded.home_team_id, away_team_id = excluded.away_team_id,
                        starting_at = excluded.starting_at, status = excluded.status,
                        home_goals = excluded.home_goals, away_goals = excluded.away_goals,
                        venue = excluded.venue, source_provider = excluded.source_provider,
                        provider_updated_at = excluded.provider_updated_at,
                        collected_at = NOW(), raw_payload = excluded.raw_payload
                    """,
                    (_provider_id(fixture["id"]), season_id, league_id, home_id, away_id,
                     fixture.get("starting_at"), status, home_goals, away_goals,
                     _nested_name(venue), _provider_updated_at(fixture), Jsonb(fixture)),
                )
                _entity_link(cursor, "fixture", fixture["id"], _provider_id(fixture["id"]))
                counts["fixtures"] += 1

            _sync_result(cursor, "leagues", 1, counts["leagues"])
            _sync_result(cursor, "seasons", 1, counts["seasons"])
            _sync_result(cursor, "teams", len(teams), counts["teams"])
            _sync_result(cursor, "fixtures", len(fixtures), counts["fixtures"])
    return {
        "provider": "sportmonks",
        "league": league.get("name"),
        "season": season.get("name"),
        "received": {"teams": len(teams), "fixtures": len(fixtures)},
        "upserted": counts,
        "idempotent": True,
        "raw_snapshots_preserved": True,
        "neon_prediction_ledger_modified": False,
    }


def _rows_as_dicts(cursor) -> list[dict[str, Any]]:
    """Convert the current cursor result into ordinary dictionaries."""
    columns = [column.name for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_repository_leagues(database_url: str) -> list[dict[str, Any]]:
    """Read canonical leagues, newest collected first."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT league_id, name, country, competition_type, source_provider,
                       provider_updated_at, collected_at
                FROM football_leagues
                ORDER BY name
                """
            )
            return _rows_as_dicts(cursor)


def get_repository_seasons(
    database_url: str, *, league_id: str | None = None
) -> list[dict[str, Any]]:
    """Read seasons, optionally restricted to one canonical league ID."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            if league_id:
                cursor.execute(
                    """
                    SELECT season_id, league_id, name, start_date, end_date,
                           is_current, source_provider, provider_updated_at, collected_at
                    FROM football_seasons
                    WHERE league_id = %s
                    ORDER BY start_date DESC NULLS LAST, name DESC
                    """,
                    (league_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT season_id, league_id, name, start_date, end_date,
                           is_current, source_provider, provider_updated_at, collected_at
                    FROM football_seasons
                    ORDER BY start_date DESC NULLS LAST, name DESC
                    """
                )
            return _rows_as_dicts(cursor)


def get_repository_teams(
    database_url: str,
    *,
    season_id: str | None = None,
    league_id: str | None = None,
) -> list[dict[str, Any]]:
    """Read teams, optionally limited to teams appearing in a season or league."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    if season_id and league_id:
        raise ValueError("Pass season_id or league_id, not both.")
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            if season_id:
                cursor.execute(
                    """
                    SELECT DISTINCT t.team_id, t.name, t.short_name, t.country,
                           t.source_provider, t.provider_updated_at, t.collected_at
                    FROM football_teams AS t
                    JOIN football_fixtures AS f
                      ON f.home_team_id = t.team_id OR f.away_team_id = t.team_id
                    WHERE f.season_id = %s
                    ORDER BY t.name
                    """,
                    (season_id,),
                )
            elif league_id:
                cursor.execute(
                    """
                    SELECT DISTINCT t.team_id, t.name, t.short_name, t.country,
                           t.source_provider, t.provider_updated_at, t.collected_at
                    FROM football_teams AS t
                    JOIN football_fixtures AS f
                      ON f.home_team_id = t.team_id OR f.away_team_id = t.team_id
                    WHERE f.league_id = %s
                    ORDER BY t.name
                    """,
                    (league_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT team_id, name, short_name, country, source_provider,
                           provider_updated_at, collected_at
                    FROM football_teams
                    ORDER BY name
                    """
                )
            return _rows_as_dicts(cursor)


def get_repository_fixtures(
    database_url: str,
    *,
    season_id: str | None = None,
    league_id: str | None = None,
    team_id: str | None = None,
    upcoming_only: bool = False,
    completed_only: bool = False,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Read fixtures with safe optional filters and a bounded result size.

    completed_only deliberately requires both a recognized completed status
    and non-null exact scores; merely having a score is not sufficient.
    """
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    if season_id and league_id:
        raise ValueError("Pass season_id or league_id, not both.")
    if upcoming_only and completed_only:
        raise ValueError("A fixture query cannot be both upcoming and completed.")
    safe_limit = max(1, min(int(limit), 2000))
    clauses: list[str] = []
    params: list[Any] = []
    if season_id:
        clauses.append("season_id = %s")
        params.append(season_id)
    if league_id:
        clauses.append("league_id = %s")
        params.append(league_id)
    if team_id:
        clauses.append("(home_team_id = %s OR away_team_id = %s)")
        params.extend((team_id, team_id))
    if upcoming_only:
        clauses.append("starting_at >= NOW()")
    if completed_only:
        clauses.append(
            "LOWER(COALESCE(status, '')) IN "
            "('finished', 'complete', 'completed', 'ft', 'full time')"
        )
        clauses.append("home_goals IS NOT NULL AND away_goals IS NOT NULL")
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(safe_limit)
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT fixture_id, season_id, league_id, home_team_id, away_team_id,
                       starting_at, status, home_goals, away_goals, venue,
                       source_provider, provider_updated_at, collected_at
                FROM football_fixtures
                {where_sql}
                ORDER BY starting_at DESC NULLS LAST
                LIMIT %s
                """,
                tuple(params),
            )
            return _rows_as_dicts(cursor)


def get_repository_team_history(
    database_url: str,
    team_id: str,
    *,
    before_datetime: Any = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return the latest verified completed fixtures for one canonical team ID."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    if not team_id:
        raise ValueError("A canonical team_id is required.")
    safe_limit = max(1, min(int(limit), 50))
    clauses = [
        "(home_team_id = %s OR away_team_id = %s)",
        "LOWER(COALESCE(status, '')) IN "
        "('finished', 'complete', 'completed', 'ft', 'full time')",
        "home_goals IS NOT NULL AND away_goals IS NOT NULL",
    ]
    params: list[Any] = [team_id, team_id]
    if before_datetime is not None:
        clauses.append("starting_at < %s")
        params.append(before_datetime)
    params.append(safe_limit)
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT fixture_id, season_id, league_id, home_team_id, away_team_id,
                       starting_at, status, home_goals, away_goals, venue,
                       source_provider, provider_updated_at, collected_at
                FROM football_fixtures
                WHERE {" AND ".join(clauses)}
                ORDER BY starting_at DESC
                LIMIT %s
                """,
                tuple(params),
            )
            return _rows_as_dicts(cursor)
