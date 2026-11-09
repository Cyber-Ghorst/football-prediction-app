"""Canonical football data repository schema for CockroachDB.

This module is intentionally isolated from the prediction engine and Neon
prediction ledger. Provider snapshots remain the immutable raw archive;
these tables hold normalized, queryable football entities.
"""
from __future__ import annotations

import time

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


def _execute_batched_upsert(
    cursor,
    *,
    table: str,
    columns: tuple[str, ...],
    rows: list[tuple[Any, ...]],
    conflict_sql: str,
    batch_size: int = 100,
) -> int:
    """Write rows in bounded multi-value INSERT statements."""
    if not rows:
        return 0
    if batch_size < 1:
        raise ValueError("batch_size must be positive.")
    row_placeholder = "(" + ", ".join(["%s"] * len(columns)) + ")"
    column_sql = ", ".join(columns)
    written = 0
    for offset in range(0, len(rows), batch_size):
        batch = rows[offset:offset + batch_size]
        values_sql = ", ".join([row_placeholder] * len(batch))
        parameters = tuple(value for row in batch for value in row)
        cursor.execute(
            f"INSERT INTO {table} ({column_sql}) VALUES {values_sql} {conflict_sql}",
            parameters,
        )
        written += len(batch)
    return written


def import_sportmonks_season(
    database_url: str,
    *,
    league: dict[str, Any],
    season: dict[str, Any],
    teams: list[dict[str, Any]],
    fixtures: list[dict[str, Any]],
    progress_callback=None,
) -> dict[str, Any]:
    """Bulk-import one Sportmonks season into the canonical CockroachDB repository.

    All writes remain in one transaction. Provider snapshots are maintained
    separately, and this importer never accesses the Neon prediction ledger.
    """
    import uuid

    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    league_id = _provider_id(league.get("id"))
    season_id = _provider_id(season.get("id"))
    if str(season.get("league_id")) != str(league.get("id")):
        raise ValueError("Selected Sportmonks season does not belong to the selected league.")

    counts = {
        "leagues": 0, "seasons": 0, "teams": 0, "fixtures": 0,
        "statistics": 0, "skipped_fixtures": 0,
    }
    import_started = time.monotonic()
    print(
        f"[Repository import] Starting bulk CockroachDB import for season {season_id}: "
        f"{len(teams)} teams, {len(fixtures)} fixtures.",
        flush=True,
    )
    if progress_callback:
        progress_callback(f"Preparing bulk import: {len(teams)} teams and {len(fixtures)} fixtures.")

    # Prepare normalized rows before opening the transaction. This keeps Python
    # parsing and UUID generation out of the database write window.
    team_rows: list[tuple[Any, ...]] = []
    link_rows: list[tuple[Any, ...]] = []

    def add_link(entity_type: str, provider_id: Any, canonical_id: str) -> None:
        provider_entity_id = str(provider_id)
        link_id = str(uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"sportmonks:{entity_type}:{provider_entity_id}",
        ))
        link_rows.append((
            link_id, "sportmonks", entity_type, provider_entity_id, canonical_id,
        ))

    add_link("league", league.get("id"), league_id)
    add_link("season", season.get("id"), season_id)

    for team in teams:
        if team.get("id") is None or not team.get("name"):
            continue
        team_id = _provider_id(team["id"])
        team_rows.append((
            team_id, str(team["name"]),
            team.get("short_code") or team.get("short_name"),
            _nested_name(team.get("country")),
            team.get("image_path") or team.get("logo"),
            "sportmonks", _provider_updated_at(team), Jsonb(team),
        ))
        add_link("team", team["id"], team_id)

    fixture_rows: list[tuple[Any, ...]] = []
    statistic_rows: list[tuple[Any, ...]] = []
    statistics_fixture_ids: list[str] = []
    seen_statistics_fixture_ids: set[str] = set()

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

        canonical_fixture_id = _provider_id(fixture["id"])
        state = fixture.get("state")
        status = _nested_name(state) or (
            str(fixture.get("state_id")) if fixture.get("state_id") is not None else None
        )
        fixture_rows.append((
            canonical_fixture_id, season_id, league_id, home_id, away_id,
            fixture.get("starting_at"), status, home_goals, away_goals,
            _nested_name(fixture.get("venue")), "sportmonks",
            _provider_updated_at(fixture), Jsonb(fixture),
        ))
        add_link("fixture", fixture["id"], canonical_fixture_id)

        # Only replace a fixture's normalized statistics when the provider
        # explicitly supplied the statistics field (including an empty list).
        if "statistics" not in fixture:
            continue
        if canonical_fixture_id not in seen_statistics_fixture_ids:
            statistics_fixture_ids.append(canonical_fixture_id)
            seen_statistics_fixture_ids.add(canonical_fixture_id)

        supplied_statistics = fixture.get("statistics")
        if not isinstance(supplied_statistics, list):
            continue
        for statistic_index, statistic in enumerate(supplied_statistics):
            if not isinstance(statistic, dict):
                continue
            statistic_type = statistic.get("type")
            if isinstance(statistic_type, dict):
                statistic_type_id = statistic_type.get("id")
                statistic_type_name = statistic_type.get("name")
            else:
                statistic_type_id = None
                statistic_type_name = str(statistic_type or "").strip()
            if not statistic_type_name:
                statistic_type_name = str(
                    statistic.get("name") or statistic.get("code") or ""
                ).strip()
            if not statistic_type_name:
                continue

            participant_id = statistic.get("participant_id")
            canonical_participant_id = (
                _provider_id(participant_id) if participant_id is not None else None
            )
            raw_data = statistic.get("data")
            if isinstance(raw_data, dict) and "value" in raw_data:
                statistic_value = raw_data.get("value")
            elif raw_data is not None:
                statistic_value = raw_data
            else:
                statistic_value = statistic.get("value")

            external_statistic_id = statistic.get("id")
            stable_identity = (
                str(external_statistic_id) if external_statistic_id is not None
                else f"{participant_id}:{statistic_type_id or statistic_type_name}:{statistic_index}"
            )
            statistic_id = str(uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"sportmonks:fixture-statistic:{fixture['id']}:{stable_identity}",
            ))
            statistic_rows.append((
                statistic_id, canonical_fixture_id, canonical_participant_id,
                statistic_type_name, Jsonb(statistic_value), "sportmonks",
                str(external_statistic_id) if external_statistic_id is not None else None,
                _provider_updated_at(fixture), Jsonb(statistic),
            ))

    counts["teams"] = len(team_rows)
    counts["fixtures"] = len(fixture_rows)
    counts["statistics"] = len(statistic_rows)

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
                (
                    league_id, str(league.get("name") or "Unknown league"),
                    _nested_name(league.get("country")),
                    _nested_name(league.get("type") or league.get("competition_type")),
                    league.get("image_path") or league.get("logo"),
                    _provider_updated_at(league), Jsonb(league),
                ),
            )
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
                (
                    season_id, league_id, str(season.get("name") or ""),
                    season.get("starting_at") or None, season.get("ending_at") or None,
                    season.get("is_current"), _provider_updated_at(season), Jsonb(season),
                ),
            )
            counts["seasons"] = 1

            _execute_batched_upsert(
                cursor,
                table="football_teams",
                columns=(
                    "team_id", "name", "short_name", "country", "logo_url",
                    "source_provider", "provider_updated_at", "raw_payload",
                ),
                rows=team_rows,
                conflict_sql="""
                    ON CONFLICT (team_id) DO UPDATE SET
                        name = excluded.name, short_name = excluded.short_name,
                        country = excluded.country, logo_url = excluded.logo_url,
                        source_provider = excluded.source_provider,
                        provider_updated_at = excluded.provider_updated_at,
                        collected_at = NOW(), raw_payload = excluded.raw_payload
                """,
                batch_size=50,
            )
            if progress_callback:
                progress_callback(f"Bulk-saved {counts['teams']} teams. Writing {counts['fixtures']} fixtures in batches...")

            _execute_batched_upsert(
                cursor,
                table="football_fixtures",
                columns=(
                    "fixture_id", "season_id", "league_id", "home_team_id", "away_team_id",
                    "starting_at", "status", "home_goals", "away_goals", "venue",
                    "source_provider", "provider_updated_at", "raw_payload",
                ),
                rows=fixture_rows,
                conflict_sql="""
                    ON CONFLICT (fixture_id) DO UPDATE SET
                        season_id = excluded.season_id, league_id = excluded.league_id,
                        home_team_id = excluded.home_team_id, away_team_id = excluded.away_team_id,
                        starting_at = excluded.starting_at, status = excluded.status,
                        home_goals = excluded.home_goals, away_goals = excluded.away_goals,
                        venue = excluded.venue, source_provider = excluded.source_provider,
                        provider_updated_at = excluded.provider_updated_at,
                        collected_at = NOW(), raw_payload = excluded.raw_payload
                """,
                batch_size=40,
            )
            if progress_callback:
                progress_callback(f"Bulk-saved {counts['fixtures']} fixtures. Updating provider crosswalks...")

            _execute_batched_upsert(
                cursor,
                table="provider_entity_links",
                columns=(
                    "link_id", "provider", "entity_type", "provider_entity_id",
                    "canonical_entity_id",
                ),
                rows=link_rows,
                conflict_sql="""
                    ON CONFLICT (provider, entity_type, provider_entity_id)
                    DO UPDATE SET canonical_entity_id = excluded.canonical_entity_id,
                                  last_seen_at = NOW()
                """,
                batch_size=100,
            )

            # Delete old normalized statistics only for fixtures whose provider
            # response explicitly included a statistics field.
            for offset in range(0, len(statistics_fixture_ids), 100):
                batch_ids = statistics_fixture_ids[offset:offset + 100]
                placeholders = ", ".join(["%s"] * len(batch_ids))
                cursor.execute(
                    f"DELETE FROM football_fixture_statistics WHERE fixture_id IN ({placeholders})",
                    tuple(batch_ids),
                )

            _execute_batched_upsert(
                cursor,
                table="football_fixture_statistics",
                columns=(
                    "statistic_id", "fixture_id", "team_id", "statistic_type",
                    "statistic_value", "source_provider", "provider_statistic_id",
                    "provider_updated_at", "raw_payload",
                ),
                rows=statistic_rows,
                conflict_sql="""
                    ON CONFLICT (statistic_id) DO UPDATE SET
                        fixture_id = excluded.fixture_id,
                        team_id = excluded.team_id,
                        statistic_type = excluded.statistic_type,
                        statistic_value = excluded.statistic_value,
                        source_provider = excluded.source_provider,
                        provider_statistic_id = excluded.provider_statistic_id,
                        provider_updated_at = excluded.provider_updated_at,
                        collected_at = NOW(), raw_payload = excluded.raw_payload
                """,
                batch_size=100,
            )
            if progress_callback:
                progress_callback(
                    f"Bulk writes complete: {counts['fixtures']} fixtures and "
                    f"{counts['statistics']} statistics. Saving sync state..."
                )

            _sync_result(cursor, "leagues", 1, counts["leagues"])
            _sync_result(cursor, "seasons", 1, counts["seasons"])
            _sync_result(cursor, "teams", len(teams), counts["teams"])
            _sync_result(cursor, "fixtures", len(fixtures), counts["fixtures"])
            _sync_result(
                cursor, "fixture_statistics",
                counts["statistics"], counts["statistics"],
            )

    duration = time.monotonic() - import_started
    print(
        f"[Repository import] Bulk transaction committed in {duration:.2f}s; "
        f"fixtures={counts['fixtures']}, statistics={counts['statistics']}, "
        f"links={len(link_rows)}.",
        flush=True,
    )
    if progress_callback:
        progress_callback(f"Database transaction committed in {duration:.1f}s.")
    return {
        "provider": "sportmonks",
        "league": league.get("name"),
        "season": season.get("name"),
        "received": {"teams": len(teams), "fixtures": len(fixtures)},
        "upserted": counts,
        "provider_links_written": len(link_rows),
        "statistics_source": "fixture raw_payload.statistics when supplied by provider",
        "idempotent": True,
        "raw_snapshots_preserved": True,
        "neon_prediction_ledger_modified": False,
        "import_mode": "chunked_bulk_upsert",
        "transaction_duration_seconds": round(duration, 2),
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
            "('finished', 'complete', 'completed', 'ft', 'full time', '5')"
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
                       source_provider, provider_updated_at, collected_at, raw_payload
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
        "('finished', 'complete', 'completed', 'ft', 'full time', '5')",
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
                       source_provider, provider_updated_at, collected_at, raw_payload
                FROM football_fixtures
                WHERE {" AND ".join(clauses)}
                ORDER BY starting_at DESC
                LIMIT %s
                """,
                tuple(params),
            )
            return _rows_as_dicts(cursor)




def audit_all_repository_team_histories(
    database_url: str,
    *,
    history_limit: int = 10,
) -> dict[str, Any]:
    """Audit recent verified completed-match history for every canonical team.

    Uses one bounded database read for teams and one windowed fixture query.
    A team history is valid only when each row identifies that team on exactly
    one side, has a recognized completed status and non-negative exact scores.
    Season consistency and duplicate fixture fingerprints are reported rather
    than silently filtered.
    """
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    safe_limit = max(1, min(int(history_limit), 20))
    completed_statuses = (
        "finished", "complete", "completed", "ft", "full time", "5"
    )
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT team_id, name, source_provider
                FROM football_teams
                ORDER BY name, team_id
                """
            )
            teams = _rows_as_dicts(cursor)
            cursor.execute(
                """
                WITH completed AS (
                    SELECT fixture_id, season_id, league_id, home_team_id AS team_id,
                           away_team_id, home_team_id, starting_at, status,
                           home_goals, away_goals, source_provider, TRUE AS is_home
                    FROM football_fixtures
                    WHERE LOWER(COALESCE(status, '')) IN
                        ('finished', 'complete', 'completed', 'ft', 'full time', '5')
                      AND home_goals IS NOT NULL AND away_goals IS NOT NULL
                      AND home_goals >= 0 AND away_goals >= 0
                      AND starting_at < NOW()
                    UNION ALL
                    SELECT fixture_id, season_id, league_id, away_team_id AS team_id,
                           away_team_id, home_team_id, starting_at, status,
                           home_goals, away_goals, source_provider, FALSE AS is_home
                    FROM football_fixtures
                    WHERE LOWER(COALESCE(status, '')) IN
                        ('finished', 'complete', 'completed', 'ft', 'full time', '5')
                      AND home_goals IS NOT NULL AND away_goals IS NOT NULL
                      AND home_goals >= 0 AND away_goals >= 0
                      AND starting_at < NOW()
                ),
                ranked AS (
                    SELECT *, ROW_NUMBER() OVER (
                        PARTITION BY team_id
                        ORDER BY starting_at DESC, fixture_id DESC
                    ) AS history_rank
                    FROM completed
                )
                SELECT fixture_id, season_id, league_id, team_id, away_team_id,
                       home_team_id, starting_at, status, home_goals, away_goals,
                       source_provider, is_home, history_rank
                FROM ranked
                WHERE history_rank <= %s
                ORDER BY team_id, starting_at DESC, fixture_id DESC
                """,
                (safe_limit,),
            )
            history_rows = _rows_as_dicts(cursor)
            cursor.execute(
                """
                SELECT season_id, league_id, home_team_id, away_team_id,
                       starting_at, COUNT(*) AS duplicate_count,
                       ARRAY_AGG(fixture_id ORDER BY fixture_id) AS fixture_ids
                FROM football_fixtures
                WHERE starting_at IS NOT NULL
                GROUP BY season_id, league_id, home_team_id, away_team_id, starting_at
                HAVING COUNT(*) > 1
                ORDER BY duplicate_count DESC
                LIMIT 200
                """
            )
            duplicate_groups = _rows_as_dicts(cursor)

    by_team: dict[str, list[dict[str, Any]]] = {}
    for row in history_rows:
        by_team.setdefault(str(row.get("team_id")), []).append(row)

    duplicate_fixture_ids = {
        str(fixture_id)
        for group in duplicate_groups
        for fixture_id in (group.get("fixture_ids") or [])
    }
    team_results = []
    for team in teams:
        team_id = str(team.get("team_id"))
        rows = by_team.get(team_id, [])
        valid_identity = all(
            (str(row.get("home_team_id")) == team_id) !=
            (str(row.get("away_team_id")) == team_id)
            for row in rows
        )
        valid_scores = all(
            isinstance(row.get("home_goals"), int) and row["home_goals"] >= 0
            and isinstance(row.get("away_goals"), int) and row["away_goals"] >= 0
            for row in rows
        )
        seasons = sorted({str(row.get("season_id")) for row in rows if row.get("season_id") is not None})
        fixture_ids = [str(row.get("fixture_id")) for row in rows]
        duplicate_ids = (
            len(fixture_ids) != len(set(fixture_ids))
            or any(fixture_id in duplicate_fixture_ids for fixture_id in fixture_ids)
        )
        team_results.append({
            "team_id": team_id,
            "team_name": team.get("name"),
            "source_provider": team.get("source_provider"),
            "history_matches_returned": len(rows),
            "history_target_met": len(rows) >= safe_limit,
            "team_identity_valid": valid_identity,
            "scores_valid": valid_scores,
            "season_consistent": len(seasons) <= 1,
            "season_ids": seasons,
            "duplicate_fixture_ids_in_history": duplicate_ids,
            "history_status": "pass" if (
                len(rows) >= safe_limit and valid_identity and valid_scores
                and len(seasons) <= 1 and not duplicate_ids
            ) else "review",
            "matches": rows,
        })

    passed = sum(item["history_status"] == "pass" for item in team_results)
    return {
        "audit_status": "success",
        "history_limit_per_team": safe_limit,
        "teams_scanned": len(teams),
        "teams_with_history": sum(item["history_matches_returned"] > 0 for item in team_results),
        "teams_meeting_history_target": sum(item["history_target_met"] for item in team_results),
        "teams_passing_all_checks": passed,
        "teams_requiring_review": len(team_results) - passed,
        "duplicate_fixture_groups_found": len(duplicate_groups),
        "duplicate_fixture_groups": duplicate_groups,
        "checks": {
            "recognized_completed_status_and_both_nonnegative_scores_required": True,
            "home_away_identity_checked": True,
            "season_consistency_checked": True,
            "duplicate_fixture_fingerprints_checked": True,
            "prediction_engine_modified": False,
            "neon_prediction_ledger_modified": False,
        },
        "teams": team_results,
    }

