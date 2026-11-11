"""CockroachDB storage for immutable provider API snapshots.

This store is deliberately separate from prediction_storage.py: Neon remains
the prediction-ledger database, while CockroachDB stores source observations.
Snapshots are append-only and retain provider/source provenance.
"""
from __future__ import annotations

import hashlib
import json
import uuid
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb


def _connect(database_url: str):
    """Connect to CockroachDB using the CA certificate shipped with the app."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    cert_path = Path(__file__).resolve().with_name("root.crt")
    if not cert_path.is_file():
        raise FileNotFoundError(
            f"CockroachDB CA certificate was not found at {cert_path}"
        )
    return psycopg.connect(
        database_url,
        connect_timeout=10,
        sslmode="verify-full",
        sslrootcert=str(cert_path),
    )


CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS provider_api_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    cache_key TEXT NOT NULL,
    provider TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    request_params JSONB NOT NULL,
    source_ids JSONB NOT NULL DEFAULT '[]'::JSONB,
    payload JSONB NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ,
    payload_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS provider_api_snapshots_cache_lookup
    ON provider_api_snapshots (cache_key, retrieved_at DESC);
CREATE INDEX IF NOT EXISTS provider_api_snapshots_provider_resource
    ON provider_api_snapshots (provider, resource_type, retrieved_at DESC);

CREATE TABLE IF NOT EXISTS provider_collection_runs (
    run_id TEXT PRIMARY KEY,
    cache_key TEXT NOT NULL,
    provider TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    attempted_at TIMESTAMPTZ NOT NULL,
    succeeded BOOLEAN NOT NULL,
    http_status INTEGER,
    error_type TEXT,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS provider_collection_runs_lookup
    ON provider_collection_runs (cache_key, attempted_at DESC);

CREATE TABLE IF NOT EXISTS provider_reliability_history (
    snapshot_id TEXT PRIMARY KEY,
    competition TEXT NOT NULL,
    season INTEGER NOT NULL,
    primary_provider TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    matches JSONB NOT NULL,
    matches_count INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS provider_reliability_history_scope
    ON provider_reliability_history (competition, season, captured_at DESC);

CREATE TABLE IF NOT EXISTS provider_conflict_resolution_audit (
    audit_id TEXT PRIMARY KEY,
    competition TEXT NOT NULL,
    season INTEGER NOT NULL,
    fixture_identity JSONB NOT NULL,
    field_name TEXT NOT NULL,
    triage_status TEXT NOT NULL,
    selected_provider TEXT,
    selected_value JSONB,
    observations JSONB NOT NULL,
    corroborating_providers JSONB NOT NULL,
    conflicting_providers JSONB NOT NULL,
    resolution_reason TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    manual_override BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS provider_conflict_audit_scope
    ON provider_conflict_resolution_audit (competition, season, recorded_at DESC);

CREATE TABLE IF NOT EXISTS provider_competition_registry (
    identity_key TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_competition_id TEXT NOT NULL,
    provider_season_id TEXT NOT NULL,
    competition_name TEXT NOT NULL,
    country TEXT NOT NULL,
    season_name TEXT NOT NULL,
    season_start TEXT,
    season_end TEXT,
    is_current BOOLEAN,
    discovery_status TEXT NOT NULL,
    registration_status TEXT NOT NULL,
    crosswalk_status TEXT NOT NULL,
    canonical_competition_id TEXT,
    prediction_ready BOOLEAN NOT NULL DEFAULT FALSE,
    readiness_reason TEXT NOT NULL,
    raw_competition JSONB NOT NULL,
    raw_season JSONB NOT NULL,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, provider_competition_id, provider_season_id)
);
CREATE INDEX IF NOT EXISTS provider_competition_registry_scope
    ON provider_competition_registry (provider, country, competition_name, season_name);
"""



_SCHEMA_INITIALIZATION_LOCK = threading.Lock()
_INITIALIZED_DATABASES: set[str] = set()


def _database_fingerprint(database_url: str) -> str:
    """Return a non-reversible key for process-local schema initialization state."""
    return hashlib.sha256(str(database_url).encode("utf-8")).hexdigest()


