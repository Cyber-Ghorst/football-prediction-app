"""Build a read-only, provider-independent competition catalogue from source consensus.

This catalogue is a review aid, not a canonical database. It never creates
canonical rows, provider links, fixture staging records, or predictions.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from provider_entity_crosswalk import normalize_entity_name
from provider_neutral_identity import canonical_competition_key


def _country_key(value: Any) -> str:
    key = normalize_entity_name(value)
    aliases = {
        "de": "germany", "deutschland": "germany",
        "es": "spain", "espana": "spain",
        "it": "italy", "italia": "italy",
        "fr": "france", "nl": "netherlands", "nederland": "netherlands",
        "pt": "portugal", "us": "united states", "usa": "united states",
    }
    return aliases.get(key, key)


def _season_years(*values: Any) -> list[int]:
    """Extract years only from human-readable season labels, never provider IDs."""
    years = set()
    for value in values:
        for match in re.findall(r"(?<!\d)(20\d{2})(?!\d)", str(value or "")):
            years.add(int(match))
    return sorted(years)


def _season_evidence(
    provider: str,
    competition_id: str,
    provider_seasons: Mapping[str, Iterable[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    rows = []
    for season in provider_seasons.get(provider, []) or []:
        if not isinstance(season, Mapping):
            continue
        parent_id = str(season.get("provider_competition_id") or "")
        if parent_id != competition_id:
            continue
        name = str(season.get("name") or season.get("season_name") or "").strip()
        season_id = str(season.get("id") or season.get("provider_season_id") or "").strip()
        rows.append({
            "provider": provider,
            "provider_season_id": season_id or None,
            "season_name": name or None,
            # Provider season IDs are opaque identifiers. Numeric IDs such as
            # "2037" must never be mistaken for calendar season years.
            "start_years": _season_years(name),
            "observation_count": int(season.get("observation_count") or 0),
        })
    return sorted(rows, key=lambda row: (row["season_name"] or "", row["provider_season_id"] or ""))


def _competition_type_evidence(sources: list[dict[str, Any]]) -> dict[str, Any]:
    values = []
    for source in sources:
        value = str(source.get("competition_type") or "").strip()
        if value:
            values.append({
                "provider": source["provider"],
                "value": value,
                "normalized_value": normalize_entity_name(value),
            })
    distinct = sorted({row["normalized_value"] for row in values})
    if not values:
        status = "unknown_not_supplied"
    elif len(distinct) == 1 and len({row["provider"] for row in values}) >= 2:
        status = "corroborated_same_type"
    elif len(distinct) > 1:
        status = "provider_type_conflict"
    else:
        status = "single_provider_type_evidence"
    return {"status": status, "values": values}


def _identity_candidate(
    competition_name: str,
    country: str,
    type_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Generate a review-only key only when type is corroborated by providers."""
    if type_evidence.get("status") != "corroborated_same_type":
        return {
            "identity_candidate_key": None,
            "identity_candidate_key_status": "blocked_without_corroborated_competition_type",
        }
    values = type_evidence.get("values") or []
    normalized_types = {
        str(value.get("normalized_value") or "")
        for value in values if isinstance(value, Mapping)
    }
    if len(normalized_types) != 1 or not next(iter(normalized_types), ""):
        return {
            "identity_candidate_key": None,
            "identity_candidate_key_status": "blocked_without_corroborated_competition_type",
        }
    competition_type = next(iter(normalized_types))
    try:
        key = canonical_competition_key(competition_name, country, competition_type)
    except ValueError:
        return {
            "identity_candidate_key": None,
            "identity_candidate_key_status": "blocked_missing_identity_dimension",
        }
    return {
        "identity_candidate_key": key,
        "identity_candidate_key_status": "generated_for_manual_review_only",
    }


def _season_consensus(sources: list[dict[str, Any]]) -> dict[str, Any]:
    provider_years = {
        source["provider"]: {
            year
            for season in source.get("seasons", [])
            for year in season.get("start_years", [])
        }
        for source in sources
    }
    populated = {provider: years for provider, years in provider_years.items() if years}
    common_years = set.intersection(*populated.values()) if len(populated) >= 2 else set()
    if len(populated) < 2:
        status = "insufficient_provider_season_evidence"
    elif common_years:
        status = "cross_provider_start_year_overlap"
    else:
        status = "season_year_conflict"
    return {
        "status": status,
        "provider_start_years": {
            provider: sorted(years) for provider, years in sorted(provider_years.items())
        },
        "shared_start_years": sorted(common_years),
        "season_records": [
            season for source in sources for season in source.get("seasons", [])
        ],
    }


