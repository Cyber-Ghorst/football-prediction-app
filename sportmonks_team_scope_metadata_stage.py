"""Stage verified Sportmonks-native team scope into provider source rows only.

Country labels are resolved from Sportmonks Core API using exact country IDs
present in each raw team payload. Team type and gender are copied only from
documented raw team fields. Conflicting structured values are held, never
overwritten. No canonical entities or provider links are created.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from provider_data_storage import _connect
from provider_team_scope_evidence_audit import extract_team_scope_evidence
from sportmonks import SportmonksClient
from sportmonks_team_scope_metadata_audit import resolve_country_ids

REPORT = Path("sportmonks-team-scope-metadata-stage-report.json")
COLUMNS = ("provider_entity_id", "name", "country", "team_type", "gender_scope", "raw_payload")
ALLOWED_TEAM_TYPES = {"domestic", "national"}
ALLOWED_GENDERS = {"male", "female"}


def build_scope_updates(rows: list[Mapping[str, Any]], country_names: Mapping[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    updates = []
    held = []
    for row in rows:
        record = extract_team_scope_evidence({
            "provider": "sportmonks",
            "provider_entity_id": row.get("provider_entity_id"),
            "name": row.get("name"),
            "raw_payload": row.get("raw_payload"),
        })
        candidates = record["raw_provider_scope_candidates"]
        values: dict[str, list[Any]] = {}
        for item in candidates:
            values.setdefault(item["field"], []).append(item.get("value"))
        country_ids = {
            str(value).strip() for value in values.get("country_id", [])
            if value is not None and str(value).strip().isdigit()
            and int(str(value).strip()) > 0
        }
        team_types = {
            str(value).strip().casefold() for value in values.get("team_type", [])
            if value is not None and str(value).strip()
        }
        genders = {
            str(value).strip().casefold() for value in values.get("gender_scope", [])
            if value is not None and str(value).strip()
        }
        if len(country_ids) != 1 or len(team_types) != 1 or len(genders) != 1:
            held.append({
                "provider_entity_id": str(row.get("provider_entity_id")),
                "reason": "missing_or_ambiguous_provider_native_scope_fields",
                "country_ids": sorted(country_ids),
                "team_type_values": sorted(team_types),
                "gender_values": sorted(genders),
            })
            continue
        country_id = next(iter(country_ids))
        country = country_names.get(country_id)
        team_type = next(iter(team_types))
        gender = next(iter(genders))
        if not country:
            held.append({
                "provider_entity_id": str(row.get("provider_entity_id")),
                "reason": "country_id_not_exactly_resolved",
                "country_id": country_id,
            })
            continue
        if team_type not in ALLOWED_TEAM_TYPES or gender not in ALLOWED_GENDERS:
            held.append({
                "provider_entity_id": str(row.get("provider_entity_id")),
                "reason": "unrecognized_scope_value",
                "country_id": country_id,
                "team_type": team_type,
                "gender_scope": gender,
            })
            continue
        existing = {
            "country": str(row.get("country") or "").strip(),
            "team_type": str(row.get("team_type") or "").strip().casefold(),
            "gender_scope": str(row.get("gender_scope") or "").strip().casefold(),
        }
        desired = {
            "country": country,
            "team_type": team_type,
            "gender_scope": gender,
        }
        conflicts = {
            key: {"existing": existing[key], "provider_evidence": desired[key]}
            for key in desired
            if existing[key] and existing[key] != desired[key]
        }
        if conflicts:
            held.append({
                "provider_entity_id": str(row.get("provider_entity_id")),
                "reason": "existing_structured_scope_conflicts_with_provider_evidence",
                "conflicts": conflicts,
            })
            continue
        updates.append({
            "provider_entity_id": str(row.get("provider_entity_id")),
            "country_id": country_id,
            "country": country,
            "team_type": team_type,
            "gender_scope": gender,
            "already_matching": all(existing[key] == desired[key] for key in desired),
        })
    return updates, held


def stage_sportmonks_team_scope(database_url: str, client_factory=SportmonksClient) -> dict[str, Any]:
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(
                """SELECT provider_entity_id, name, country, team_type, gender_scope, raw_payload
                   FROM provider_source_entities
                   WHERE provider = 'sportmonks' AND entity_type = 'team'
                   ORDER BY provider_entity_id"""
            )
            rows = [dict(zip(COLUMNS, values)) for values in cursor.fetchall()]
    with client_factory() as client:
        country_ids = sorted({
            str(item["value"]).strip()
            for row in rows
            for item in extract_team_scope_evidence({
                "provider": "sportmonks",
                "provider_entity_id": row.get("provider_entity_id"),
                "name": row.get("name"),
                "raw_payload": row.get("raw_payload"),
            })["raw_provider_scope_candidates"]
            if item["field"] == "country_id" and item.get("value") is not None
            and str(item["value"]).strip().isdigit()
        }, key=int)
        country_results = resolve_country_ids(country_ids, client)
    country_names = {
        country_id: str(result["name"])
        for country_id, result in country_results.items()
        if result.get("status") == "resolved_exact_id"
    }
    updates, held = build_scope_updates(rows, country_names)
    eligible = [row for row in updates if not row["already_matching"]]
    updated = 0
    failed_updates = []
    if eligible:
        with _connect(database_url) as connection:
            with connection.cursor() as cursor:
                for row in eligible:
                    cursor.execute(
                        """UPDATE provider_source_entities
                           SET country = COALESCE(NULLIF(country, ''), %s),
                               team_type = COALESCE(NULLIF(team_type, ''), %s),
                               gender_scope = COALESCE(NULLIF(gender_scope, ''), %s)
                           WHERE provider = 'sportmonks'
                             AND entity_type = 'team'
                             AND provider_entity_id = %s
                             AND (country IS NULL OR country = '' OR country = %s)
                             AND (team_type IS NULL OR team_type = '' OR team_type = %s)
                             AND (gender_scope IS NULL OR gender_scope = '' OR gender_scope = %s)""",
                        (
                            row["country"], row["team_type"], row["gender_scope"],
                            row["provider_entity_id"], row["country"],
                            row["team_type"], row["gender_scope"],
                        ),
                    )
                    if cursor.rowcount == 1:
                        updated += 1
                    else:
                        failed_updates.append({
                            "provider_entity_id": row["provider_entity_id"],
                            "reason": "row_changed_or_scope_conflict_at_update_time",
                        })
    return {
        "operation": "sportmonks_team_scope_metadata_stage",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "write_scope": "provider_source_evidence_only",
        "country_id_resolution": country_results,
        "country_ids_resolved": len(country_names),
        "team_rows_examined": len(rows),
        "team_rows_eligible": len(updates),
        "team_rows_already_matching": sum(row["already_matching"] for row in updates),
        "team_rows_updated": updated,
        "team_rows_held": len(held) + len(failed_updates),
        "held_samples": held[:30],
        "update_conflict_samples": failed_updates[:30],
        "country_value_counts": dict(sorted(Counter(row["country"] for row in updates).items())),
        "team_type_value_counts": dict(sorted(Counter(row["team_type"] for row in updates).items())),
        "gender_value_counts": dict(sorted(Counter(row["gender_scope"] for row in updates).items())),
        "canonical_entities_written": 0,
        "provider_links_written": 0,
        "fixtures_written": 0,
        "predictions_written": 0,
        "prediction_ledger_touched": False,
        "interpretation": (
            "Only provider-source team rows are updated. Country names come from exact-ID "
            "Sportmonks Core API responses; team type and gender are copied from raw team fields. "
            "Domestic is retained as domestic, not relabelled as club. No age-group or squad scope "
            "is inferred, and conflicting pre-existing values are held."
        ),
    }


def main() -> int:
    report = stage_sportmonks_team_scope(os.getenv("PROVIDER_DATABASE_URL", "").strip())
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
                      encoding="utf-8")
    print(json.dumps({
        "checked_at_utc": report["checked_at_utc"],
        "write_scope": report["write_scope"],
        "country_ids_resolved": report["country_ids_resolved"],
        "team_rows_examined": report["team_rows_examined"],
        "team_rows_eligible": report["team_rows_eligible"],
        "team_rows_already_matching": report["team_rows_already_matching"],
        "team_rows_updated": report["team_rows_updated"],
        "team_rows_held": report["team_rows_held"],
        "country_value_counts": report["country_value_counts"],
        "team_type_value_counts": report["team_type_value_counts"],
        "gender_value_counts": report["gender_value_counts"],
        "canonical_entities_written": report["canonical_entities_written"],
        "provider_links_written": report["provider_links_written"],
        "prediction_ledger_touched": report["prediction_ledger_touched"],
        "report": str(REPORT),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
