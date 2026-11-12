"""Build read-only provider entity crosswalk review reports from archived fixtures."""
from __future__ import annotations

from typing import Any, Mapping

from football_repository import (
    get_repository_leagues,
    get_repository_seasons,
    get_repository_teams,
)
import provider_data_storage
import provider_entity_crosswalk
from provider_entity_crosswalk import (
    build_entity_crosswalk_candidates,
    extract_provider_entities_from_observations,
)


def load_provider_observation_snapshots(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
    """Resolve the snapshot loader lazily after provider storage has finished importing."""
    return provider_data_storage.load_provider_observation_snapshots(*args, **kwargs)


def _load_provider_links_by_type(database_url: str, *, provider: str) -> dict[str, dict[str, str]]:
    """Use the grouped loader when available; fall back for older app deployments."""
    grouped_loader = getattr(
        provider_entity_crosswalk, "load_provider_entity_links_by_type", None
    )
    if callable(grouped_loader):
        return grouped_loader(database_url, provider=provider)
    return {
        entity_type: provider_entity_crosswalk.load_provider_entity_links(
            database_url, provider=provider, entity_type=entity_type
        )
        for entity_type in ("league", "season", "team")
    }


def load_canonical_crosswalk_catalogue(database_url: str) -> dict[str, list[dict[str, Any]]]:
    """Load the shared canonical catalogue once for a multi-provider audit."""
    return {
        "leagues": get_repository_leagues(database_url),
        "seasons": get_repository_seasons(database_url),
        "teams": get_repository_teams(database_url),
    }


def build_provider_crosswalk_review_report(
    database_url: str,
    *,
    provider: str,
    snapshot_limit: int = 100,
    canonical_catalogue: Mapping[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Combine archived source entities with canonical records and exact-match candidates."""
    provider_name = str(provider or "").strip().casefold()
    snapshots = load_provider_observation_snapshots(
        database_url, provider=provider_name, limit=snapshot_limit
    )
    observations = []
    for snapshot in snapshots:
        payload = snapshot.get("payload")
        if not isinstance(payload, dict):
            continue
        if payload.get("provider") != provider_name:
            continue
        rows = payload.get("observations")
        if isinstance(rows, list):
            observations.extend(row for row in rows if isinstance(row, dict))

    source = extract_provider_entities_from_observations(provider_name, observations)
    catalogue = canonical_catalogue or load_canonical_crosswalk_catalogue(database_url)
    canonical_leagues = list(catalogue.get("leagues", []))
    canonical_seasons = list(catalogue.get("seasons", []))
    canonical_teams = list(catalogue.get("teams", []))

    league_candidates = build_entity_crosswalk_candidates(
        provider_name, "league", source["leagues"], canonical_leagues
    )
    existing_links = _load_provider_links_by_type(
        database_url, provider=provider_name
    )
    existing_league_links = existing_links.get("league", {})
    existing_season_links = existing_links.get("season", {})
    existing_team_links = existing_links.get("team", {})
    season_candidates = build_entity_crosswalk_candidates(
        provider_name, "season", source["seasons"], canonical_seasons,
        canonical_parent_ids=existing_league_links,
    )
    team_candidates = build_entity_crosswalk_candidates(
        provider_name, "team", source["teams"], canonical_teams
    )

    for candidates, existing in (
        (league_candidates, existing_league_links),
        (season_candidates, existing_season_links),
        (team_candidates, existing_team_links),
    ):
        for candidate in candidates:
            linked_id = existing.get(str(candidate.get("provider_entity_id")))
            if linked_id:
                candidate["canonical_entity_id"] = linked_id
                candidate["status"] = "already_linked"
                candidate["reason"] = "An existing provider-to-canonical link is already stored."

    return {
        "provider": provider_name,
        "snapshot_count": len(snapshots),
        "observation_count": len(observations),
        "source_entity_counts": {
            "leagues": len(source["leagues"]),
            "seasons": len(source["seasons"]),
            "teams": len(source["teams"]),
        },
        # Retained for the cross-provider catalogue audit; this is read-only.
        "source_entities": source,
        "existing_link_counts": {
            "leagues": len(existing_league_links),
            "seasons": len(existing_season_links),
            "teams": len(existing_team_links),
        },
        "canonical_options": {
            "leagues": [str(row["league_id"]) for row in canonical_leagues if row.get("league_id")],
            "seasons": [str(row["season_id"]) for row in canonical_seasons if row.get("season_id")],
            "teams": [str(row["team_id"]) for row in canonical_teams if row.get("team_id")],
        },
        "candidates": {
            "leagues": league_candidates,
            "seasons": season_candidates,
            "teams": team_candidates,
        },
    }
