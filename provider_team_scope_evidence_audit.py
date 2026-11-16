"""Read-only inventory of explicit team-scope evidence in staged provider payloads.

This audit surfaces provider-supplied values for review. It does not infer,
normalize, approve or write team identities or cross-provider links.
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from provider_data_storage import _connect

REPORT = Path("provider-team-scope-evidence-audit.json")
COLUMNS = (
    "provider", "provider_entity_id", "name", "country", "team_type",
    "gender_scope", "age_group", "squad_scope", "raw_payload",
)
FIELD_KEYS = {
    "country": {"country", "country_name", "countryname", "team_country_from_provider"},
    # Preserve provider-native IDs separately; they are not country-name labels.
    "country_id": {"country_id", "countryid"},
    "nationality": {"nationality"},
    "team_type": {"team_type", "teamtype", "national", "is_national", "national_team", "is_national_team"},
    "gender_scope": {"gender", "gender_scope", "genderscope", "gender_name", "gendername"},
    "age_group": {"age_group", "agegroup", "age_group_name", "agegroupname", "age"},
    "squad_scope": {"squad_scope", "squadscope", "squad", "team_scope", "teamscope"},
}
STRUCTURED_FIELDS = ("country", "team_type", "gender_scope", "age_group", "squad_scope")


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, Mapping) else {}
    return {}


def _scalar(value: Any) -> Any:
    if isinstance(value, Mapping):
        # Preserve provider-native objects as compact JSON, not a guessed label.
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)[:300]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)[:300]


def _walk_evidence(value: Any, path: str = "raw_payload", depth: int = 0):
    if depth > 8:
        return
    obj = _mapping(value)
    for key, child in obj.items():
        normalized = str(key).casefold().replace("-", "_")
        for field, aliases in FIELD_KEYS.items():
            if normalized in aliases:
                yield field, f"{path}.{key}", _scalar(child)
                break
        if isinstance(child, Mapping):
            yield from _walk_evidence(child, f"{path}.{key}", depth + 1)
        elif isinstance(child, list):
            for index, item in enumerate(child[:20]):
                if isinstance(item, Mapping):
                    yield from _walk_evidence(item, f"{path}.{key}[{index}]", depth + 1)


def extract_team_scope_evidence(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return stored fields and raw provider candidates without promoting them."""
    raw = _mapping(row.get("raw_payload"))
    evidence = [
        {"field": field, "path": path, "value": value}
        for field, path, value in _walk_evidence(raw)
    ]
    structured = {
        field: _scalar(row.get(field))
        for field in STRUCTURED_FIELDS
        if row.get(field) is not None and str(row.get(field)).strip() != ""
    }
    return {
        "provider": str(row.get("provider") or "unknown").casefold(),
        "provider_entity_id": str(row.get("provider_entity_id") or ""),
        "name": row.get("name"),
        "structured_scope_fields": structured,
        "raw_provider_scope_candidates": evidence,
        "interpretation": "raw candidates are observations only; no team scope was inferred or approved",
    }


def build_team_scope_evidence_audit(rows: list[Mapping[str, Any]], sample_limit: int = 12) -> dict[str, Any]:
    by_provider: dict[str, list[dict[str, Any]]] = defaultdict(list)
    field_counts: dict[str, Counter] = defaultdict(Counter)
    structured_counts: dict[str, Counter] = defaultdict(Counter)
    structured_values: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    raw_values: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    for row in rows:
        record = extract_team_scope_evidence(row)
        provider = record["provider"]
        by_provider[provider].append(record)
        for field in STRUCTURED_FIELDS:
            value = row.get(field)
            if value is None or str(value).strip() == "":
                structured_values[provider][field]["<missing>"] += 1
            else:
                structured_counts[provider][field] += 1
                structured_values[provider][field][str(_scalar(value))] += 1
        for item in record["raw_provider_scope_candidates"]:
            field_counts[provider][item["field"]] += 1
            value = item["value"]
            if value is None or str(value).strip() == "":
                raw_values[provider][item["field"]]["<empty_or_null>"] += 1
            else:
                raw_values[provider][item["field"]][str(value)] += 1
    providers = {}
    for provider, records in sorted(by_provider.items()):
        providers[provider] = {
            "team_rows": len(records),
            "structured_scope_field_counts": dict(sorted(structured_counts[provider].items())),
            "structured_scope_value_counts": {
                field: dict(sorted(values.items()))
                for field, values in sorted(structured_values[provider].items())
            },
            "raw_provider_candidate_field_counts": dict(sorted(field_counts[provider].items())),
            "raw_provider_candidate_value_counts": {
                field: dict(sorted(values.items()))
                for field, values in sorted(raw_values[provider].items())
            },
            "sample_records": records[:sample_limit],
        }
    return {
        "read_only": True,
        "database_writes": False,
        "canonical_ids_assigned": 0,
        "provider_links_created": 0,
        "team_rows_examined": len(rows),
        "providers": providers,
        "interpretation": (
            "This report inventories explicit source payload fields only. "
            "A candidate value is not verified identity evidence until its provider meaning, "
            "team scope and season/competition context are independently validated."
        ),
    }


def audit_team_scope_evidence(database_url: str) -> dict[str, Any]:
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(
                """SELECT provider, provider_entity_id, name, country, team_type,
                          gender_scope, age_group, squad_scope, raw_payload
                   FROM provider_source_entities
                   WHERE entity_type = 'team'
                   ORDER BY provider, provider_entity_id"""
            )
            rows = [dict(zip(COLUMNS, values)) for values in cursor.fetchall()]
    report = build_team_scope_evidence_audit(rows)
    report["database_read_only"] = True
    report["checked_at"] = datetime.now(timezone.utc).isoformat()
    return report


def main() -> int:
    database_url = os.getenv("PROVIDER_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("PROVIDER_DATABASE_URL is not configured.")
    report = audit_team_scope_evidence(database_url)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
                      encoding="utf-8")
    print(json.dumps({
        "checked_at": report["checked_at"],
        "read_only": report["read_only"],
        "team_rows_examined": report["team_rows_examined"],
        "providers": {
            provider: {
                "team_rows": details["team_rows"],
                "structured_scope_field_counts": details["structured_scope_field_counts"],
                "raw_provider_candidate_field_counts": details["raw_provider_candidate_field_counts"],
            }
            for provider, details in report["providers"].items()
        },
        "canonical_ids_assigned": report["canonical_ids_assigned"],
        "provider_links_created": report["provider_links_created"],
        "report": str(REPORT),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