def _ensure_provider_storage_once(database_url: str, connection: Any) -> bool:
    """Create provider tables once, committing DDL before other workers proceed."""
    fingerprint = _database_fingerprint(database_url)
    if fingerprint in _INITIALIZED_DATABASES:
        return False
    with _SCHEMA_INITIALIZATION_LOCK:
        if fingerprint in _INITIALIZED_DATABASES:
            return False
        with connection.cursor() as cursor:
            for statement in CREATE_TABLES_SQL.split(";"):
                if statement.strip():
                    cursor.execute(statement)
        # Commit before publishing the initialized marker so concurrent writers
        # never try to insert while another worker's DDL is still uncommitted.
        connection.commit()
        _INITIALIZED_DATABASES.add(fingerprint)
    return True

FRESH_SNAPSHOT_SQL = """
SELECT snapshot_id, provider, resource_type, request_params, source_ids,
       payload, retrieved_at, expires_at, payload_sha256
FROM provider_api_snapshots
WHERE cache_key = %s AND expires_at > NOW()
ORDER BY retrieved_at DESC
LIMIT 1
"""

LATEST_SNAPSHOT_SQL = """
SELECT snapshot_id, provider, resource_type, request_params, source_ids,
       payload, retrieved_at, expires_at, payload_sha256
FROM provider_api_snapshots
WHERE cache_key = %s
ORDER BY retrieved_at DESC
LIMIT 1
"""

