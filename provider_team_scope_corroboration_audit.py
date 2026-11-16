"""Read-only cross-provider team-scope corroboration candidates.

Matches current API Ninjas club records to 2026-season API-Football,
Highlightly and LiveScoreFootball participants by unique normalized team name
within an explicitly mapped domestic competition. It never writes scope values or links.
"""
from __future__ import annotations

import json
from difflib import SequenceMatcher
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from provider_data_storage import _connect
from provider_entity_crosswalk import normalize_entity_name
from provider_season_provenance import (
    explicit_season_label,
    is_verified_2026_27_snapshot,
    season_match,
)

REPORT = Path("provider-team-scope-corroboration-audit.json")
COMPETITION_MAP = {
    ("api_football", "39"): "epl",
    ("api_football", "140"): "laliga",
    ("api_football", "135"): "seriea",
    ("api_football", "78"): "bundesliga",
    ("api_football", "61"): "ligue1",
    ("livescore_football", "ger.1"): "bundesliga",
    ("livescore_football", "fra.1"): "ligue1",
    ("highlightly", "33973"): "epl",
    ("highlightly", "119924"): "laliga",
    ("highlightly", "115669"): "seriea",
    ("highlightly", "67162"): "bundesliga",
    ("highlightly", "52695"): "ligue1",
}
COUNTRY_NAMES = {"DE": "Germany", "FR": "France", "GB": "United Kingdom", "ES": "Spain", "IT": "Italy"}


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


def _api_ninjas_scope_rows(
    api_rows: list[Mapping[str, Any]],
) -> tuple[dict[str, list[Mapping[str, Any]]], dict[str, int]]:
    """Join seasonless scope metadata to standings only by exact provider ID and competition."""
    catalogues: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    standings: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in api_rows:
        raw = _mapping(row.get("raw_payload"))
        if raw.get("team_evidence_method") == "season_scoped_standings_row":
            key = (
                str(raw.get("competition_provider_id") or "").strip(),
                str(raw.get("provider_team_id") or "").strip(),
            )
            if all(key):
                standings[key].append(row)
            continue
        provider_id = str(row.get("provider_entity_id") or "").strip()
        if not provider_id:
            continue
        for competition in _competition_ids(raw, "api_ninjas"):
            catalogues[(competition, provider_id)].append(row)

    by_competition: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    counts = {
        "catalogue_scope_rows": len(catalogues),
        "season_standings_rows": sum(len(items) for items in standings.values()),
        "joined_verified": 0,
        "missing_standings": 0,
        "ambiguous_catalogue": 0,
        "ambiguous_standings": 0,
        "mismatched_identity_or_scope": 0,
        "invalid_season_evidence": 0,
    }
    counts["orphan_standings"] = sum(
        len(items) for key, items in standings.items() if key not in catalogues
    )
    for (competition, provider_team_id), catalogue_matches in sorted(catalogues.items()):
        if len(catalogue_matches) != 1:
            counts["ambiguous_catalogue"] += 1
            continue
        catalogue = catalogue_matches[0]
        catalogue_raw = _mapping(catalogue.get("raw_payload"))
        season_matches = standings.get((competition, provider_team_id), [])
        joined = None
        join_status = "missing_standings"
        if not season_matches:
            counts["missing_standings"] += 1
        elif len(season_matches) != 1:
            join_status = "ambiguous_standings"
            counts["ambiguous_standings"] += 1
        else:
            season_row = season_matches[0]
            season_raw = _mapping(season_row.get("raw_payload"))
            returned_season = season_raw.get("provider_returned_season")
            returned_label = str(season_raw.get("provider_returned_season_label") or "").strip()
            normalized_label = explicit_season_label({"season_label": returned_label})
            checks = {
                "provider_team_id_matches": str(season_raw.get("provider_team_id") or "").strip() == provider_team_id,
                "competition_matches": str(season_raw.get("competition_provider_id") or "").strip() == competition,
                "provider_returned_league_matches": str(season_raw.get("provider_returned_league") or "").strip().casefold() == competition.casefold(),
                "persisted_team_key_matches": str(season_row.get("provider_entity_id") or "").strip() == f"{competition}:{provider_team_id}",
                "season_provider_key_matches": str(season_raw.get("season_provider_id") or "").strip() == f"{competition}:2026",
                "team_name_matches": normalize_entity_name(season_row.get("name")) == normalize_entity_name(catalogue.get("name")),
                "evidence_method_matches": season_raw.get("team_evidence_method") == "season_scoped_standings_row",
                "season_year_is_2026": not isinstance(returned_season, bool) and isinstance(returned_season, int) and returned_season == 2026,
                "season_label_is_2026_27": returned_label in {"2026-27", "2026/27"} and normalized_label == "2026/27",
            }
            if all(checks.values()):
                joined = season_row
                join_status = "verified"
                counts["joined_verified"] += 1
            else:
                join_status = "invalid_season_evidence" if (
                    not checks["season_year_is_2026"] or not checks["season_label_is_2026_27"]
                ) else "mismatched_identity_or_scope"
                counts[join_status] += 1

        merged = dict(catalogue)
        merged_raw = dict(catalogue_raw)
        # A seasonless club catalogue must never contribute an old/stale
        # season label. Only a validated standings join may add season_label.
        for season_key in (
            "season_label", "season_name", "catalogue_season_label",
            "catalogue_reference_season", "season_year", "season",
        ):
            merged_raw.pop(season_key, None)
        merged_raw["domestic_league_codes"] = [competition]
        merged_raw["season_evidence_join_status"] = join_status
        if joined is not None:
            season_raw = dict(_mapping(joined.get("raw_payload")))
            merged_raw["season_label"] = "2026/27"
            merged_raw["season_standings_provider_entity_id"] = str(joined.get("provider_entity_id") or "")
            merged_raw["season_standings_evidence"] = season_raw
        merged_raw["catalogue_scope_evidence"] = dict(catalogue_raw)
        merged["raw_payload"] = merged_raw
        by_competition[competition].append(merged)
    return by_competition, counts


