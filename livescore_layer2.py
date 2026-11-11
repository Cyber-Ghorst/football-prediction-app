"""Fail-closed LiveScoreFootball result fallback for missing Sportmonks scores.

LiveScoreFootball is a stored snapshot service. Its data is eligible only after
both global metadata freshness and an exact, season-specific competition
crosswalk pass. It can fill only missing full-time scores on an already-known,
completed Sportmonks fixture; it never replaces a valid Sportmonks score.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping


def collect_livescore_verified_result_fallback(
    client: Any,
    *,
    source_competition: Mapping[str, Any],
    sportmonks_fixtures: list[Mapping[str, Any]],
    selected_team_ids: set[int],
    competition_key: str,
    season: int,
    season_id: int,
    now: datetime | None = None,
    max_age_seconds: int = 24 * 60 * 60,
    max_unique_date_requests: int = 10,
) -> dict[str, Any]:
    """Deprecated: LiveScoreFootball is not a multi-league result provider."""
    return {
        "status": "disabled",
        "reason": (
            "The current worldcup26.ir fork is historical FIFA World Cup 2026 data only. "
            "The generic fixture endpoint returned HTTP 400; no current-result fallback is permitted."
        ),
        "verified_matches": [],
    }


def apply_livescore_verified_result_fallback_to_profiles(
    profiles: list[dict[str, Any]],
    verified_matches: list[Mapping[str, Any]],
    *,
    history_limit: int = 10,
) -> dict[str, Any]:
    """Deprecated no-op: never mutate Layer 2 profiles from this provider."""
    return {
        "status": "disabled",
        "profiles_updated": 0,
        "matches_added": 0,
        "duplicates_skipped": 0,
        "reason": "LiveScoreFootball is not an active Layer 2 result source.",
    }
