"""Provider-neutral source evidence repository, separate from canonical identities.

This additive repository stores provider-native entities, fixtures and
statistics without selecting a canonical provider, creating canonical IDs,
or linking different providers. It is intentionally not called by the
legacy Sportmonks importer or prediction workflow.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
import json

from psycopg.types.json import Jsonb

from provider_data_storage import _connect

SUPPORTED_PROVIDERS = {
    "sportmonks", "highlightly", "livescore_football", "api_football",
    "api_ninjas", "openscores", "openligadb", "openfootball",
    "open_matchday", "football_data_org", "bzzoiro",
}

PROVIDER_SOURCE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS provider_source_entities (
    provider TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('competition', 'season', 'team')),
    provider_entity_id TEXT NOT NULL,
    name TEXT NOT NULL,
    country TEXT,
    competition_type TEXT,
    parent_competition_provider_id TEXT,
    season_label TEXT,
    start_date DATE,
    end_date DATE,
    team_type TEXT,
    gender_scope TEXT,
    age_group TEXT,
    squad_scope TEXT,
    provider_updated_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload JSONB,
    PRIMARY KEY (provider, entity_type, provider_entity_id)
);
CREATE INDEX IF NOT EXISTS provider_source_entities_parent_idx
    ON provider_source_entities (provider, entity_type, parent_competition_provider_id);
CREATE INDEX IF NOT EXISTS provider_source_entities_name_idx
    ON provider_source_entities (entity_type, country, name);

CREATE TABLE IF NOT EXISTS provider_source_fixtures (
    provider TEXT NOT NULL,
    provider_fixture_id TEXT NOT NULL,
    competition_provider_id TEXT NOT NULL,
    season_provider_id TEXT NOT NULL,
    home_team_provider_id TEXT NOT NULL,
    away_team_provider_id TEXT NOT NULL,
    kickoff_utc TIMESTAMPTZ NOT NULL,
    status TEXT,
    home_score INTEGER,
    away_score INTEGER,
    venue TEXT,
    provider_updated_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload JSONB,
    PRIMARY KEY (provider, provider_fixture_id),
    CHECK (home_team_provider_id <> away_team_provider_id)
);
CREATE INDEX IF NOT EXISTS provider_source_fixtures_scope_idx
    ON provider_source_fixtures (provider, competition_provider_id, season_provider_id, kickoff_utc);
CREATE INDEX IF NOT EXISTS provider_source_fixtures_teams_idx
    ON provider_source_fixtures (provider, home_team_provider_id, away_team_provider_id, kickoff_utc);

CREATE TABLE IF NOT EXISTS provider_source_fixture_statistics (
    provider TEXT NOT NULL,
    provider_fixture_id TEXT NOT NULL,
    provider_statistic_id TEXT NOT NULL,
    provider_team_id TEXT,
    statistic_type TEXT NOT NULL,
    statistic_value JSONB,
    provider_updated_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload JSONB,
    PRIMARY KEY (provider, provider_fixture_id, provider_statistic_id)
);
CREATE INDEX IF NOT EXISTS provider_source_statistics_fixture_idx
    ON provider_source_fixture_statistics (provider, provider_fixture_id, provider_team_id);
"""


def _provider(value: Any) -> str:
    provider = str(value or "").strip().casefold()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError("Unsupported provider.")
    return provider


