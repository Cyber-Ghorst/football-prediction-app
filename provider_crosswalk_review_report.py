"""Build read-only provider entity crosswalk review reports from archived fixtures."""
from __future__ import annotations

from typing import Any

from football_repository import (
    get_repository_leagues,
    get_repository_seasons,
    get_repository_teams,
)
from provider_data_storage import load_provider_observation_snapshots
from provider_entity_crosswalk import (
    build_entity_crosswalk_candidates,
    extract_provider_entities_from_observations,
    load_provider_entity_links,
)


def build_provider_crosswalk_review_report(
    database_url: str,
    *,
    provider: str,
    snapshot_limit: int = 100,
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
    canonical_leagues = get_repository_leagues(database_url)
    canonical_seasons = get_repository_seasons(database_url)
    canonical_teams = get_repository_teams(database_url)

    league_candidates = build_entity_crosswalk_candidates(
        provider_name, "league", source["leagues"], canonical_leagues
    )
    existing_league_links = load_provider_entity_links(
        database_url, provider=provider_name, entity_type="league"
    )
    season_candidates = build_entity_crosswalk_candidates(
        provider_name, "season", source["seasons"], canonical_seasons,
        canonical_parent_ids=existing_league_links,
    )
    team_candidates = build_entity_crosswalk_candidates(
        provider_name, "team", source["teams"], canonical_teams
    )

    return {
        "provider": provider_name,
        "snapshot_count": len(snapshots),
        "observation_count": len(observations),
        "source_entity_counts": {
            "leagues": len(source["leagues"]),
            "seasons": len(source["seasons"]),
            "teams": len(source["teams"]),
        },
        "existing_link_counts": {
            "leagues": len(existing_league_links),
            "seasons": len(load_provider_entity_links(
                database_url, provider=provider_name, entity_type="season"
            )),
            "teams": len(load_provider_entity_links(
                database_url, provider=provider_name, entity_type="team"
            )),
        },
        "candidates": {
            "leagues": league_candidates,
            "seasons": season_candidates,
            "teams": team_candidates,
        },
    }
