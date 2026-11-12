"""Build a read-only, provider-independent competition catalogue from source consensus.

This catalogue is a review aid, not a canonical database. It never creates
canonical rows, provider links, fixture staging records, or predictions.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from provider_entity_crosswalk import normalize_entity_name


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


def build_provider_independent_competition_catalogue(
    provider_entities: Mapping[str, Iterable[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Group exact competition-name/country identities across independent providers.

    Entries without country context are retained but cannot be corroborated.
    No fuzzy matching, aliases, canonical IDs, or automatic approvals are used.
    """
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
            source = {
                "provider": provider_name,
                "provider_competition_id": str(source_id),
                "competition_name": name,
                "country": country or None,
                "observation_count": int(entity.get("observation_count") or 0),
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
        entries.append({
            "normalized_name": entry["normalized_name"],
            "normalized_country": entry["normalized_country"],
            "competition_names": sorted(entry["competition_names"], key=str.casefold),
            "countries": sorted(entry["countries"], key=str.casefold),
            "provider_count": len(providers),
            "providers": providers,
            "sources": sources,
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
        "country_unscoped_sources": unscoped,
        "canonical_rows_created": 0,
        "provider_links_created": 0,
        "automatic_mapping_approvals": 0,
    }
