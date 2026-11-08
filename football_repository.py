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