def _required_id(value: Any, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{label} is required.")
    return result


def _aware_datetime(value: Any, label: str) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        result = value
    else:
        try:
            result = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except (TypeError, ValueError):
            raise ValueError(f"{label} must be a valid ISO-8601 timestamp.") from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone.")
    return result.astimezone(timezone.utc)


def validate_provider_source_bundle(
    provider: str,
    *,
    entities: list[Mapping[str, Any]] | None = None,
    fixtures: list[Mapping[str, Any]] | None = None,
    statistics: list[Mapping[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Validate provider-native evidence without deriving cross-provider identity."""
    source = _provider(provider)
    normalized: dict[str, list[dict[str, Any]]] = {
        "entities": [], "fixtures": [], "statistics": [],
    }
    for row in entities or []:
        if not isinstance(row, Mapping):
            raise ValueError("Every source entity must be an object.")
        kind = str(row.get("entity_type") or "").strip().casefold()
        if kind not in {"competition", "season", "team"}:
            raise ValueError("Source entity_type must be competition, season or team.")
        entity_id = _required_id(row.get("provider_entity_id") or row.get("id"), "Provider entity ID")
        name = _required_id(row.get("name"), "Provider entity name")
        parent = row.get("parent_competition_provider_id")
        if kind == "season":
            parent = _required_id(parent, "Season parent competition provider ID")
        normalized["entities"].append({
            "provider": source, "entity_type": kind, "provider_entity_id": entity_id,
            "name": name, "country": row.get("country"),
            "competition_type": row.get("competition_type"),
            "parent_competition_provider_id": str(parent).strip() if parent else None,
            "season_label": row.get("season_label"),
            "start_date": row.get("start_date"), "end_date": row.get("end_date"),
            "team_type": row.get("team_type"), "gender_scope": row.get("gender_scope"),
            "age_group": row.get("age_group"), "squad_scope": row.get("squad_scope"),
            "provider_updated_at": _aware_datetime(row.get("provider_updated_at"), "provider_updated_at"),
            "raw_payload": row.get("raw_payload", dict(row)),
        })

    for row in fixtures or []:
        if not isinstance(row, Mapping):
            raise ValueError("Every source fixture must be an object.")
        home = _required_id(row.get("home_team_provider_id"), "Home team provider ID")
        away = _required_id(row.get("away_team_provider_id"), "Away team provider ID")
        if home == away:
            raise ValueError("Home and away team provider IDs must differ.")
        kickoff = _aware_datetime(row.get("kickoff_utc"), "Fixture kickoff")
        if kickoff is None:
            raise ValueError("Fixture kickoff is required.")
        normalized["fixtures"].append({
            "provider": source,
            "provider_fixture_id": _required_id(row.get("provider_fixture_id"), "Provider fixture ID"),
            "competition_provider_id": _required_id(row.get("competition_provider_id"), "Competition provider ID"),
            "season_provider_id": _required_id(row.get("season_provider_id"), "Season provider ID"),
            "home_team_provider_id": home, "away_team_provider_id": away,
            "kickoff_utc": kickoff,
            "status": row.get("status"), "home_score": row.get("home_score"),
            "away_score": row.get("away_score"), "venue": row.get("venue"),
            "provider_updated_at": _aware_datetime(row.get("provider_updated_at"), "provider_updated_at"),
            "raw_payload": row.get("raw_payload", dict(row)),
        })

    for index, row in enumerate(statistics or []):
        if not isinstance(row, Mapping):
            raise ValueError("Every source statistic must be an object.")
        normalized["statistics"].append({
            "provider": source,
            "provider_fixture_id": _required_id(row.get("provider_fixture_id"), "Statistic fixture provider ID"),
            "provider_statistic_id": _required_id(
                row.get("provider_statistic_id") or f"row-{index}", "Provider statistic ID"
            ),
            "provider_team_id": str(row.get("provider_team_id") or "").strip() or None,
            "statistic_type": _required_id(row.get("statistic_type"), "Statistic type"),
            "statistic_value": row.get("statistic_value"),
            "provider_updated_at": _aware_datetime(row.get("provider_updated_at"), "provider_updated_at"),
            "raw_payload": row.get("raw_payload", dict(row)),
        })
    return normalized


def ensure_provider_source_repository(database_url: str) -> dict[str, Any]:
    """Create additive provider-source tables; existing legacy tables are untouched."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            for statement in PROVIDER_SOURCE_SCHEMA_SQL.split(";"):
                if statement.strip():
                    cursor.execute(statement.strip())
            cursor.execute(
                """SELECT table_name FROM information_schema.tables
                   WHERE table_schema = current_schema()
                     AND table_name IN (
                       'provider_source_entities', 'provider_source_fixtures',
                       'provider_source_fixture_statistics'
                     ) ORDER BY table_name"""
            )
            tables = [row[0] for row in cursor.fetchall()]
    if len(tables) != 3:
        raise RuntimeError("Provider source repository schema is incomplete.")
    return {"success": True, "tables": tables, "canonical_entities_written": 0,
            "provider_links_written": 0, "prediction_ledger_touched": False}


def store_provider_source_bundle(
    database_url: str,
    provider: str,
    *,
    entities: list[Mapping[str, Any]] | None = None,
    fixtures: list[Mapping[str, Any]] | None = None,
    statistics: list[Mapping[str, Any]] | None = None,
    write_scope: str | None = None,
) -> dict[str, int]:
    """Persist provider-native evidence only; never create canonical entities or links.

    Callers must explicitly select the narrow source-evidence write scope. This
    API is not wired into app prediction, future-fixture discovery, or legacy
    Sportmonks imports.
    """
    if write_scope != "provider_source_evidence_only":
        raise ValueError("Explicit write_scope='provider_source_evidence_only' is required.")
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    bundle = validate_provider_source_bundle(
        provider, entities=entities, fixtures=fixtures, statistics=statistics,
    )
    ensure_provider_source_repository(database_url)
    counts = {"entities": 0, "fixtures": 0, "statistics": 0}
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            for row in bundle["entities"]:
                cursor.execute(
                    """INSERT INTO provider_source_entities (
                        provider, entity_type, provider_entity_id, name, country,
                        competition_type, parent_competition_provider_id, season_label,
                        start_date, end_date, team_type, gender_scope, age_group, squad_scope,
                        provider_updated_at, raw_payload
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (provider, entity_type, provider_entity_id) DO UPDATE SET
                        name = excluded.name, country = excluded.country,
                        competition_type = excluded.competition_type,
                        parent_competition_provider_id = excluded.parent_competition_provider_id,
                        season_label = excluded.season_label, start_date = excluded.start_date,
                        end_date = excluded.end_date, team_type = excluded.team_type,
                        gender_scope = excluded.gender_scope, age_group = excluded.age_group,
                        squad_scope = excluded.squad_scope,
                        provider_updated_at = excluded.provider_updated_at,
                        last_seen_at = NOW(), raw_payload = excluded.raw_payload""",
                    (row["provider"], row["entity_type"], row["provider_entity_id"], row["name"],
                     row["country"], row["competition_type"], row["parent_competition_provider_id"],
                     row["season_label"], row["start_date"], row["end_date"], row["team_type"],
                     row["gender_scope"], row["age_group"], row["squad_scope"],
                     row["provider_updated_at"], Jsonb(row["raw_payload"])),
                )
                counts["entities"] += 1
            for row in bundle["fixtures"]:
                cursor.execute(
                    """INSERT INTO provider_source_fixtures (
                        provider, provider_fixture_id, competition_provider_id,
                        season_provider_id, home_team_provider_id, away_team_provider_id,
                        kickoff_utc, status, home_score, away_score, venue,
                        provider_updated_at, raw_payload
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (provider, provider_fixture_id) DO UPDATE SET
                        competition_provider_id = excluded.competition_provider_id,
                        season_provider_id = excluded.season_provider_id,
                        home_team_provider_id = excluded.home_team_provider_id,
                        away_team_provider_id = excluded.away_team_provider_id,
                        kickoff_utc = excluded.kickoff_utc, status = excluded.status,
                        home_score = excluded.home_score, away_score = excluded.away_score,
                        venue = excluded.venue, provider_updated_at = excluded.provider_updated_at,
                        last_seen_at = NOW(), raw_payload = excluded.raw_payload""",
                    (row["provider"], row["provider_fixture_id"], row["competition_provider_id"],
                     row["season_provider_id"], row["home_team_provider_id"], row["away_team_provider_id"],
                     row["kickoff_utc"], row["status"], row["home_score"], row["away_score"],
                     row["venue"], row["provider_updated_at"], Jsonb(row["raw_payload"])),
                )
                counts["fixtures"] += 1
            for row in bundle["statistics"]:
                cursor.execute(
                    """INSERT INTO provider_source_fixture_statistics (
                        provider, provider_fixture_id, provider_statistic_id, provider_team_id,
                        statistic_type, statistic_value, provider_updated_at, raw_payload
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (provider, provider_fixture_id, provider_statistic_id) DO UPDATE SET
                        provider_team_id = excluded.provider_team_id,
                        statistic_type = excluded.statistic_type,
                        statistic_value = excluded.statistic_value,
                        provider_updated_at = excluded.provider_updated_at,
                        last_seen_at = NOW(), raw_payload = excluded.raw_payload""",
                    (row["provider"], row["provider_fixture_id"], row["provider_statistic_id"],
                     row["provider_team_id"], row["statistic_type"], Jsonb(row["statistic_value"]),
                     row["provider_updated_at"], Jsonb(row["raw_payload"])),
                )
                counts["statistics"] += 1
    return counts


def audit_provider_source_evidence(database_url: str, provider: str) -> dict[str, Any]:
    """Read-only audit of provider-native staging rows; no canonical data is consulted."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    source = _provider(provider)
    entity_counts: dict[str, dict[str, int]] = {}
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(
                """SELECT entity_type, COUNT(*), COUNT(country), COUNT(competition_type),
                          COUNT(parent_competition_provider_id), COUNT(team_type),
                          COUNT(gender_scope), COUNT(age_group), COUNT(squad_scope)
                   FROM provider_source_entities
                   WHERE provider = %s
                   GROUP BY entity_type ORDER BY entity_type""",
                (source,),
            )
            for (entity_type, total, country_known, competition_type_known,
                 parent_competition_known, team_type_known, gender_known,
                 age_group_known, squad_scope_known) in cursor.fetchall():
                entity_counts[str(entity_type)] = {
                    "total": int(total or 0),
                    "country_known": int(country_known or 0),
                    "competition_type_known": int(competition_type_known or 0),
                    "parent_competition_known": int(parent_competition_known or 0),
                    "team_type_known": int(team_type_known or 0),
                    "gender_scope_known": int(gender_known or 0),
                    "age_group_known": int(age_group_known or 0),
                    "squad_scope_known": int(squad_scope_known or 0),
                }
            cursor.execute(
                """SELECT
                     COUNT(*) FILTER (WHERE raw_payload->>'team_evidence_complete' = 'false'),
                     COUNT(*) FILTER (WHERE jsonb_typeof(raw_payload->'competition_provider_ids') = 'array'),
                     COUNT(*) FILTER (WHERE country IS NULL)
                   FROM provider_source_entities
                   WHERE provider = %s AND entity_type = 'team'""",
                (source,),
            )
            team_row = cursor.fetchone() or (0, 0, 0)
            cursor.execute(
                """SELECT COUNT(*) FROM provider_source_fixtures WHERE provider = %s""",
                (source,),
            )
            fixture_count = int((cursor.fetchone() or (0,))[0] or 0)
            cursor.execute(
                """SELECT COUNT(*) FROM provider_source_fixture_statistics WHERE provider = %s""",
                (source,),
            )
            statistic_count = int((cursor.fetchone() or (0,))[0] or 0)
    return {
        "provider": source,
        "read_only": True,
        "database_writes": False,
        "entity_counts": entity_counts,
        "team_evidence": {
            "incomplete_participant_evidence_count": int(team_row[0] or 0),
            "competition_context_array_count": int(team_row[1] or 0),
            "country_missing_count": int(team_row[2] or 0),
        },
        "fixture_rows": fixture_count,
        "statistic_rows": statistic_count,
        "canonical_entities_created": 0,
        "cross_provider_links_created": 0,
        "prediction_ledger_touched": False,
    }
