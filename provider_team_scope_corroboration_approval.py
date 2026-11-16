"""Record approved cross-provider team-scope corroboration without creating identity links.

Only unique exact-name matches within mapped current domestic competitions are
accepted. API Ninjas country/type/gender values are preserved in a separate
corroboration table; target provider source rows and canonical repositories are
not modified.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from psycopg.types.json import Jsonb

from provider_data_storage import _connect
from provider_team_scope_corroboration_audit import audit_team_scope_corroboration

REPORT = Path("provider-team-scope-corroboration-approval-report.json")
APPROVAL_REASON = (
    "Layer 12 reviewed scope corroboration: unique exact normalized team name "
    "within the same current domestic competition; API Ninjas explicitly reports "
    "active club, ISO country code and men's gender. This is scope evidence only, "
    "not a canonical team identity or provider link."
)
TABLE_SQL = """
CREATE TABLE IF NOT EXISTS provider_team_scope_corroborations (
    corroboration_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_entity_id TEXT NOT NULL,
    corroborating_provider TEXT NOT NULL,
    corroborating_entity_id TEXT NOT NULL,
    competition_provider_id TEXT NOT NULL,
    corroborating_competition_code TEXT NOT NULL,
    country_code TEXT NOT NULL,
    country_name TEXT NOT NULL,
    team_type TEXT NOT NULL,
    gender_scope TEXT NOT NULL,
    match_method TEXT NOT NULL,
    approval_reason TEXT NOT NULL,
    evidence_snapshot JSONB NOT NULL,
    approved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (
        provider, provider_entity_id, corroborating_provider,
        corroborating_entity_id, competition_provider_id
    )
);
CREATE INDEX IF NOT EXISTS provider_team_scope_corroborations_target_idx
    ON provider_team_scope_corroborations (provider, provider_entity_id);