def get_repository_fixture_statistics(
    database_url: str,
    fixture_ids: list[str],
) -> list[dict[str, Any]]:
    """Read normalized statistics for a bounded set of canonical fixture IDs."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    normalized_ids = list(dict.fromkeys(str(value) for value in fixture_ids if value))
    if not normalized_ids:
        return []
    if len(normalized_ids) > 2000:
        raise ValueError("A maximum of 2000 fixture IDs may be queried at once.")
    placeholders = ", ".join(["%s"] * len(normalized_ids))
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT statistic_id, fixture_id, team_id, statistic_type,
                       statistic_value, source_provider, provider_statistic_id,
                       provider_updated_at, collected_at, raw_payload
                FROM football_fixture_statistics
                WHERE fixture_id IN ({placeholders})
                ORDER BY fixture_id, team_id, statistic_type
                """,
                tuple(normalized_ids),
            )
            return _rows_as_dicts(cursor)



def audit_repository_fixture_statistics(database_url: str) -> dict[str, Any]:
    """Audit normalized fixture-statistic coverage and relational integrity."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")

    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(s.statistic_id) AS statistic_rows,
                    COUNT(s.statistic_id) FILTER (
                        WHERE f.fixture_id IS NULL
                    ) AS orphan_statistic_rows,
                    COUNT(s.statistic_id) FILTER (
                        WHERE f.fixture_id IS NOT NULL
                          AND s.team_id IS NOT NULL
                          AND s.team_id NOT IN (f.home_team_id, f.away_team_id)
                    ) AS invalid_team_association_rows,
                    COUNT(s.statistic_id) FILTER (
                        WHERE s.statistic_type IS NULL OR BTRIM(s.statistic_type) = ''
                    ) AS missing_statistic_type_rows,
                    COUNT(s.statistic_id) FILTER (
                        WHERE s.statistic_value IS NULL
                           OR s.statistic_value = 'null'::JSONB
                    ) AS missing_statistic_value_rows,
                    COUNT(DISTINCT s.fixture_id) FILTER (
                        WHERE f.fixture_id IS NOT NULL
                    ) AS fixtures_with_statistics,
                    COUNT(DISTINCT f.fixture_id) FILTER (
                        WHERE s.statistic_id IS NULL
                    ) AS fixtures_without_statistics,
                    COUNT(DISTINCT f.fixture_id) FILTER (
                        WHERE LOWER(COALESCE(f.status, '')) IN
                            ('finished', 'complete', 'completed', 'ft', 'full time', '5')
                          AND f.home_goals IS NOT NULL AND f.away_goals IS NOT NULL
                          AND f.starting_at < NOW()
                    ) AS completed_scored_fixtures,
                    COUNT(DISTINCT f.fixture_id) FILTER (
                        WHERE LOWER(COALESCE(f.status, '')) IN
                            ('finished', 'complete', 'completed', 'ft', 'full time', '5')
                          AND f.home_goals IS NOT NULL AND f.away_goals IS NOT NULL
                          AND f.starting_at < NOW()
                          AND s.statistic_id IS NOT NULL
                    ) AS completed_scored_fixtures_with_statistics
                FROM football_fixture_statistics AS s
                FULL OUTER JOIN football_fixtures AS f
                    ON f.fixture_id = s.fixture_id
                """
            )
            summary_rows = _rows_as_dicts(cursor)
            summary = summary_rows[0] if summary_rows else {}

            cursor.execute(
                """
                WITH duplicate_groups AS (
                    SELECT fixture_id, team_id, statistic_type, source_provider,
                           COUNT(*) AS duplicate_count
                    FROM football_fixture_statistics
                    GROUP BY fixture_id, team_id, statistic_type, source_provider
                    HAVING COUNT(*) > 1
                )
                SELECT COUNT(*) AS duplicate_logical_groups,
                       COALESCE(SUM(duplicate_count - 1), 0) AS excess_duplicate_rows
                FROM duplicate_groups
                """
            )
            duplicate_summary_rows = _rows_as_dicts(cursor)
            duplicate_summary = (
                duplicate_summary_rows[0] if duplicate_summary_rows else {}
            )

            cursor.execute(
                """
                SELECT fixture_id, team_id, statistic_type, source_provider,
                       COUNT(*) AS duplicate_count,
                       ARRAY_AGG(statistic_id ORDER BY statistic_id) AS statistic_ids
                FROM football_fixture_statistics
                GROUP BY fixture_id, team_id, statistic_type, source_provider
                HAVING COUNT(*) > 1
                ORDER BY duplicate_count DESC, fixture_id
                LIMIT 100
                """
            )
            duplicate_samples = _rows_as_dicts(cursor)

            cursor.execute(
                """
                SELECT source_provider, COUNT(*) AS statistic_rows,
                       COUNT(DISTINCT fixture_id) AS fixtures_covered
                FROM football_fixture_statistics
                GROUP BY source_provider
                ORDER BY statistic_rows DESC, source_provider
                """
            )
            provider_breakdown = _rows_as_dicts(cursor)

    total_completed = int(summary.get("completed_scored_fixtures") or 0)
    completed_with_stats = int(
        summary.get("completed_scored_fixtures_with_statistics") or 0
    )
    coverage = (
        round(completed_with_stats / total_completed * 100, 2)
        if total_completed else None
    )
    duplicate_groups = int(duplicate_summary.get("duplicate_logical_groups") or 0)
    integrity_issues = {
        "orphan_statistic_rows": int(summary.get("orphan_statistic_rows") or 0),
        "invalid_team_association_rows": int(
            summary.get("invalid_team_association_rows") or 0
        ),
        "missing_statistic_type_rows": int(
            summary.get("missing_statistic_type_rows") or 0
        ),
        "missing_statistic_value_rows": int(
            summary.get("missing_statistic_value_rows") or 0
        ),
        "duplicate_logical_groups": duplicate_groups,
    }
    return {
        "audit_status": "success" if not any(integrity_issues.values()) else "review",
        "summary": {
            key: int(value or 0) for key, value in summary.items()
        },
        "completed_fixture_statistics_coverage_percent": coverage,
        "integrity_issues": integrity_issues,
        "duplicate_excess_rows": int(duplicate_summary.get("excess_duplicate_rows") or 0),
        "duplicate_samples": duplicate_samples,
        "provider_breakdown": provider_breakdown,
        "checks": {
            "orphan_statistics_checked": True,
            "team_associations_checked_against_fixture_participants": True,
            "missing_statistic_types_and_values_checked": True,
            "duplicate_logical_statistic_records_checked": True,
            "prediction_engine_modified": False,
            "neon_prediction_ledger_modified": False,
        },
    }