def build_corroboration_report(
    rows: list[Mapping[str, Any]],
    approved_corroborations: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    all_approval_rows = list(approved_corroborations or [])
    # Match the provider-neutral identity audit: only snapshots explicitly
    # verified on both sides for 2026/27 count as approved scope evidence.
    approved_rows = [
        row for row in all_approval_rows
        if is_verified_2026_27_snapshot(row.get("evidence_snapshot"))
    ]
    legacy_provisional_rows = [
        row for row in all_approval_rows
        if not is_verified_2026_27_snapshot(row.get("evidence_snapshot"))
    ]
    approved_by_provider = Counter(
        str(row.get("provider") or "").casefold() for row in approved_rows
    )
    approved_by_match_method = Counter(
        str(row.get("match_method") or "") for row in approved_rows
    )
    api_rows = [row for row in rows if str(row.get("provider") or "").casefold() == "api_ninjas"]
    target_rows = [
        row for row in rows
        if str(row.get("provider") or "").casefold() in {"api_football", "highlightly", "livescore_football"}
    ]
    api_by_comp, api_season_join_counts = _api_ninjas_scope_rows(api_rows)

    reports = []
    all_candidates = []
    for provider in ("api_football", "highlightly", "livescore_football"):
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
                season_verified, target_label, api_label, season_status = season_match(
                    source_row.get("raw_payload"), api_row.get("raw_payload")
                )
                api_raw = _mapping(api_row.get("raw_payload"))
                join_status = str(api_raw.get("season_evidence_join_status") or "missing_standings")
                season_verified = season_verified and join_status == "verified"
                if join_status != "verified":
                    season_status = (
                        "held_missing_explicit_season" if join_status == "missing_standings"
                        else f"held_api_ninjas_{join_status}"
                    )
                scope_complete = bool(
                    country_code and team_type in {"club", "national"}
                    and gender in {"men", "women"}
                )
                candidate = {
                    "target_provider": provider,
                    "target_provider_team_id": str(source_row.get("provider_entity_id")),
                    "target_provider_team_name": source_row.get("name"),
                    "api_ninjas_team_id": str(api_row.get("provider_entity_id")),
                    "api_ninjas_team_name": api_row.get("name"),
                    "api_ninjas_season_standings_provider_entity_id": api_raw.get("season_standings_provider_entity_id"),
                    "api_ninjas_season_evidence_join_status": join_status,
                    "competition_scope": provider_competition,
                    "api_ninjas_domestic_competition": api_competition,
                    "identity_basis": "unique_exact_normalized_team_name_within_same_current_domestic_competition",
                    "target_season_label": target_label,
                    "api_ninjas_season_label": api_label,
                    "season_match_verified": season_verified,
                    "season_gate_status": season_status,
                    "country_code_iso3166_alpha2": country_code or None,
                    "country_name_from_iso_code": COUNTRY_NAMES.get(country_code),
                    "team_type_from_api_ninjas": team_type or None,
                    "gender_from_api_ninjas": gender or None,
                    "gender_scope_normalized_candidate": (
                        "male" if gender == "men" else "female" if gender == "women" else None
                    ),
                    "status": (
                        "scope_corroboration_candidate"
                        if scope_complete and season_verified
                        else season_status if not season_verified
                        else "held_api_ninjas_scope_incomplete"
                    ),
                }
                candidates.append(candidate)
                all_candidates.append(candidate)
            ambiguous_keys = {
                key for key in set(source_by_name) & set(api_by_name)
                if len(source_by_name[key]) != 1 or len(api_by_name[key]) != 1
            }
            approved_for_competition = [
                row for row in approved_rows
                if str(row.get("provider") or "").casefold() == provider
                and str(row.get("competition_provider_id") or "") == provider_competition
            ]
            approved_alias_by_target = {
                str(row.get("provider_entity_id")): row
                for row in approved_for_competition
                if row.get("match_method") == "manual_official_competition_alias_review"
                and _mapping(row.get("evidence_snapshot")).get("season_match_verified") is True
                and _mapping(row.get("evidence_snapshot")).get("target_season_label") == "2026/27"
                and _mapping(row.get("evidence_snapshot")).get("api_ninjas_season_label") == "2026/27"
            }
            approved_aliases = []
            unmatched = []
            for key, rows_for_name in sorted(source_by_name.items()):
                if key in api_by_name or key in ambiguous_keys:
                    continue
                for row in rows_for_name:
                    target_id = str(row.get("provider_entity_id") or "")
                    approved_alias = approved_alias_by_target.get(target_id)
                    if approved_alias:
                        approved_aliases.append({
                            "provider_entity_id": target_id,
                            "target_team_name": row.get("name"),
                            "api_ninjas_team_id": approved_alias.get("corroborating_entity_id"),
                            "match_method": approved_alias.get("match_method"),
                            "country_name": approved_alias.get("country_name"),
                            "team_type": approved_alias.get("team_type"),
                            "gender_scope": approved_alias.get("gender_scope"),
                        })
                        continue
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
                                "season_label": explicit_season_label(api_row.get("raw_payload")),
                                "normalized_name_similarity": round(score, 3),
                                "country_code_iso3166_alpha2": str(api_row.get("country") or "").strip().upper() or None,
                                "country_name_from_iso_code": COUNTRY_NAMES.get(str(api_row.get("country") or "").strip().upper()),
                                "team_type_from_api_ninjas": str(api_row.get("team_type") or "").strip().casefold() or None,
                                "gender_from_api_ninjas": str(api_row.get("gender_scope") or "").strip().casefold() or None,
                                "api_ninjas_domestic_competition": api_competition,
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
                        "source_season_label": explicit_season_label(row.get("raw_payload")),
                        "reason": "no_unique_exact_normalized_name_match_in_api_ninjas_competition",
                        "near_name_candidates": near_matches[:3],
                    })
            reports.append({
                "target_provider": provider,
                "target_competition_provider_id": provider_competition,
                "api_ninjas_competition_code": api_competition,
                "target_team_rows": len(source),
                "api_ninjas_team_rows": len(api_comp),
                "api_ninjas_team_catalogue": [
                    {
                        "provider_entity_id": str(row.get("provider_entity_id") or ""),
                        "name": row.get("name"),
                        "season_label": explicit_season_label(row.get("raw_payload")),
                        "country_code": str(row.get("country") or "").strip().upper() or None,
                        "team_type": str(row.get("team_type") or "").strip().casefold() or None,
                        "gender_scope": str(row.get("gender_scope") or "").strip().casefold() or None,
                        "season_label": explicit_season_label(row.get("raw_payload")),
                    }
                    for row in sorted(
                        api_comp,
                        key=lambda item: (
                            str(item.get("name") or "").casefold(),
                            str(item.get("provider_entity_id") or ""),
                        ),
                    )
                ],
                "unique_exact_name_candidates": len(candidates),
                "scope_complete_candidates": sum(
                    row["status"] == "scope_corroboration_candidate" for row in candidates
                ),
                "ambiguous_name_groups": ambiguous,
                "approved_exact_corroborations": 0,
                "legacy_provisional_exact_corroborations": sum(
                    row.get("match_method") == "unique_exact_normalized_team_name_within_same_current_domestic_competition"
                    for row in approved_for_competition
                ),
                "approved_manual_alias_corroborations": len(approved_aliases),
                "approved_manual_aliases": approved_aliases,
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
        "api_ninjas_season_evidence_join": api_season_join_counts,
        "unique_exact_name_candidates": len(all_candidates),
        "scope_complete_candidates": sum(
            row["status"] == "scope_corroboration_candidate" for row in all_candidates
        ),
        "approved_scope_corroborations": len(approved_rows),
        "legacy_provisional_scope_corroborations": len(legacy_provisional_rows),
        "approved_by_provider": {
            provider: approved_by_provider.get(provider, 0)
            for provider in ("api_football", "highlightly", "livescore_football")
        },
        "approved_by_match_method": {
            "unique_exact_normalized_team_name_within_same_current_domestic_competition":
                approved_by_match_method.get(
                    "unique_exact_normalized_team_name_within_same_current_domestic_competition", 0
                ),
            "manual_official_competition_alias_review": approved_by_match_method.get(
                "manual_official_competition_alias_review", 0
            ),
        },
        "competitions": reports,
        "interpretation": (
            "This audit identifies exact-name candidates within mapped domestic competitions. "
            "Only explicit matching 2026/27 labels on both source records pass the season gate. "
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
                     AND provider IN ('api_ninjas', 'api_football', 'highlightly', 'livescore_football')
                   ORDER BY provider, provider_entity_id"""
            )
            rows = [dict(zip(columns, values)) for values in cursor.fetchall()]
            cursor.execute(
                """SELECT provider, provider_entity_id, corroborating_entity_id,
                          competition_provider_id, match_method, country_name,
                          team_type, gender_scope, evidence_snapshot
                   FROM provider_team_scope_corroborations
                   ORDER BY provider, provider_entity_id, corroborating_entity_id"""
            )
            approved_columns = (
                "provider", "provider_entity_id", "corroborating_entity_id",
                "competition_provider_id", "match_method", "country_name",
                "team_type", "gender_scope", "evidence_snapshot",
            )
            approved_rows = [
                dict(zip(approved_columns, values)) for values in cursor.fetchall()
            ]
    report = build_corroboration_report(rows, approved_rows)
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