"""


def build_approved_records(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = []
    for competition in report.get("competitions") or []:
        for candidate in competition.get("candidates") or []:
            if candidate.get("status") != "scope_corroboration_candidate":
                continue
            country_code = str(candidate.get("country_code_iso3166_alpha2") or "").strip().upper()
            country_name = str(candidate.get("country_name_from_iso_code") or "").strip()
            team_type = str(candidate.get("team_type_from_api_ninjas") or "").strip().casefold()
            gender_raw = str(candidate.get("gender_from_api_ninjas") or "").strip().casefold()
            gender_scope = candidate.get("gender_scope_normalized_candidate")
            if (
                not country_code or not country_name or team_type != "club"
                or gender_raw != "men" or gender_scope != "male"
            ):
                continue
            provider = str(candidate.get("target_provider") or "").strip().casefold()
            provider_id = str(candidate.get("target_provider_team_id") or "").strip()
            api_id = str(candidate.get("api_ninjas_team_id") or "").strip()
            competition_id = str(candidate.get("competition_scope") or "").strip()
            competition_code = str(candidate.get("api_ninjas_domestic_competition") or "").strip()
            if not all((provider, provider_id, api_id, competition_id, competition_code)):
                continue
            snapshot = {
                "target_provider": provider,
                "target_provider_team_id": provider_id,
                "target_provider_team_name": candidate.get("target_provider_team_name"),
                "api_ninjas_team_id": api_id,
                "api_ninjas_team_name": candidate.get("api_ninjas_team_name"),
                "api_ninjas_competition_code": competition_code,
                "identity_basis": candidate.get("identity_basis"),
                "country_code_iso3166_alpha2": country_code,
                "country_name_from_iso_code": country_name,
                "team_type_from_api_ninjas": team_type,
                "gender_from_api_ninjas": gender_raw,
                "gender_scope_normalized_candidate": gender_scope,
            }
            records.append({
                "provider": provider,
                "provider_entity_id": provider_id,
                "corroborating_provider": "api_ninjas",
                "corroborating_entity_id": api_id,
                "competition_provider_id": competition_id,
                "corroborating_competition_code": competition_code,
                "country_code": country_code,
                "country_name": country_name,
                "team_type": team_type,
                "gender_scope": gender_scope,
                "match_method": "unique_exact_normalized_team_name_within_same_current_domestic_competition",
                "approval_reason": APPROVAL_REASON,
                "evidence_snapshot": snapshot,
            })
    return records


def approve_team_scope_corroborations(database_url: str) -> dict[str, Any]:
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    audit = audit_team_scope_corroboration(database_url)
    records = build_approved_records(audit)
    inserted = 0
    already_present = 0
    held_conflicts = []
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(TABLE_SQL)
            for row in records:
                cursor.execute(
                    """SELECT country_code, country_name, team_type, gender_scope,
                              corroborating_entity_id
                       FROM provider_team_scope_corroborations
                       WHERE provider = %s AND provider_entity_id = %s
                       ORDER BY approved_at DESC""",
                    (row["provider"], row["provider_entity_id"]),
                )
                existing = cursor.fetchall()
                conflicting = [
                    value for value in existing
                    if (
                        str(value[0]) != row["country_code"]
                        or str(value[1]) != row["country_name"]
                        or str(value[2]) != row["team_type"]
                        or str(value[3]) != row["gender_scope"]
                    )
                ]
                if conflicting:
                    held_conflicts.append({
                        "provider": row["provider"],
                        "provider_entity_id": row["provider_entity_id"],
                        "reason": "existing_scope_corroboration_conflict",
                    })
                    continue
                if any(str(value[4]) == row["corroborating_entity_id"] for value in existing):
                    already_present += 1
                    continue
                corroboration_id = str(uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    ":".join((
                        row["provider"], row["provider_entity_id"],
                        row["corroborating_provider"], row["corroborating_entity_id"],
                        row["competition_provider_id"],
                    )),
                ))
                cursor.execute(
                    """INSERT INTO provider_team_scope_corroborations (
                           corroboration_id, provider, provider_entity_id,
                           corroborating_provider, corroborating_entity_id,
                           competition_provider_id, corroborating_competition_code,
                           country_code, country_name, team_type, gender_scope,
                           match_method, approval_reason, evidence_snapshot
                       ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (
                           provider, provider_entity_id, corroborating_provider,
                           corroborating_entity_id, competition_provider_id
                       ) DO NOTHING""",
                    (
                        corroboration_id, row["provider"], row["provider_entity_id"],
                        row["corroborating_provider"], row["corroborating_entity_id"],
                        row["competition_provider_id"], row["corroborating_competition_code"],
                        row["country_code"], row["country_name"], row["team_type"],
                        row["gender_scope"], row["match_method"], row["approval_reason"],
                        Jsonb(row["evidence_snapshot"]),
                    ),
                )
                inserted += cursor.rowcount
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "operation": "provider_team_scope_corroboration_approval",
        "write_scope": "provider_team_scope_corroborations_table_only",
        "candidate_records": len(records),
        "new_corroborations_written": inserted,
        "already_present": already_present,
        "held_conflicts": held_conflicts,
        "highlightly_corroborations": sum(row["provider"] == "highlightly" for row in records) - len([
            row for row in held_conflicts if row["provider"] == "highlightly"
        ]),
        "livescore_corroborations": sum(row["provider"] == "livescore_football" for row in records) - len([
            row for row in held_conflicts if row["provider"] == "livescore_football"
        ]),
        "provider_source_rows_updated": 0,
        "canonical_entities_written": 0,
        "provider_links_written": 0,
        "fixtures_written": 0,
        "predictions_written": 0,
        "prediction_ledger_touched": False,
        "approval_reason": APPROVAL_REASON,
        "age_group_scope_resolved": False,
        "squad_scope_resolved": False,
        "interpretation": (
            "Approved records are cross-provider scope corroboration evidence only. "
            "The source provider rows are unchanged and team canonical identity remains "
            "held until age-group and squad scope are independently evidenced."
        ),
    }


def main() -> int:
    report = approve_team_scope_corroborations(
        os.getenv("PROVIDER_DATABASE_URL", "").strip()
    )
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
                      encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
