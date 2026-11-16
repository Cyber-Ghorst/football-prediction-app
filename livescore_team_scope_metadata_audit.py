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
API_COLUMNS = ("entity_type", "provider_entity_id", "name", "country", "team_type", "raw_payload")


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


def _norm(value: Any) -> str:
    import re
    import unicodedata
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("&", " and ")
    return re.sub(r"\\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def build_api_football_country_candidates(
    livescore_rows: list[Mapping[str, Any]],
    api_football_rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Emit exact-name, same-country/competition/season scope candidates only."""
    competitions = {
        str(row.get("provider_entity_id")): row
        for row in api_football_rows
        if row.get("entity_type") == "competition"
    }
    seasons = {
        str(row.get("provider_entity_id")): row
        for row in api_football_rows
        if row.get("entity_type") == "season"
    }
    teams = [row for row in api_football_rows if row.get("entity_type") == "team"]
    results = []
    for target in TARGETS:
        slug = target["slug"]
        ls_rows = [
            row for row in livescore_rows
            if slug in _competition_slugs(row.get("raw_payload"))
        ]
        expected_competition = "bundesliga" if target["country"] == "Germany" else "ligue 1"
        competition_ids = []
        for comp_id, comp in competitions.items():
            if _norm(comp.get("country")) != _norm(target["country"]):
                continue
            if _norm(comp.get("name")) != expected_competition:
                continue
            season_id = f"{comp_id}:2026"
            season = seasons.get(season_id)
            if not season or str(season.get("parent_competition_provider_id") or "") != comp_id:
                continue
            raw = _mapping(comp.get("raw_payload"))
            if not raw:
                pass
            competition_ids.append(comp_id)
        af_rows = []
        for team in teams:
            raw = _mapping(team.get("raw_payload"))
            comp_ids = raw.get("competition_provider_ids")
            if not isinstance(comp_ids, list):
                continue
            if not any(str(value) in competition_ids for value in comp_ids):
                continue
            if str(raw.get("catalogue_reference_season") or "") != "2026":
                continue
            af_rows.append(team)
        ls_by_name: dict[str, list[Mapping[str, Any]]] = {}
        af_by_name: dict[str, list[Mapping[str, Any]]] = {}
        for row in ls_rows:
            ls_by_name.setdefault(_norm(row.get("name")), []).append(row)
        for row in af_rows:
            af_by_name.setdefault(_norm(row.get("name")), []).append(row)
        candidates = []
        ambiguous = []
        ambiguous_livescore_count = 0
        for name_key in sorted(set(ls_by_name) & set(af_by_name)):
            left, right = ls_by_name[name_key], af_by_name[name_key]
            if len(left) != 1 or len(right) != 1:
                ambiguous_livescore_count += len(left)
                ambiguous.append({
                    "normalized_name": name_key,
                    "livescore_count": len(left),
                    "api_football_count": len(right),
                    "status": "ambiguous_duplicate_name",
                })
                continue
            live, api = left[0], right[0]
            candidates.append({
                "livescore_team_id": str(live.get("provider_entity_id")),
                "livescore_team_name": live.get("name"),
                "api_football_team_id": str(api.get("provider_entity_id")),
                "api_football_team_name": api.get("name"),
                "country_from_api_football_team_record": api.get("country"),
                "team_type_from_api_football_team_record": api.get("team_type"),
                "identity_basis": "unique_exact_normalized_team_name_within_same_country_competition_and_2026_season",
                "status": "scope_corroboration_candidate_not_approved",
            })
        results.append({
            "competition": target,
            "api_football_competition_ids": competition_ids,
            "livescore_team_count": len(ls_rows),
            "api_football_team_count": len(af_rows),
            "exact_unique_name_candidates": len(candidates),
            "ambiguous_name_groups": ambiguous,
            "ambiguous_livescore_team_count": ambiguous_livescore_count,
            "candidates": candidates,
            "unmatched_livescore_team_count": len(ls_rows) - len(candidates) - ambiguous_livescore_count,
            "interpretation": (
                "API-Football team country/type values are explicit provider observations. "
                "Exact-name cross-provider matches are candidates only; no IDs or scope values "
                "are transferred into LiveScoreFootball records without approval."
            ),
        })
    return {"read_only": True, "provider_links_created": 0, "competitions": results}


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
            cursor.execute(
                """SELECT entity_type, provider_entity_id, name, country, team_type, raw_payload
                   FROM provider_source_entities
                   WHERE provider = 'api_football'
                     AND entity_type IN ('team', 'competition', 'season')
                   ORDER BY entity_type, provider_entity_id"""
            )
            api_football_rows = [dict(zip(API_COLUMNS, values)) for values in cursor.fetchall()]
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
    report["api_football_scope_candidates"] = build_api_football_country_candidates(
        staged_rows, api_football_rows
    )
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
