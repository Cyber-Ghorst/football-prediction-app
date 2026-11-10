"""Conservative provider-to-canonical entity crosswalk review.

Name matches are suggestions only. A persisted link requires an explicit
approval reason and an existing canonical entity.
"""
from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Any, Iterable, Mapping

from football_repository import ensure_football_repository
from provider_data_storage import _connect

SUPPORTED_PROVIDERS = {
    "openligadb", "openfootball", "open_matchday",
    "livescore_football", "bzzoiro",
}
ENTITY_TABLES = {
    "league": ("football_leagues", "league_id"),
    "season": ("football_seasons", "season_id"),
    "team": ("football_teams", "team_id"),
    "fixture": ("football_fixtures", "fixture_id"),
}


def normalize_entity_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.casefold().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _value(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return value
    return None

def _display_value(value: Any) -> str:
    if isinstance(value, Mapping):
        value = value.get("name") or value.get("displayName") or value.get("display_name")
    return str(value or "").strip()


def build_entity_crosswalk_candidates(
    provider: str,
    entity_type: str,
    source_entities: Iterable[Mapping[str, Any]],
    canonical_entities: Iterable[Mapping[str, Any]],
    *,
    canonical_parent_ids: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Suggest exact name/country or parent-scoped season matches; never auto-link."""
    provider_name = str(provider or "").strip().casefold()
    if provider_name not in SUPPORTED_PROVIDERS:
        raise ValueError("Unsupported provider.")
    if entity_type not in {"league", "season", "team"}:
        raise ValueError("entity_type must be league, season or team.")

    parent_map = {str(k): str(v) for k, v in (canonical_parent_ids or {}).items()}
    canonical = [row for row in canonical_entities if isinstance(row, Mapping)]
    output: list[dict[str, Any]] = []

    for source in source_entities:
        if not isinstance(source, Mapping):
            continue
        if entity_type == "league":
            source_id = _value(source, "provider_competition_id", "competition_id", "id", "slug")
            source_name = _value(source, "competition_name", "name", "league_name")
            source_country = _value(source, "country", "country_name")
            source_parent = None
        elif entity_type == "team":
            source_id = _value(source, "provider_team_id", "team_id", "id")
            source_name = _value(source, "team_name", "name", "display_name")
            source_country = _value(source, "country", "country_name")
            source_parent = None
        else:
            source_id = _value(source, "provider_season_id", "season_id", "id")
            source_name = _value(source, "season_name", "name", "season")
            source_country = None
            provider_parent = _value(source, "provider_competition_id", "competition_id", "league_id")
            source_parent = parent_map.get(str(provider_parent)) if provider_parent is not None else None

        base = {
            "provider": provider_name,
            "entity_type": entity_type,
            "provider_entity_id": str(source_id) if source_id is not None else None,
            "provider_name": str(source_name or ""),
            "canonical_entity_id": None,
            "canonical_name": None,
            "status": "unmatched",
            "reason": "",
        }
        if source_id is None or not source_name:
            output.append({**base, "status": "invalid_source_identity",
                           "reason": "Provider entity ID and name are both required."})
            continue
        if entity_type == "season" and source_parent is None:
            output.append({**base, "status": "parent_competition_unmapped",
                           "reason": "A verified provider-competition to canonical-competition link is required first."})
            continue

        source_key = normalize_entity_name(source_name)
        matches = []
        for target in canonical:
            if entity_type == "league":
                target_id = _value(target, "league_id", "canonical_entity_id")
                target_name = _value(target, "name", "competition_name")
                target_country = _value(target, "country", "country_name")
                exact_context = (
                    bool(source_country) and bool(target_country)
                    and normalize_entity_name(_display_value(source_country)) == normalize_entity_name(_display_value(target_country))
                )
            elif entity_type == "team":
                target_id = _value(target, "team_id", "canonical_entity_id")
                target_name = _value(target, "name", "team_name")
                target_country = _value(target, "country", "country_name")
                exact_context = (
                    bool(source_country) and bool(target_country)
                    and normalize_entity_name(source_country) == normalize_entity_name(target_country)
                )
            else:
                target_id = _value(target, "season_id", "canonical_entity_id")
                target_name = _value(target, "name", "season_name")
                target_parent = _value(target, "league_id", "canonical_league_id")
                exact_context = str(target_parent or "") == source_parent

            if (
                target_id is not None and target_name
                and normalize_entity_name(target_name) == source_key
                and exact_context
            ):
                matches.append((str(target_id), str(target_name)))

        if len(matches) == 1:
            output.append({
                **base, "canonical_entity_id": matches[0][0],
                "canonical_name": matches[0][1],
                "status": "candidate_requires_manual_approval",
                "reason": "Exact normalized name and required country/parent context match; explicit review is still mandatory.",
            })
        elif len(matches) > 1:
            output.append({
                **base, "status": "ambiguous_multiple_canonical_matches",
                "reason": f"{len(matches)} canonical entities match the exact identity criteria.",
            })
        else:
            output.append({
                **base, "status": "no_exact_contextual_match",
                "reason": "No exact name plus country/parent-context match; no link is proposed.",
            })
    return output


def save_explicit_provider_entity_links(
    database_url: str,
    *,
    links: list[Mapping[str, Any]],
    approval_reason: str,
) -> int:
    """Persist only explicitly reviewed links to existing canonical entities."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    reason = str(approval_reason or "").strip()
    if len(reason) < 12:
        raise ValueError("An explicit approval_reason of at least 12 characters is required.")
    if not isinstance(links, list) or not links:
        raise ValueError("At least one explicit provider entity link is required.")

    prepared = []
    for link in links:
        if not isinstance(link, Mapping):
            raise ValueError("Every link must be an object.")
        provider = str(link.get("provider") or "").strip().casefold()
        entity_type = str(link.get("entity_type") or "").strip().casefold()
        provider_id = str(link.get("provider_entity_id") or "").strip()
        canonical_id = str(link.get("canonical_entity_id") or "").strip()
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError("Unsupported provider in explicit link.")
        if entity_type not in ENTITY_TABLES:
            raise ValueError("Unsupported canonical entity type.")
        if not provider_id or not canonical_id:
            raise ValueError("Provider and canonical entity IDs are required.")
        table, primary_key = ENTITY_TABLES[entity_type]
        link_id = str(uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{provider}:{entity_type}:{provider_id}",
        ))
        prepared.append((provider, entity_type, provider_id, canonical_id,
                         table, primary_key, link_id))

    ensure_football_repository(database_url)
    saved = 0
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            for provider, entity_type, provider_id, canonical_id, table, primary_key, link_id in prepared:
                cursor.execute(
                    f"SELECT {primary_key} FROM {table} WHERE {primary_key} = %s",
                    (canonical_id,),
                )
                if cursor.fetchone() is None:
                    raise ValueError(
                        f"Canonical {entity_type} {canonical_id} does not exist."
                    )
                cursor.execute(
                    """SELECT canonical_entity_id FROM provider_entity_links
                       WHERE provider = %s AND entity_type = %s AND provider_entity_id = %s""",
                    (provider, entity_type, provider_id),
                )
                existing = cursor.fetchone()
                if existing and str(existing[0]) != canonical_id:
                    raise ValueError(
                        f"Conflicting existing link for {provider} {entity_type} {provider_id}."
                    )
                if existing:
                    continue
                cursor.execute(
                    """INSERT INTO provider_entity_links (
                           link_id, provider, entity_type, provider_entity_id, canonical_entity_id
                       ) VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (provider, entity_type, provider_entity_id) DO NOTHING""",
                    (link_id, provider, entity_type, provider_id, canonical_id),
                )
                saved += 1
    return saved
