"""Read-only LiveScoreFootball club-catalogue scope audit.

Uses the provider's documented /clubs catalogue, joins only by exact
provider team ID to previously observed season-window participants, and
reports provider-supplied country values and endpoint-level club semantics.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from livescore_football import LiveScoreFootballClient
from provider_data_storage import _connect

TARGETS = (
    {"slug": "ger.1", "name": "German Bundesliga", "country": "Germany"},
    {"slug": "fra.1", "name": "French Ligue 1", "country": "France"},
)
REPORT = Path("livescore-team-scope-metadata-audit.json")
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


def _competition_slugs(raw_payload: Any) -> set[str]:
    raw = _mapping(raw_payload)
    values = raw.get("competition_provider_ids")
    if not isinstance(values, list):
        return set()
    return {str(value).strip() for value in values if str(value or "").strip()}


def build_scope_report(
    staged_rows: list[Mapping[str, Any]],
    catalogues: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    competitions = []
    for target in TARGETS:
        slug = target["slug"]
        catalogue = catalogues.get(slug) or {}
        clubs = catalogue.get("clubs") if isinstance(catalogue.get("clubs"), list) else []
        by_id = {
            str(row.get("id")): row
            for row in clubs
            if isinstance(row, Mapping) and row.get("id") is not None
        }
        observed = [
            row for row in staged_rows
            if slug in _competition_slugs(row.get("raw_payload"))
        ]
        country_counts: Counter[str] = Counter()
        source_counts: Counter[str] = Counter()
        matched = []
        unmatched = []
        for row in observed:
            team_id = str(row.get("provider_entity_id") or "")
            record = by_id.get(team_id)
            if record is None:
                unmatched.append({
                    "provider_entity_id": team_id,
                    "name": row.get("name"),
                    "status": "no_exact_id_match_in_club_catalogue",
                })
                continue
            country = str(record.get("country") or "").strip()
            source = str(record.get("catalogSource") or "").strip() or "unspecified"
            source_counts[source] += 1
            if country:
                country_counts[country] += 1
            matched.append({
                "provider_entity_id": team_id,
                "observed_name": row.get("name"),
                "catalogue_name": record.get("displayName") or record.get("name"),
                "country": country or None,
                "city": record.get("city") or None,
                "catalog_source": source,
                "team_type_evidence": "club_endpoint_contract",
            })
        competitions.append({
            "competition": target,
            "catalogue_status": "returned" if catalogue.get("status") == "ok" else catalogue.get("status", "not_requested"),
            "catalogue_count": len(clubs),
            "dedicated_catalog_count": (catalogue.get("meta") or {}).get("dedicatedCatalogCount"),
            "match_snapshot_fallback": (catalogue.get("meta") or {}).get("matchSnapshotFallback"),
            "season_window_observed_team_count": len(observed),
            "exact_provider_id_matches": len(matched),
            "unmatched_observed_team_count": len(unmatched),
            "country_value_counts": dict(sorted(country_counts.items())),
            "catalog_source_counts": dict(sorted(source_counts.items())),
            "team_type_evidence": {
                "value": "club",
                "basis": "records returned by the provider's league /clubs endpoint",
                "scope": "endpoint-level club classification; not a senior/first-team or gender claim",
            },
            "matched_teams": matched,
            "unmatched_teams": unmatched,
        })
    return {
        "read_only": True,
        "database_writes": False,
        "canonical_ids_assigned": 0,
        "provider_links_created": 0,
        "fixtures_ingested": 0,
        "prediction_model_modified": False,
        "prediction_ledger_touched": False,
        "competitions": competitions,
    }


def audit_livescore_team_scope(database_url: str, client_factory=LiveScoreFootballClient) -> dict[str, Any]:
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(
                """SELECT provider_entity_id, name, raw_payload
                   FROM provider_source_entities
                   WHERE provider = 'livescore_football' AND entity_type = 'team'
                   ORDER BY provider_entity_id"""
            )
            staged_rows = [dict(zip(COLUMNS, values)) for values in cursor.fetchall()]
    catalogues = {}
    with client_factory() as client:
        for target in TARGETS:
            try:
                payload = client.clubs(target["slug"])
                catalogues[target["slug"]] = {
                    "status": "ok",
                    "clubs": payload.get("clubs", []),
                    "meta": payload.get("meta") or {},
                }
            except Exception as exc:
                catalogues[target["slug"]] = {
                    "status": "error",
                    "error_type": type(exc).__name__,
                }
    report = build_scope_report(staged_rows, catalogues)
    report.update({
        "operation": "livescore_team_scope_metadata_audit",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "database_touched_read_only": True,
        "catalogue_requests": len(TARGETS),
        "country_inferred_from_competition": False,
        "interpretation": (
            "Country is reported only when present on an exact-ID-matched provider club record. "
            "The /clubs route supports club classification only; it does not establish gender, "
            "age group, senior/reserve or first-team scope. Match-snapshot fallback is kept "
            "distinct from dedicated club-catalogue evidence."
        ),
    })
    return report


def main() -> int:
    report = audit_livescore_team_scope(os.getenv("PROVIDER_DATABASE_URL", "").strip())
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
                      encoding="utf-8")
    print(json.dumps({
        "checked_at_utc": report["checked_at_utc"],
        "read_only": report["read_only"],
        "competitions": [
            {
                "slug": item["competition"]["slug"],
                "catalogue_status": item["catalogue_status"],
                "catalogue_count": item["catalogue_count"],
                "exact_provider_id_matches": item["exact_provider_id_matches"],
                "country_value_counts": item["country_value_counts"],
                "catalog_source_counts": item["catalog_source_counts"],
            }
            for item in report["competitions"]
        ],
        "database_writes": report["database_writes"],
        "report": str(REPORT),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
