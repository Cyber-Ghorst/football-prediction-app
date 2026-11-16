"""Persist official team-scope review evidence separately from source and canonical records."""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from psycopg.types.json import Jsonb

from provider_data_storage import _connect
from provider_official_team_scope_audit import audit_official_team_scope

REPORT = Path("provider-official-team-scope-stage-report.json")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS provider_official_team_scope_evidence (
    provider TEXT NOT NULL,
    provider_entity_id TEXT NOT NULL,
    competition_provider_id TEXT NOT NULL,
    season_label TEXT NOT NULL,
    official_competition_key TEXT NOT NULL,
    official_team_name TEXT,
    scope_candidate JSONB,
    official_reference_url TEXT NOT NULL,
    source_endpoint TEXT,
    source_retrieved_at TIMESTAMPTZ,
    provider_evidence_method TEXT,
    provider_roster_observation_complete BOOLEAN NOT NULL DEFAULT FALSE,
    evidence_status TEXT NOT NULL,
    promotion_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    evidence_snapshot JSONB NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (
        provider, provider_entity_id, competition_provider_id, season_label
    )
);
CREATE INDEX IF NOT EXISTS provider_official_team_scope_evidence_status_idx
    ON provider_official_team_scope_evidence (evidence_status, provider, season_label);
"""


def _timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("source_retrieved_at must include a timezone.")
    return result


def build_official_scope_stage_rows(
    audit_report: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build separate evidence rows; never mutate provider source or canonical entities."""
    rows = []
    for candidate in audit_report.get("candidates") or []:
        rows.append({
            "provider": str(candidate.get("provider") or ""),
            "provider_entity_id": str(candidate.get("provider_entity_id") or ""),
            "competition_provider_id": str(candidate.get("competition_provider_id") or ""),
            "season_label": str(candidate.get("season_label") or "unknown"),
            "official_competition_key": str(candidate.get("competition_key") or ""),
            "official_team_name": candidate.get("official_team_name"),
            "scope_candidate": candidate.get("scope_candidate"),
            "official_reference_url": str(candidate.get("official_reference_url") or ""),
            "source_endpoint": candidate.get("source_endpoint"),
            "source_retrieved_at": _timestamp(candidate.get("source_retrieved_at")),
            "provider_evidence_method": candidate.get("team_evidence_method"),
            "provider_roster_observation_complete": bool(
                candidate.get("provider_roster_observation_complete")
            ),
            "evidence_status": str(candidate.get("status") or "held_unclassified"),
            "promotion_allowed": False,
            "evidence_snapshot": dict(candidate),
        })
    for row in rows:
        required = (
            row["provider"], row["provider_entity_id"],
            row["competition_provider_id"], row["official_competition_key"],
            row["official_reference_url"], row["evidence_status"],
        )
        if any(not str(value).strip() for value in required):
            raise ValueError("Official team-scope evidence row is missing a required identity field.")
    return rows


def stage_official_team_scope_evidence(database_url: str) -> dict[str, Any]:
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    audit = audit_official_team_scope(database_url)
    rows = build_official_scope_stage_rows(audit)
    inserted_or_updated = 0
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            for statement in CREATE_TABLE_SQL.split(";"):
                if statement.strip():
                    cursor.execute(statement)
            for row in rows:
                cursor.execute(
                    """INSERT INTO provider_official_team_scope_evidence (
                           provider, provider_entity_id, competition_provider_id,
                           season_label, official_competition_key, official_team_name,
                           scope_candidate, official_reference_url, source_endpoint,
                           source_retrieved_at, provider_evidence_method,
                           provider_roster_observation_complete, evidence_status,
                           promotion_allowed, evidence_snapshot
                       ) VALUES (
                           %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                           %s, %s, %s, FALSE, %s
                       )
                       ON CONFLICT (
                           provider, provider_entity_id, competition_provider_id, season_label
                       ) DO UPDATE SET
                           official_competition_key = EXCLUDED.official_competition_key,
                           official_team_name = EXCLUDED.official_team_name,
                           scope_candidate = EXCLUDED.scope_candidate,
                           official_reference_url = EXCLUDED.official_reference_url,
                           source_endpoint = EXCLUDED.source_endpoint,
                           source_retrieved_at = EXCLUDED.source_retrieved_at,
                           provider_evidence_method = EXCLUDED.provider_evidence_method,
                           provider_roster_observation_complete = EXCLUDED.provider_roster_observation_complete,
                           evidence_status = EXCLUDED.evidence_status,
                           promotion_allowed = FALSE,
                           evidence_snapshot = EXCLUDED.evidence_snapshot,
                           last_seen_at = NOW()""",
                    (
                        row["provider"], row["provider_entity_id"],
                        row["competition_provider_id"], row["season_label"],
                        row["official_competition_key"], row["official_team_name"],
                        Jsonb(row["scope_candidate"]) if row["scope_candidate"] is not None else None,
                        row["official_reference_url"], row["source_endpoint"],
                        row["source_retrieved_at"], row["provider_evidence_method"],
                        row["provider_roster_observation_complete"], row["evidence_status"],
                        Jsonb(row["evidence_snapshot"]),
                    ),
                )
                inserted_or_updated += max(cursor.rowcount, 0)
    report = {
        "checked_at": datetime.now().astimezone().isoformat(),
        "read_only_source_audit": True,
        "official_scope_evidence_table_written": True,
        "provider_source_entities_modified": 0,
        "canonical_ids_assigned": 0,
        "provider_links_created": 0,
        "provider_scope_fields_updated": 0,
        "promotion_allowed": False,
        "evidence_rows_upserted": inserted_or_updated,
        "candidate_count": len(rows),
        "evidence_status_counts": dict(Counter(row["evidence_status"] for row in rows)),
        "provider_counts": dict(Counter(row["provider"] for row in rows)),
        "source_audit_checked_at": audit.get("checked_at"),
        "source_rows_examined": audit.get("source_rows_examined"),
        "report": str(REPORT),
        "interpretation": (
            "Evidence is stored in a separate review table only. It does not update "
            "provider_source_entities, team scope columns, canonical IDs, provider links, "
            "fixtures, predictions, model weights, TVD or prediction-ledger records."
        ),
    }
    return report


def main() -> int:
    report = stage_official_team_scope_evidence(
        os.getenv("PROVIDER_DATABASE_URL", "").strip()
    )
    REPORT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