def get_completed_scored_fixtures_missing_statistics(
    database_url: str,
    *,
    season_id: str = "sportmonks:27965",
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return a small read-only sample of completed, scored fixtures with no normalized stats."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    safe_limit = max(1, min(int(limit), 10))
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    f.fixture_id,
                    f.season_id,
                    f.league_id,
                    ht.name AS home_team,
                    at.name AS away_team,
                    f.starting_at,
                    f.status,
                    f.home_goals,
                    f.away_goals
                FROM football_fixtures f
                JOIN football_teams ht ON ht.team_id = f.home_team_id
                JOIN football_teams at ON at.team_id = f.away_team_id
                WHERE f.season_id = %s
                  AND f.source_provider = 'sportmonks'
                  AND f.status = '5'
                  AND f.home_goals IS NOT NULL
                  AND f.away_goals IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1
                      FROM football_fixture_statistics s
                      WHERE s.fixture_id = f.fixture_id
                  )
                ORDER BY f.starting_at DESC, f.fixture_id
                LIMIT %s
                """,
                (str(season_id), safe_limit),
            )
            rows = cursor.fetchall()
    columns = (
        "fixture_id", "season_id", "league_id", "home_team", "away_team",
        "starting_at", "status", "home_goals", "away_goals",
    )
    return [dict(zip(columns, row)) for row in rows]


def diagnose_fixture_statistics_coverage(database_url: str) -> dict[str, Any]:
    """Explain fixture-statistics gaps by completion state and stored provider payload."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")

    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH fixture_stats AS (
                    SELECT fixture_id, COUNT(*) AS statistic_rows
                    FROM football_fixture_statistics
                    GROUP BY fixture_id
                ),
                classified AS (
                    SELECT
                        f.fixture_id, f.season_id, f.league_id, f.starting_at,
                        COALESCE(f.status, '<NULL>') AS status,
                        f.home_goals, f.away_goals, f.source_provider,
                        f.collected_at,
                        COALESCE(fs.statistic_rows, 0) AS statistic_rows,
                        (f.raw_payload->'statistics') IS NOT NULL AS raw_statistics_present,
                        CASE
                            WHEN (f.raw_payload->'statistics') IS NULL
                                THEN 'not_in_stored_provider_payload'
                            WHEN f.raw_payload->'statistics' = '[]'::JSONB
                                THEN 'provider_returned_empty_statistics'
                            ELSE 'provider_payload_contains_statistics'
                        END AS statistics_payload_state,
                        CASE
                            WHEN LOWER(COALESCE(f.status, '')) IN
                                ('finished', 'complete', 'completed', 'ft', 'full time', '5')
                             AND f.home_goals IS NOT NULL AND f.away_goals IS NOT NULL
                             AND f.starting_at < NOW()
                                THEN 'completed_scored'
                            WHEN f.starting_at < NOW()
                                THEN 'past_unverified_or_unscored'
                            WHEN f.starting_at >= NOW()
                                THEN 'future_or_upcoming'
                            ELSE 'unknown_kickoff'
                        END AS fixture_cohort
                    FROM football_fixtures AS f
                    LEFT JOIN fixture_stats AS fs ON fs.fixture_id = f.fixture_id
                )
                SELECT
                    COUNT(*) AS total_fixtures,
                    COUNT(*) FILTER (WHERE statistic_rows > 0) AS fixtures_with_normalized_statistics,
                    COUNT(*) FILTER (WHERE statistic_rows = 0) AS fixtures_without_normalized_statistics,
                    COUNT(*) FILTER (WHERE fixture_cohort = 'completed_scored') AS completed_scored_fixtures,
                    COUNT(*) FILTER (WHERE fixture_cohort = 'completed_scored' AND statistic_rows > 0)
                        AS completed_scored_with_statistics,
                    COUNT(*) FILTER (WHERE fixture_cohort = 'completed_scored' AND statistic_rows = 0)
                        AS completed_scored_missing_statistics,
                    COUNT(*) FILTER (WHERE fixture_cohort = 'past_unverified_or_unscored')
                        AS past_unverified_or_unscored_fixtures,
                    COUNT(*) FILTER (WHERE fixture_cohort = 'future_or_upcoming')
                        AS future_or_upcoming_fixtures,
                    COUNT(*) FILTER (WHERE fixture_cohort = 'unknown_kickoff')
                        AS unknown_kickoff_fixtures,
                    COUNT(*) FILTER (WHERE statistics_payload_state = 'not_in_stored_provider_payload')
                        AS missing_statistics_from_stored_provider_payload,
                    COUNT(*) FILTER (WHERE statistics_payload_state = 'provider_returned_empty_statistics')
                        AS provider_payload_with_empty_statistics,
                    COUNT(*) FILTER (WHERE statistics_payload_state = 'provider_payload_contains_statistics'
                                      AND statistic_rows = 0)
                        AS provider_statistics_present_but_not_normalized
                FROM classified
                """
            )
            summary_rows = _rows_as_dicts(cursor)
            summary = summary_rows[0] if summary_rows else {}

            cursor.execute(
                """
                WITH fixture_stats AS (
                    SELECT fixture_id, COUNT(*) AS statistic_rows
                    FROM football_fixture_statistics
                    GROUP BY fixture_id
                )
                SELECT
                    f.season_id,
                    COALESCE(f.status, '<NULL>') AS status,
                    CASE
                        WHEN LOWER(COALESCE(f.status, '')) IN
                            ('finished', 'complete', 'completed', 'ft', 'full time', '5')
                         AND f.home_goals IS NOT NULL AND f.away_goals IS NOT NULL
                         AND f.starting_at < NOW()
                            THEN 'completed_scored'
                        WHEN f.starting_at < NOW()
                            THEN 'past_unverified_or_unscored'
                        WHEN f.starting_at >= NOW()
                            THEN 'future_or_upcoming'
                        ELSE 'unknown_kickoff'
                    END AS fixture_cohort,
                    COUNT(*) AS fixture_count,
                    COUNT(*) FILTER (WHERE COALESCE(fs.statistic_rows, 0) > 0)
                        AS fixtures_with_statistics,
                    COUNT(*) FILTER (WHERE COALESCE(fs.statistic_rows, 0) = 0)
                        AS fixtures_without_statistics,
                    COUNT(*) FILTER (WHERE f.raw_payload->'statistics' IS NULL)
                        AS provider_statistics_field_absent,
                    COUNT(*) FILTER (WHERE f.raw_payload->'statistics' = '[]'::JSONB)
                        AS provider_returned_empty_statistics,
                    COUNT(*) FILTER (
                        WHERE f.raw_payload->'statistics' IS NOT NULL
                          AND f.raw_payload->'statistics' <> '[]'::JSONB
                          AND COALESCE(fs.statistic_rows, 0) = 0
                    ) AS provider_statistics_present_but_not_normalized
                FROM football_fixtures AS f
                LEFT JOIN fixture_stats AS fs ON fs.fixture_id = f.fixture_id
                GROUP BY f.season_id, COALESCE(f.status, '<NULL>'),
                    CASE
                        WHEN LOWER(COALESCE(f.status, '')) IN
                            ('finished', 'complete', 'completed', 'ft', 'full time', '5')
                         AND f.home_goals IS NOT NULL AND f.away_goals IS NOT NULL
                         AND f.starting_at < NOW()
                            THEN 'completed_scored'
                        WHEN f.starting_at < NOW()
                            THEN 'past_unverified_or_unscored'
                        WHEN f.starting_at >= NOW()
                            THEN 'future_or_upcoming'
                        ELSE 'unknown_kickoff'
                    END
                ORDER BY f.season_id, fixture_cohort, status
                """
            )
            cohort_breakdown = _rows_as_dicts(cursor)

            cursor.execute(
                """
                WITH fixture_stats AS (
                    SELECT fixture_id, COUNT(*) AS statistic_rows
                    FROM football_fixture_statistics
                    GROUP BY fixture_id
                )
                SELECT
                    f.fixture_id, f.season_id, f.league_id,
                    home.name AS home_team, away.name AS away_team,
                    f.starting_at, f.status, f.home_goals, f.away_goals,
                    f.source_provider, f.collected_at,
                    CASE
                        WHEN f.raw_payload->'statistics' IS NULL
                            THEN 'not_in_stored_provider_payload'
                        WHEN f.raw_payload->'statistics' = '[]'::JSONB
                            THEN 'provider_returned_empty_statistics'
                        ELSE 'provider_payload_contains_statistics'
                    END AS statistics_payload_state,
                    COALESCE(fs.statistic_rows, 0) AS normalized_statistic_rows,
                    CASE
                        WHEN LOWER(COALESCE(f.status, '')) IN
                            ('finished', 'complete', 'completed', 'ft', 'full time', '5')
                         AND f.home_goals IS NOT NULL AND f.away_goals IS NOT NULL
                         AND f.starting_at < NOW()
                            THEN 'completed_scored'
                        WHEN f.starting_at < NOW()
                            THEN 'past_unverified_or_unscored'
                        WHEN f.starting_at >= NOW()
                            THEN 'future_or_upcoming'
                        ELSE 'unknown_kickoff'
                    END AS fixture_cohort
                FROM football_fixtures AS f
                LEFT JOIN fixture_stats AS fs ON fs.fixture_id = f.fixture_id
                LEFT JOIN football_teams AS home ON home.team_id = f.home_team_id
                LEFT JOIN football_teams AS away ON away.team_id = f.away_team_id
                WHERE COALESCE(fs.statistic_rows, 0) = 0
                ORDER BY f.starting_at DESC NULLS LAST, f.fixture_id
                LIMIT 100
                """
            )
            missing_fixture_samples = _rows_as_dicts(cursor)

    return {
        "diagnostic_status": "success",
        "summary": {key: int(value or 0) for key, value in summary.items()},
        "cohort_breakdown": cohort_breakdown,
        "missing_fixture_samples": missing_fixture_samples,
        "interpretation_guide": {
            "not_in_stored_provider_payload": "The stored fixture response did not contain a statistics field; this does not by itself prove the provider has no statistics.",
            "provider_returned_empty_statistics": "The stored provider response explicitly contained an empty statistics list.",
            "provider_payload_contains_statistics": "The stored response included a non-empty statistics payload; if normalized rows are zero, investigate the importer.",
            "completed_scored": "Recognized completed status, both scores present, and kickoff is in the past.",
        },
        "read_only": True,
        "prediction_engine_modified": False,
        "neon_prediction_ledger_modified": False,
    }


def diagnose_repository_fixture_history(database_url: str) -> dict[str, Any]:
    """Summarize imported fixture statuses and score coverage to diagnose history reads."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(status, '<NULL>') AS status,
                       COUNT(*) AS fixture_count,
                       COUNT(*) FILTER (
                           WHERE home_goals IS NOT NULL AND away_goals IS NOT NULL
                       ) AS fixtures_with_both_scores,
                       COUNT(*) FILTER (
                           WHERE starting_at < NOW()
                       ) AS fixtures_in_past
                FROM football_fixtures
                GROUP BY COALESCE(status, '<NULL>')
                ORDER BY fixture_count DESC, status
                """
            )
            status_summary = _rows_as_dicts(cursor)
            cursor.execute(
                """
                SELECT fixture_id, starting_at, status, home_goals, away_goals,
                       raw_payload->'state' AS raw_state,
                       raw_payload->>'state_id' AS raw_state_id,
                       raw_payload->'scores' AS raw_scores
                FROM football_fixtures
                WHERE starting_at < NOW()
                ORDER BY starting_at DESC NULLS LAST
                LIMIT 5
                """
            )
            recent_past_samples = _rows_as_dicts(cursor)
    return {
        "status_summary": status_summary,
        "recent_past_fixture_samples": recent_past_samples,
        "history_filter_requires_recognized_status_and_both_scores": True,
    }
