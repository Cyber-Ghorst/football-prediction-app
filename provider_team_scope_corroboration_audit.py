"""Read-only cross-provider team-scope corroboration candidates.

Matches current API Ninjas club records to 2026-season Highlightly and
LiveScoreFootball participants by unique normalized team name within an
explicitly mapped domestic competition. It never writes scope values or links.
"""
from __future__ import annotations

import json
from difflib import SequenceMatcher
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from provider_data_storage import _connect
from provider_entity_crosswalk import normalize_entity_name

REPORT = Path("provider-team-scope-corroboration-audit.json")
COMPETITION_MAP = {
    ("livescore_football", "ger.1"): "bundesliga",
    ("livescore_football", "fra.1"): "ligue1",
    ("highlightly", "67162"): "bundesliga",
    ("highlightly", "52695"): "ligue1",
}
COUNTRY_NAMES = {"DE": "Germany", "FR": "France"}


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


def _competition_ids(raw_payload: Any, provider: str) -> set[str]:
    raw = _mapping(raw_payload)
    key = "domestic_league_codes" if provider == "api_ninjas" else "competition_provider_ids"
    values = raw.get(key)
    if not isinstance(values, list):
        return set()
    return {str(value).strip() for value in values if str(value or "").strip()}


def build_corroboration_report(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    api_rows = [row for row in rows if str(row.get("provider") or "").casefold() == "api_ninjas"]
    target_rows = [
        row for row in rows
        if str(row.get("provider") or "").casefold() in {"highlightly", "livescore_football"}
    ]
    api_by_comp: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in api_rows:
        for competition in _competition_ids(row.get("raw_payload"), "api_ninjas"):
            api_by_comp[competition].append(row)

    reports = []
    all_candidates = []
    for provider in ("highlightly", "livescore_football"):
        for provider_competition, api_competition in sorted(
            (key[1], value) for key, value in COMPETITION_MAP.items() if key[0] == provider
        ):
            source = [
                row for row in target_rows
                if str(row.get("provider") or "").casefold() == provider
                and provider_competition in _competition_ids(row.get("raw_payload"), provider)
            ]
            api_comp = api_by_comp.get(api_competition, [])
            source_by_name: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
            api_by_name: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
            for row in source:
                source_by_name[normalize_entity_name(row.get("name"))].append(row)
            for row in api_comp:
                api_by_name[normalize_entity_name(row.get("name"))].append(row)
            candidates = []
            ambiguous = []
            for name_key in sorted(set(source_by_name) & set(api_by_name)):
                left, right = source_by_name[name_key], api_by_name[name_key]
                if len(left) != 1 or len(right) != 1:
                    ambiguous.append({
                        "normalized_name": name_key,
                        "target_provider_rows": len(left),
                        "api_ninjas_rows": len(right),
                    })
                    continue
                source_row, api_row = left[0], right[0]
                country_code = str(api_row.get("country") or "").strip().upper()
                team_type = str(api_row.get("team_type") or "").strip().casefold()
                gender = str(api_row.get("gender_scope") or "").strip().casefold()
                candidate = {
                    "target_provider": provider,
                    "target_provider_team_id": str(source_row.get("provider_entity_id")),
                    "target_provider_team_name": source_row.get("name"),
                    "api_ninjas_team_id": str(api_row.get("provider_entity_id")),
                    "api_ninjas_team_name": api_row.get("name"),
                    "competition_scope": provider_competition,
                    "api_ninjas_domestic_competition": api_competition,
                    "identity_basis": "unique_exact_normalized_team_name_within_same_current_domestic_competition",
                    "country_code_iso3166_alpha2": country_code or None,
                    "country_name_from_iso_code": COUNTRY_NAMES.get(country_code),
                    "team_type_from_api_ninjas": team_type or None,
                    "gender_from_api_ninjas": gender or None,
                    "gender_scope_normalized_candidate": (
                        "male" if gender == "men" else "female" if gender == "women" else None
                    ),
                    "status": (
                        "scope_corroboration_candidate"
                        if country_code and team_type in {"club", "national"} and gender in {"men", "women"}
                        else "held_api_ninjas_scope_incomplete"
                    ),
                }
                candidates.append(candidate)
                all_candidates.append(candidate)
            ambiguous_keys = {
                key for key in set(source_by_name) & set(api_by_name)
                if len(source_by_name[key]) != 1 or len(api_by_name[key]) != 1
            }
            unmatched = []
            for key, rows_for_name in sorted(source_by_name.items()):
                if key in api_by_name or key in ambiguous_keys:
                    continue
                for row in rows_for_name:
                    near_matches = []
                    for api_row in api_comp:
                        api_name = str(api_row.get("name") or "")
                        score = SequenceMatcher(
                            None, key, normalize_entity_name(api_name)
                        ).ratio()
                        if score >= 0.60:
                            near_matches.append({
                                "api_ninjas_team_id": str(api_row.get("provider_entity_id") or ""),
                                "api_ninjas_team_name": api_name,
                                "normalized_name_similarity": round(score, 3),
                                "review_status": "manual_review_only_not_an_identity_match",
                            })
                    near_matches.sort(
                        key=lambda item: (
                            -item["normalized_name_similarity"],
                            item["api_ninjas_team_name"],
                            item["api_ninjas_team_id"],
                        )
                    )
                    unmatched.append({
                        "provider": provider,
                        "provider_entity_id": str(row.get("provider_entity_id") or ""),
                        "name": row.get("name"),
                        "normalized_name": key,
                        "competition_provider_id": provider_competition,
                        "reason": "no_unique_exact_normalized_name_match_in_api_ninjas_competition",
                        "near_name_candidates": near_matches[:3],
                    })
            reports.append({
                "target_provider": provider,
                "target_competition_provider_id": provider_competition,
                "api_ninjas_competition_code": api_competition,
                "target_team_rows": len(source),
                "api_ninjas_team_rows": len(api_comp),
                "unique_exact_name_candidates": len(candidates),
                "scope_complete_candidates": sum(
                    row["status"] == "scope_corroboration_candidate" for row in candidates
                ),
                "ambiguous_name_groups": ambiguous,
                "unmatched_target_team_rows": len(unmatched),
                "unmatched_target_teams": unmatched,
                "candidates": candidates,
                "interpretation": (
                    "Candidates are read-only corroboration leads. API Ninjas scope values are not "
                    "copied into the target provider's source rows and no provider link is created."
                ),
            })
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "database_writes": False,
        "provider_links_created": 0,
        "provider_scope_fields_updated": 0,
        "target_team_rows_examined": len(target_rows),
        "api_ninjas_team_rows_examined": len(api_rows),
        "unique_exact_name_candidates": len(all_candidates),
        "scope_complete_candidates": sum(
            row["status"] == "scope_corroboration_candidate" for row in all_candidates
        ),
        "competitions": reports,
        "interpretation": (
            "This audit identifies exact-name candidates within mapped current domestic competitions. "
            "It does not approve cross-provider identity, transfer country/type/gender values, or "
            "infer age-group or squad scope."
        ),
    }


def audit_team_scope_corroboration(database_url: str) -> dict[str, Any]:
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    columns = ("provider", "provider_entity_id", "name", "country", "team_type", "gender_scope", "raw_payload")
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(
                """SELECT provider, provider_entity_id, name, country, team_type,
                          gender_scope, raw_payload
                   FROM provider_source_entities
                   WHERE entity_type = 'team'
                     AND provider IN ('api_ninjas', 'highlightly', 'livescore_football')
                   ORDER BY provider, provider_entity_id"""
            )
            rows = [dict(zip(columns, values)) for values in cursor.fetchall()]
    report = build_corroboration_report(rows)
    report["database_read_only"] = True
    report["source_rows_read"] = len(rows)
    return report


def main() -> int:
    import os
    report = audit_team_scope_corroboration(os.getenv("PROVIDER_DATABASE_URL", "").strip())
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
                      encoding="utf-8")
    print(json.dumps({
        key: report[key] for key in (
            "checked_at", "read_only", "target_team_rows_examined",
            "api_ninjas_team_rows_examined", "unique_exact_name_candidates",
            "scope_complete_candidates", "provider_links_created",
            "provider_scope_fields_updated",
        )
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
