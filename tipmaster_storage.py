"""Neon persistence for independent TipMaster benchmark snapshots.

This table is separate from prediction_ledger. Benchmark records are immutable
source observations and never become prediction inputs.
"""
from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

import psycopg
from psycopg.types.json import Jsonb


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tipmaster_benchmark_records (
    source_match_id TEXT PRIMARY KEY,
    payload JSONB NOT NULL,
    kickoff_at TIMESTAMPTZ NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

UPSERT_SQL = """
INSERT INTO tipmaster_benchmark_records
    (source_match_id, payload, kickoff_at, fetched_at)
VALUES (%s, %s, %s::timestamptz, %s::timestamptz)
ON CONFLICT (source_match_id) DO UPDATE
SET payload = EXCLUDED.payload,
    kickoff_at = EXCLUDED.kickoff_at,
    fetched_at = EXCLUDED.fetched_at,
    updated_at = NOW()
WHERE EXCLUDED.fetched_at >= tipmaster_benchmark_records.fetched_at
"""

SELECT_SQL = """
SELECT payload
FROM tipmaster_benchmark_records
WHERE kickoff_at >= NOW() - INTERVAL '365 days'
ORDER BY kickoff_at DESC, source_match_id
LIMIT 5000
"""


def _clean_record(record: Mapping[str, Any]) -> tuple[str, dict[str, Any], str, str]:
    payload = json.loads(json.dumps(dict(record), ensure_ascii=False, default=str, allow_nan=False))
    source_match_id = str(payload.get("source_match_id") or "").strip()
    kickoff_at = str(payload.get("kickoff_at") or "").strip()
    fetched_at = str(payload.get("fetched_at") or "").strip()
    if not source_match_id or not kickoff_at or not fetched_at:
        raise ValueError("TipMaster records require source_match_id, kickoff_at and fetched_at.")
    if payload.get("source") != "tipmaster" or payload.get("prediction_inputs_eligible") is not False:
        raise ValueError("Only isolated TipMaster benchmark records may be persisted.")
    if not isinstance(payload.get("groups"), dict) or not payload["groups"]:
        raise ValueError("TipMaster benchmark record must contain validated cohort groups.")
    return source_match_id, payload, kickoff_at, fetched_at


def save_tipmaster_benchmark_records(
    database_url: str, records: Iterable[Mapping[str, Any]]
) -> int:
    if not database_url:
        raise ValueError("DATABASE_URL is required for TipMaster benchmark storage.")
    prepared = [_clean_record(row) for row in records]
    if not prepared:
        return 0
    ids = [item[0] for item in prepared]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate TipMaster source_match_id values in one batch.")
    with psycopg.connect(database_url, connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)
            cursor.executemany(
                UPSERT_SQL,
                [(key, Jsonb(payload), kickoff, fetched) for key, payload, kickoff, fetched in prepared],
            )
    return len(prepared)


def load_tipmaster_benchmark_records(database_url: str) -> list[dict[str, Any]]:
    if not database_url:
        raise ValueError("DATABASE_URL is required for TipMaster benchmark storage.")
    with psycopg.connect(database_url, connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)
            cursor.execute(SELECT_SQL)
            rows = cursor.fetchall()
    return [
        payload for (payload,) in rows
        if isinstance(payload, dict)
        and payload.get("source") == "tipmaster"
        and payload.get("prediction_inputs_eligible") is False
    ]
