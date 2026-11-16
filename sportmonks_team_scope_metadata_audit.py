"""Read-only Sportmonks team country/type metadata audit.

Reads staged provider-native team payloads, then resolves each distinct
Sportmonks country_id through the documented Core Country-by-ID endpoint.
No country name is guessed and no database/canonical records are modified.
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

REPORT = Path("sportmonks-team-scope-metadata-audit.json")
COLUMNS = ("provider_entity_id", "name", "raw_payload")


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return {}
    return value if isinstance(value, Mapping) else {}


def build_team_scope_inventory(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    country_ids: Counter[str] = Counter()
    team_types: Counter[str] = Counter()
    genders: Counter[str] = Counter()
    teams_without_country_id = 0
    teams_without_type = 0
    for row in rows:
        record = extract_team_scope_evidence({
            "provider": "sportmonks",
            "provider_entity_id": row.get("provider_entity_id"),
            "name": row.get("name"),
            "raw_payload": row.get("raw_payload"),
        })
        fields = record["raw_provider_scope_candidates"]
        team_country_ids = {
            str(item["value"]).strip()
            for item in fields
            if item["field"] == "country_id"
            and item["value"] is not None
            and str(item["value"]).strip().isdigit()
            and int(str(item["value"]).strip()) > 0
        }
        team_types_found = {
            str(item["value"]).strip().casefold()
            for item in fields
            if item["field"] == "team_type"
            and item["value"] is not None
            and str(item["value"]).strip()
        }
        genders_found = {
            str(item["value"]).strip().casefold()
            for item in fields
            if item["field"] == "gender_scope"
            and item["value"] is not None
            and str(item["value"]).strip()
        }
        if team_country_ids:
            for value in team_country_ids:
                country_ids[value] += 1
        else:
            teams_without_country_id += 1
        if team_types_found:
            team_types.update(team_types_found)
        else:
            teams_without_type += 1
        genders.update(genders_found)
    return {
        "team_rows_examined": len(rows),
        "country_id_team_counts": dict(sorted(country_ids.items(), key=lambda item: int(item[0]))),
        "distinct_country_id_count": len(country_ids),
        "teams_without_country_id": teams_without_country_id,
        "team_type_value_counts": dict(sorted(team_types.items())),
        "teams_without_team_type": teams_without_type,
        "gender_value_counts": dict(sorted(genders.items())),
    }


def resolve_country_ids(country_ids: list[str], client: Any) -> dict[str, Any]:
    api_root = client.base_url.rsplit("/football", 1)[0]
    resolved: dict[str, Any] = {}
    for country_id in country_ids:
        path = f"/core/countries/{country_id}"
        try:
            response = client.session.get(
                f"{api_root}{path}",
                timeout=client.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data") if isinstance(payload, dict) else None
            if isinstance(data, list):
                matches = [row for row in data if isinstance(row, dict) and str(row.get("id")) == country_id]
                data = matches[0] if len(matches) == 1 else None
            if not isinstance(data, dict) or str(data.get("id")) != country_id or not str(data.get("name") or "").strip():
                resolved[country_id] = {
                    "status": "unresolved_response",
                    "http_status": response.status_code,
                }
                continue
            resolved[country_id] = {
                "status": "resolved_exact_id",
                "http_status": response.status_code,
                "country_id": data.get("id"),
                "name": data.get("name"),
                "official_name": data.get("official_name"),
                "iso2": data.get("iso2"),
                "iso3": data.get("iso3"),
                "fifa_name": data.get("fifa_name"),
            }
        except Exception as exc:
            resolved[country_id] = {
                "status": "request_error",
                "error_type": type(exc).__name__,
                "http_status": getattr(getattr(exc, "response", None), "status_code", None),
            }
    return resolved


def audit_sportmonks_team_scope(database_url: str, client_factory=SportmonksClient) -> dict[str, Any]:
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(
                """SELECT provider_entity_id, name, raw_payload
                   FROM provider_source_entities
                   WHERE provider = 'sportmonks' AND entity_type = 'team'
                   ORDER BY provider_entity_id"""
            )
            rows = [dict(zip(COLUMNS, values)) for values in cursor.fetchall()]
    inventory = build_team_scope_inventory(rows)
    with client_factory() as client:
        countries = resolve_country_ids(list(inventory["country_id_team_counts"]), client)
    return {
        "operation": "sportmonks_team_scope_metadata_audit",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "database_touched_read_only": True,
        "database_writes": False,
        "canonical_ids_assigned": 0,
        "provider_links_created": 0,
        "fixtures_ingested": 0,
        "prediction_model_modified": False,
        "prediction_ledger_touched": False,
        "team_scope_inventory": inventory,
        "country_id_resolution": countries,
        "country_ids_resolved": sum(value.get("status") == "resolved_exact_id" for value in countries.values()),
        "country_ids_unresolved": sum(value.get("status") != "resolved_exact_id" for value in countries.values()),
        "interpretation": (
            "Country names are accepted only when the Sportmonks Core API response ID exactly "
            "matches the country_id stored in the provider-native team payload. Team type and "
            "gender remain source observations; no club/national or gender scope is inferred."
        ),
    }


def main() -> int:
    report = audit_sportmonks_team_scope(os.getenv("PROVIDER_DATABASE_URL", "").strip())
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps({
        "checked_at_utc": report["checked_at_utc"],
        "read_only": report["read_only"],
        "team_scope_inventory": report["team_scope_inventory"],
        "country_id_resolution": report["country_id_resolution"],
        "country_ids_resolved": report["country_ids_resolved"],
        "country_ids_unresolved": report["country_ids_unresolved"],
        "database_writes": report["database_writes"],
        "canonical_ids_assigned": report["canonical_ids_assigned"],
        "provider_links_created": report["provider_links_created"],
        "report": str(REPORT),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