INSERT_SNAPSHOT_SQL = """
INSERT INTO provider_api_snapshots (
    snapshot_id, cache_key, provider, resource_type, request_params,
    source_ids, payload, retrieved_at, expires_at, payload_sha256
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

INSERT_RUN_SQL = """
INSERT INTO provider_collection_runs (
    run_id, cache_key, provider, resource_type, attempted_at,
    succeeded, http_status, error_type, error_message
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def _json_safe(value: Any) -> Any:
    """Normalize API payloads and metadata to strict JSON-compatible values."""
    return json.loads(
        json.dumps(value, ensure_ascii=False, default=str, allow_nan=False)
    )


def build_provider_cache_key(
    provider: str, resource_type: str, request_params: Mapping[str, Any]
) -> str:
    """Create a stable, provider-scoped key; callers must omit credentials."""
    provider_name = str(provider).strip().lower()
    resource_name = str(resource_type).strip().lower()
    if not provider_name or not resource_name:
        raise ValueError("provider and resource_type are required.")
    params = _json_safe(dict(request_params))
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{provider_name}:{resource_name}:{digest}"


def ensure_provider_storage(database_url: str) -> None:
    """Create provider tables once per database per process."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    with _connect(database_url) as connection:
        _ensure_provider_storage_once(database_url, connection)


def check_provider_storage_connection(database_url: str) -> bool:
    """Create required tables and verify a live CockroachDB SQL round trip."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    ensure_provider_storage(database_url)
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
    if row != (1,):
        raise RuntimeError("CockroachDB connection check returned an unexpected result.")
    return True


def _snapshot_from_row(row: tuple[Any, ...]) -> dict[str, Any]:
    names = (
        "snapshot_id", "provider", "resource_type", "request_params",
        "source_ids", "payload", "retrieved_at", "expires_at", "payload_sha256",
    )
    return dict(zip(names, row))


def load_provider_snapshot(
    database_url: str, cache_key: str, *, allow_stale: bool = False
) -> dict[str, Any] | None:
    """Return the latest fresh snapshot, or latest historical snapshot if requested."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    query = LATEST_SNAPSHOT_SQL if allow_stale else FRESH_SNAPSHOT_SQL
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (cache_key,))
            row = cursor.fetchone()
    return _snapshot_from_row(row) if row else None


def load_provider_observation_snapshots(
    database_url: str,
    *,
    provider: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Load recent archived future-fixture observation batches for crosswalk review."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("limit must be an integer from 1 through 1000.")
    provider_name = str(provider).strip().lower() if provider else None
    if provider_name and provider_name not in {
        "openligadb", "openfootball", "open_matchday", "livescore_football", "bzzoiro",
        "highlightly", "api_ninjas"
    }:
        raise ValueError("Unsupported future-fixture provider.")
    ensure_provider_storage(database_url)
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            if provider_name:
                cursor.execute(
                    """SELECT snapshot_id, provider, resource_type, request_params,
                              source_ids, payload, retrieved_at, expires_at, payload_sha256
                       FROM provider_api_snapshots
                       WHERE resource_type = %s AND provider = %s
                       ORDER BY retrieved_at DESC, snapshot_id DESC
                       LIMIT %s""",
                    ("future_fixture_observations", provider_name, limit),
                )
            else:
                cursor.execute(
                    """SELECT snapshot_id, provider, resource_type, request_params,
                              source_ids, payload, retrieved_at, expires_at, payload_sha256
                       FROM provider_api_snapshots
                       WHERE resource_type = %s
                       ORDER BY retrieved_at DESC, snapshot_id DESC
                       LIMIT %s""",
                    ("future_fixture_observations", limit),
                )
            rows = cursor.fetchall()
    return [_snapshot_from_row(row) for row in rows]


def save_provider_snapshot(
    database_url: str,
    *,
    provider: str,
    resource_type: str,
    cache_key: str,
    request_params: Mapping[str, Any],
    payload: Any,
    source_ids: Any = None,
    ttl_seconds: int = 1800,
    retrieved_at: datetime | None = None,
) -> str:
    """Append a successful provider response and return its immutable snapshot ID."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    if not provider or not resource_type or not cache_key:
        raise ValueError("provider, resource_type and cache_key are required.")
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or ttl_seconds < 0:
        raise ValueError("ttl_seconds must be a non-negative integer.")
    safe_payload = _json_safe(payload)
    safe_params = _json_safe(dict(request_params))
    safe_source_ids = _json_safe(source_ids if source_ids is not None else [])
    if not isinstance(safe_payload, (dict, list)):
        raise ValueError("Provider payload must be a JSON object or array.")
    captured = retrieved_at or datetime.now(timezone.utc)
    if captured.tzinfo is None:
        captured = captured.replace(tzinfo=timezone.utc)
    expires = captured + timedelta(seconds=ttl_seconds) if ttl_seconds else None
    payload_text = json.dumps(safe_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    payload_hash = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    snapshot_id = str(uuid.uuid4())

    with _connect(database_url) as connection:
        _ensure_provider_storage_once(database_url, connection)
        with connection.cursor() as cursor:
            cursor.execute(
                INSERT_SNAPSHOT_SQL,
                (
                    snapshot_id, cache_key, provider.strip().lower(),
                    resource_type.strip().lower(), Jsonb(safe_params),
                    Jsonb(safe_source_ids), Jsonb(safe_payload), captured,
                    expires, payload_hash,
                ),
            )
    return snapshot_id



def verify_provider_storage_round_trip(database_url: str) -> dict[str, Any]:
    """Write and read back a short-lived diagnostic snapshot in CockroachDB."""
    test_id = str(uuid.uuid4())
    request_params = {"diagnostic_id": test_id}
    cache_key = build_provider_cache_key(
        "internal", "storage_diagnostic", request_params
    )
    payload = {
        "diagnostic": "provider_storage_round_trip",
        "diagnostic_id": test_id,
        "message": "CockroachDB write/read verification",
    }
    snapshot_id = save_provider_snapshot(
        database_url,
        provider="internal",
        resource_type="storage_diagnostic",
        cache_key=cache_key,
        request_params=request_params,
        payload=payload,
        source_ids=[],
        ttl_seconds=300,
    )
    stored = load_provider_snapshot(database_url, cache_key)
    if not stored:
        raise RuntimeError("CockroachDB saved the diagnostic but could not retrieve it.")
    if stored.get("snapshot_id") != snapshot_id or stored.get("payload") != payload:
        raise RuntimeError("CockroachDB returned diagnostic data that did not match the saved record.")
    return {
        "success": True,
        "snapshot_id": snapshot_id,
        "payload_sha256": stored.get("payload_sha256"),
        "expires_at": stored.get("expires_at"),
    }


def record_provider_collection_run(
    database_url: str,
    *,
    provider: str,
    resource_type: str,
    cache_key: str,
    succeeded: bool,
    http_status: int | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    attempted_at: datetime | None = None,
) -> str:
    """Append collection diagnostics without replacing the last successful snapshot."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    attempted = attempted_at or datetime.now(timezone.utc)
    if attempted.tzinfo is None:
        attempted = attempted.replace(tzinfo=timezone.utc)
    run_id = str(uuid.uuid4())
    message = str(error_message)[:1000] if error_message else None
    with _connect(database_url) as connection:
        _ensure_provider_storage_once(database_url, connection)
        with connection.cursor() as cursor:
            cursor.execute(
                INSERT_RUN_SQL,
                (
                    run_id, cache_key, provider.strip().lower(),
                    resource_type.strip().lower(), attempted, bool(succeeded),
                    http_status, error_type, message,
                ),
            )
    return run_id


def save_provider_snapshot_and_record_run(
    database_url: str,
    *,
    provider: str,
    resource_type: str,
    cache_key: str,
    request_params: Mapping[str, Any],
    payload: Any,
    source_ids: Any = None,
    ttl_seconds: int = 1800,
    retrieved_at: datetime | None = None,
    http_status: int | None = None,
) -> dict[str, Any]:
    """Save an immutable snapshot and success audit row using one DB connection.

    The snapshot is committed before the best-effort audit insert, preserving it
    if that secondary insert fails while reusing the same connection.
    """
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    if not provider or not resource_type or not cache_key:
        raise ValueError("provider, resource_type and cache_key are required.")
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or ttl_seconds < 0:
        raise ValueError("ttl_seconds must be a non-negative integer.")
    safe_payload = _json_safe(payload)
    safe_params = _json_safe(dict(request_params))
    safe_source_ids = _json_safe(source_ids if source_ids is not None else [])
    if not isinstance(safe_payload, (dict, list)):
        raise ValueError("Provider payload must be a JSON object or array.")
    captured = retrieved_at or datetime.now(timezone.utc)
    if captured.tzinfo is None:
        captured = captured.replace(tzinfo=timezone.utc)
    expires = captured + timedelta(seconds=ttl_seconds) if ttl_seconds else None
    payload_text = json.dumps(safe_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    payload_hash = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    snapshot_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    attempted = datetime.now(timezone.utc)

    run_recorded = True
    run_error_type = None
    with _connect(database_url) as connection:
        _ensure_provider_storage_once(database_url, connection)
        with connection.cursor() as cursor:
            cursor.execute(
                INSERT_SNAPSHOT_SQL,
                (
                    snapshot_id, cache_key, provider.strip().lower(),
                    resource_type.strip().lower(), Jsonb(safe_params),
                    Jsonb(safe_source_ids), Jsonb(safe_payload), captured,
                    expires, payload_hash,
                ),
            )
        # Commit the immutable source observation first. The optional audit row
        # must never cause a successfully archived provider response to roll back.
        connection.commit()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    INSERT_RUN_SQL,
                    (
                        run_id, cache_key, provider.strip().lower(),
                        resource_type.strip().lower(), attempted, True,
                        http_status, None, None,
                    ),
                )
            connection.commit()
        except Exception as exc:
            run_recorded = False
            run_error_type = type(exc).__name__
            connection.rollback()

    return {
        "snapshot_id": snapshot_id,
        "run_id": run_id if run_recorded else None,
        "run_recorded": run_recorded,
        "run_error_type": run_error_type,
    }


INSERT_PROVIDER_RELIABILITY_SQL = """
INSERT INTO provider_reliability_history (
    snapshot_id, competition, season, primary_provider, captured_at,
    matches, matches_count
) VALUES (%s, %s, %s, %s, %s, %s, %s)
"""

LOAD_PROVIDER_RELIABILITY_SQL = """
SELECT snapshot_id, competition, season, primary_provider, captured_at,
       matches, matches_count
FROM provider_reliability_history
WHERE competition = %s AND season = %s
  AND captured_at >= NOW() - INTERVAL '90 days'
ORDER BY captured_at DESC
LIMIT %s
"""


def save_provider_reliability_snapshot(
    database_url: str,
    *,
    competition: str,
    season: int,
    primary_provider: str,
    matches: Any,
    captured_at: datetime | None = None,
) -> str:
    """Append exact-fixture corroboration evidence for rolling reliability analysis."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    competition_name = str(competition or "").strip()
    provider_name = str(primary_provider or "").strip().lower()
    if not competition_name or not provider_name:
        raise ValueError("competition and primary_provider are required.")
    if isinstance(season, bool) or not isinstance(season, int) or season < 1:
        raise ValueError("season must be a positive integer.")
    safe_matches = _json_safe(matches if matches is not None else [])
    if not isinstance(safe_matches, list):
        raise ValueError("matches must be a JSON array.")
    if any(not isinstance(row, dict) for row in safe_matches):
        raise ValueError("Every reliability match must be a JSON object.")
    captured = captured_at or datetime.now(timezone.utc)
    if captured.tzinfo is None:
        captured = captured.replace(tzinfo=timezone.utc)
    snapshot_id = str(uuid.uuid4())
    with _connect(database_url) as connection:
        _ensure_provider_storage_once(database_url, connection)
        with connection.cursor() as cursor:
            cursor.execute(
                INSERT_PROVIDER_RELIABILITY_SQL,
                (
                    snapshot_id, competition_name, season, provider_name,
                    captured, Jsonb(safe_matches), len(safe_matches),
                ),
            )
    return snapshot_id


def load_provider_reliability_history(
    database_url: str,
    *,
    competition: str,
    season: int,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Load append-only reliability evidence from the last 90 days."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    if not str(competition or "").strip():
        raise ValueError("competition is required.")
    if isinstance(season, bool) or not isinstance(season, int) or season < 1:
        raise ValueError("season must be a positive integer.")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 2000:
        raise ValueError("limit must be an integer between 1 and 2000.")
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                LOAD_PROVIDER_RELIABILITY_SQL,
                (str(competition).strip(), season, limit),
            )
            rows = cursor.fetchall()
    names = (
        "snapshot_id", "competition", "season", "primary_provider",
        "captured_at", "matches", "matches_count",
    )
    return [dict(zip(names, row)) for row in rows]


INSERT_CONFLICT_AUDIT_SQL = """
INSERT INTO provider_conflict_resolution_audit (
    audit_id, competition, season, fixture_identity, field_name,
    triage_status, selected_provider, selected_value, observations,
    corroborating_providers, conflicting_providers, resolution_reason,
    recorded_at, manual_override
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

LOAD_CONFLICT_AUDIT_SQL = """
SELECT audit_id, competition, season, fixture_identity, field_name,
       triage_status, selected_provider, selected_value, observations,
       corroborating_providers, conflicting_providers, resolution_reason,
       recorded_at, manual_override
FROM provider_conflict_resolution_audit
WHERE competition = %s AND season = %s
  AND recorded_at >= NOW() - INTERVAL '90 days'
ORDER BY recorded_at DESC
LIMIT %s
"""


def save_conflict_resolution_audit(
    database_url: str,
    *,
    events: list[Mapping[str, Any]],
) -> int:
    """Append conflict decisions and their complete observations atomically."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    if not isinstance(events, list):
        raise ValueError("events must be a list.")
    if not events:
        return 0
    prepared = []
    for event in events:
        if not isinstance(event, Mapping):
            raise ValueError("Every conflict audit event must be an object.")
        competition = str(event.get("competition") or "").strip()
        season = event.get("season")
        field_name = str(event.get("field") or "").strip()
        status = str(event.get("triage_status") or "").strip()
        if not competition or isinstance(season, bool) or not isinstance(season, int) or season < 1:
            raise ValueError("Each event requires a competition and positive integer season.")
        if not field_name or status not in {"resolved_by_configured_priority", "unresolved"}:
            raise ValueError("Each event requires a field and supported triage status.")
        fixture_identity = _json_safe(event.get("fixture_identity") or {})
        observations = _json_safe(event.get("observations") or [])
        if not isinstance(fixture_identity, dict) or not isinstance(observations, list):
            raise ValueError("Fixture identity must be an object and observations an array.")
        recorded_at = event.get("recorded_at")
        if isinstance(recorded_at, str):
            recorded_at = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
        if not isinstance(recorded_at, datetime):
            raise ValueError("Each event requires a valid recorded_at timestamp.")
        if recorded_at.tzinfo is None:
            recorded_at = recorded_at.replace(tzinfo=timezone.utc)
        prepared.append((
            str(uuid.uuid4()), competition, season, Jsonb(fixture_identity),
            field_name, status, event.get("selected_provider"),
            Jsonb(_json_safe(event.get("selected_value"))),
            Jsonb(observations),
            Jsonb(_json_safe(event.get("corroborating_providers") or [])),
            Jsonb(_json_safe(event.get("conflicting_providers") or [])),
            str(event.get("resolution_reason") or ""),
            recorded_at.astimezone(timezone.utc),
            bool(event.get("manual_override", False)),
        ))
    with _connect(database_url) as connection:
        _ensure_provider_storage_once(database_url, connection)
        with connection.cursor() as cursor:
            for row in prepared:
                cursor.execute(INSERT_CONFLICT_AUDIT_SQL, row)
    return len(prepared)


def load_conflict_resolution_audit(
    database_url: str,
    *,
    competition: str,
    season: int,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Load recent immutable conflict decisions for one competition/season."""
    if not database_url or not str(competition or "").strip():
        raise ValueError("database_url and competition are required.")
    if isinstance(season, bool) or not isinstance(season, int) or season < 1:
        raise ValueError("season must be a positive integer.")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("limit must be an integer between 1 and 1000.")
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(LOAD_CONFLICT_AUDIT_SQL, (str(competition).strip(), season, limit))
            rows = cursor.fetchall()
    names = (
        "audit_id", "competition", "season", "fixture_identity", "field_name",
        "triage_status", "selected_provider", "selected_value", "observations",
        "corroborating_providers", "conflicting_providers", "resolution_reason",
        "recorded_at", "manual_override",
    )
    return [dict(zip(names, row)) for row in rows]


UPSERT_COMPETITION_REGISTRY_SQL = """
INSERT INTO provider_competition_registry (
    identity_key, provider, provider_competition_id, provider_season_id,
    competition_name, country, season_name, season_start, season_end,
    is_current, discovery_status, registration_status, crosswalk_status,
    canonical_competition_id, prediction_ready, readiness_reason,
    raw_competition, raw_season, discovered_at, updated_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
ON CONFLICT (identity_key) DO UPDATE SET
    competition_name = excluded.competition_name,
    country = excluded.country,
    season_name = excluded.season_name,
    season_start = excluded.season_start,
    season_end = excluded.season_end,
    is_current = excluded.is_current,
    discovery_status = excluded.discovery_status,
    registration_status = excluded.registration_status,
    raw_competition = excluded.raw_competition,
    raw_season = excluded.raw_season,
    updated_at = NOW()
"""

def save_discovered_competition_registry(
    database_url: str, *, records: list[Mapping[str, Any]]
) -> int:
    """Upsert provider-scoped discovered competitions without promoting readiness."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    if not isinstance(records, list):
        raise ValueError("records must be a list.")
    prepared = []
    for row in records:
        if not isinstance(row, Mapping):
            raise ValueError("Each registry record must be an object.")
        required = (
            "identity_key", "provider", "provider_competition_id",
            "provider_season_id", "competition_name", "season_name",
        )
        if any(not str(row.get(key) or "").strip() for key in required):
            raise ValueError("Registry records require provider, competition/season IDs, name, country and season.")
        if row.get("prediction_ready") is not False:
            raise ValueError("Discovery cannot promote a competition to prediction-ready.")
        prepared.append((
            str(row["identity_key"]), str(row["provider"]),
            str(row["provider_competition_id"]), str(row["provider_season_id"]),
            str(row["competition_name"]), str(row["country"]),
            str(row["season_name"]), str(row.get("season_start") or ""),
            str(row.get("season_end") or ""), row.get("is_current"),
            str(row.get("discovery_status") or "discovered"),
            str(row.get("registration_status") or "registered"),
            str(row.get("crosswalk_status") or "unmapped"),
            row.get("canonical_competition_id"), False,
            str(row.get("readiness_reason") or "Independent identity and quality validation required."),
            Jsonb(_json_safe(row.get("raw_competition") or {})),
            Jsonb(_json_safe(row.get("raw_season") or {})),
        ))
    if not prepared:
        return 0
    with _connect(database_url) as connection:
        _ensure_provider_storage_once(database_url, connection)
        with connection.cursor() as cursor:
            for row in prepared:
                cursor.execute(UPSERT_COMPETITION_REGISTRY_SQL, row)
    return len(prepared)


def load_competition_registry(
    database_url: str, *, provider: str | None = None, limit: int = 1000
) -> list[dict[str, Any]]:
    """Read registered competition-season rows; newest discovery first."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 5000:
        raise ValueError("limit must be between 1 and 5000.")
    query = """
    SELECT identity_key, provider, provider_competition_id, provider_season_id,
           competition_name, country, season_name, season_start, season_end,
           is_current, discovery_status, registration_status, crosswalk_status,
           canonical_competition_id, prediction_ready, readiness_reason,
           discovered_at, updated_at
    FROM provider_competition_registry
    {provider_filter}
    ORDER BY country, competition_name, season_name, provider
    LIMIT %s
    """
    provider_filter = "WHERE provider = %s" if provider else ""
    params = (provider, limit) if provider else (limit,)
    with _connect(database_url) as connection:
        _ensure_provider_storage_once(database_url, connection)
        with connection.cursor() as cursor:
            cursor.execute(query.format(provider_filter=provider_filter), params)
            rows = cursor.fetchall()
    names = (
        "identity_key", "provider", "provider_competition_id", "provider_season_id",
        "competition_name", "country", "season_name", "season_start", "season_end",
        "is_current", "discovery_status", "registration_status", "crosswalk_status",
        "canonical_competition_id", "prediction_ready", "readiness_reason",
        "discovered_at", "updated_at",
    )
    return [dict(zip(names, row)) for row in rows]
