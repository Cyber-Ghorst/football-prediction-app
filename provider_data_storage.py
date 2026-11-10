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
"""



_SCHEMA_INITIALIZATION_LOCK = threading.Lock()
_INITIALIZED_DATABASES: set[str] = set()


def _database_fingerprint(database_url: str) -> str:
    """Return a non-reversible key for process-local schema initialization state."""
    return hashlib.sha256(str(database_url).encode("utf-8")).hexdigest()


def _ensure_provider_storage_once(database_url: str) -> bool:
    """Create provider tables once per database per process, committing before release."""
    fingerprint = _database_fingerprint(database_url)
    if fingerprint in _INITIALIZED_DATABASES:
        return False
    with _SCHEMA_INITIALIZATION_LOCK:
        if fingerprint in _INITIALIZED_DATABASES:
            return False
        with _connect(database_url) as connection:
            with connection.cursor() as cursor:
                for statement in CREATE_TABLES_SQL.split(";"):
                    if statement.strip():
                        cursor.execute(statement)
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
    _ensure_provider_storage_once(database_url)


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

    _ensure_provider_storage_once(database_url)
    with _connect(database_url) as connection:
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
    _ensure_provider_storage_once(database_url)
    with _connect(database_url) as connection:
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

    _ensure_provider_storage_once(database_url)
    run_recorded = True
    run_error_type = None
    with _connect(database_url) as connection:
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
