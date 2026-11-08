"""CockroachDB storage for immutable provider API snapshots.

This store is deliberately separate from prediction_storage.py: Neon remains
the prediction-ledger database, while CockroachDB stores source observations.
Snapshots are append-only and retain provider/source provenance.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import psycopg
from psycopg.types.json import Jsonb


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
"""

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
    """Create provider snapshot and collection-run tables if they do not exist."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    with psycopg.connect(database_url, connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            for statement in CREATE_TABLES_SQL.split(";"):
                if statement.strip():
                    cursor.execute(statement)


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
    with psycopg.connect(database_url, connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (cache_key,))
            row = cursor.fetchone()
    return _snapshot_from_row(row) if row else None


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

    with psycopg.connect(database_url, connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            for statement in CREATE_TABLES_SQL.split(";"):
                if statement.strip():
                    cursor.execute(statement)
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
    with psycopg.connect(database_url, connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            for statement in CREATE_TABLES_SQL.split(";"):
                if statement.strip():
                    cursor.execute(statement)
            cursor.execute(
                INSERT_RUN_SQL,
                (
                    run_id, cache_key, provider.strip().lower(),
                    resource_type.strip().lower(), attempted, bool(succeeded),
                    http_status, error_type, message,
                ),
            )
    return run_id