def build_provider_independent_competition_catalogue(
    provider_entities: Mapping[str, Iterable[Mapping[str, Any]]],
    provider_seasons: Mapping[str, Iterable[Mapping[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Group exact competition-name/country identities and attach review evidence.

    Season overlap is evidence only, not proof of equivalent season identity.
    Competition types are compared only when explicitly supplied by providers.
    Entries without country context cannot be corroborated.
    """
    provider_seasons = provider_seasons or {}
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    unscoped: list[dict[str, Any]] = []

    for provider, entities in sorted(provider_entities.items()):
        provider_name = str(provider or "").strip().casefold()
        if not provider_name:
            continue
        for entity in entities or []:
            if not isinstance(entity, Mapping):
                continue
            source_id = entity.get("id") or entity.get("provider_competition_id")
            name = str(entity.get("name") or entity.get("competition_name") or "").strip()
            country = str(entity.get("country") or "").strip()
            name_key = normalize_entity_name(name)
            country_key = _country_key(country)
            if not source_id or not name_key:
                continue
            competition_id = str(source_id)
            source = {
                "provider": provider_name,
                "provider_competition_id": competition_id,
                "competition_name": name,
                "country": country or None,
                "competition_type": entity.get("competition_type"),
                "observation_count": int(entity.get("observation_count") or 0),
                "seasons": _season_evidence(provider_name, competition_id, provider_seasons),
            }
            if not country_key:
                unscoped.append(source)
                continue
            key = (name_key, country_key)
            entry = grouped.setdefault(key, {
                "normalized_name": name_key,
                "normalized_country": country_key,
                "competition_names": set(),
                "countries": set(),
                "providers": set(),
                "sources": [],
            })
            entry["competition_names"].add(name)
            entry["countries"].add(country)
            entry["providers"].add(provider_name)
            entry["sources"].append(source)

    entries = []
    for entry in grouped.values():
        providers = sorted(entry["providers"])
        sources = sorted(
            entry["sources"],
            key=lambda row: (row["provider"], row["competition_name"].casefold(),
                             row["provider_competition_id"]),
        )
        competition_names = sorted(entry["competition_names"], key=str.casefold)
        countries = sorted(entry["countries"], key=str.casefold)
        type_evidence = _competition_type_evidence(sources)
        identity_candidate = _identity_candidate(
            competition_names[0], entry["normalized_country"], type_evidence
        )
        entries.append({
            "normalized_name": entry["normalized_name"],
            "normalized_country": entry["normalized_country"],
            "competition_names": competition_names,
            "countries": countries,
            "provider_count": len(providers),
            "providers": providers,
            "sources": sources,
            "season_evidence": _season_consensus(sources),
            "competition_type_evidence": type_evidence,
            **identity_candidate,
            "status": "corroborated_multi_provider" if len(providers) >= 2 else "single_provider_only",
            "canonical_mapping_created": False,
        })
    entries.sort(key=lambda row: (
        row["normalized_country"], row["normalized_name"], row["providers"]
    ))
    unscoped.sort(key=lambda row: (
        row["provider"], row["competition_name"].casefold(),
        row["provider_competition_id"],
    ))
    seed_review_candidates = [
        {
            "competition_name": row["competition_names"][0],
            "country": row["countries"][0],
            "normalized_name": row["normalized_name"],
            "normalized_country": row["normalized_country"],
            "provider_count": row["provider_count"],
            "providers": row["providers"],
            "sources": row["sources"],
            "season_evidence": row["season_evidence"],
            "competition_type_evidence": row["competition_type_evidence"],
            "identity_candidate_key": row["identity_candidate_key"],
            "identity_candidate_key_status": row["identity_candidate_key_status"],
            "status": "eligible_for_manual_canonical_seed_review",
            "canonical_record_created": False,
            "provider_links_created": False,
            "automatic_approval": False,
            "review_requirement": (
                "Verify competition identity, competition type, active season, "
                "and cross-provider season alignment before any canonical catalogue "
                "entry or provider link is created."
            ),
        }
        for row in entries
        if row["status"] == "corroborated_multi_provider"
    ]

    return {
        "method": "exact_normalized_competition_name_and_country",
        "provider_count": len([p for p in provider_entities if str(p).strip()]),
        "competition_count": len(entries),
        "corroborated_competition_count": sum(
            row["status"] == "corroborated_multi_provider" for row in entries
        ),
        "single_provider_competition_count": sum(
            row["status"] == "single_provider_only" for row in entries
        ),
        "country_unscoped_source_count": len(unscoped),
        "competitions": entries,
        "canonical_seed_review_candidate_count": len(seed_review_candidates),
        "canonical_seed_review_candidates": seed_review_candidates,
        "country_unscoped_sources": unscoped,
        "canonical_rows_created": 0,
        "provider_links_created": 0,
        "automatic_mapping_approvals": 0,
    }
