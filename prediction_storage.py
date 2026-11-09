"""Neon/PostgreSQL persistence for the prediction ledger.

The database stores each complete, auditable ledger row as JSONB. Stable
record IDs prevent duplicate inserts, and blank CSV/editor values never erase
previously saved non-empty fields.
"""
from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

import psycopg
from psycopg.types.json import Jsonb

from prediction_evaluation import merge_prediction_records


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS prediction_ledger (
    record_id TEXT PRIMARY KEY,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

SELECT_ALL_SQL = """
SELECT payload
FROM prediction_ledger
ORDER BY created_at ASC, record_id ASC
"""

SELECT_MANY_SQL = """
SELECT record_id, payload
FROM prediction_ledger
WHERE record_id = ANY(%s)
"""

UPSERT_SQL = """
INSERT INTO prediction_ledger (record_id, payload)
VALUES (%s, %s)
ON CONFLICT (record_id) DO UPDATE
SET payload = EXCLUDED.payload,
    updated_at = NOW()
"""


def _clean_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Convert pandas/numpy-compatible values to strict JSON-safe values."""
    cleaned = json.loads(json.dumps(dict(record), ensure_ascii=False, default=str, allow_nan=False))
    record_id = str(cleaned.get("record_id") or "").strip()
    if not record_id:
        raise ValueError("Every prediction ledger row must have a stable record_id.")
    cleaned["record_id"] = record_id
    return cleaned


def load_prediction_ledger(database_url: str) -> list[dict[str, Any]]:
    """Create the table if needed and return all saved prediction records."""
    if not database_url:
        raise ValueError("DATABASE_URL is required.")
    with psycopg.connect(database_url, connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)
            cursor.execute(SELECT_ALL_SQL)
            rows = cursor.fetchall()
    records = []
    for row in rows:
        payload = row[0]
        if isinstance(payload, dict) and payload.get("record_id"):
            records.append(payload)
    return records


def save_prediction_records(
    database_url: str, records: Iterable[Mapping[str, Any]]
) -> int:
    """Batch ledger reads and writes while preserving stable-ID merge semantics."""
    if not database_url:
        raise ValueError("DATABASE_URL is required.")

    cleaned_records = [_clean_record(row) for row in records]
    with psycopg.connect(database_url, connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)

            if cleaned_records:
                record_ids = list(dict.fromkeys(row["record_id"] for row in cleaned_records))
                cursor.execute(SELECT_MANY_SQL, (record_ids,))
                existing_by_id = {
                    str(record_id): payload
                    for record_id, payload in cursor.fetchall()
                    if isinstance(payload, dict)
                }

                merged_by_id = dict(existing_by_id)
                for incoming in cleaned_records:
                    existing = merged_by_id.get(incoming["record_id"])
                    merged = merge_prediction_records(
                        [existing] if isinstance(existing, dict) else [],
                        [incoming],
                    )
                    if merged:
                        merged_by_id[incoming["record_id"]] = merged[0]

                cursor.executemany(
                    UPSERT_SQL,
                    [
                        (record_id, Jsonb(merged_by_id[record_id]))
                        for record_id in record_ids
                        if record_id in merged_by_id
                    ],
                )

            cursor.execute("SELECT COUNT(*) FROM prediction_ledger")
            count = cursor.fetchone()[0]
    return int(count)
