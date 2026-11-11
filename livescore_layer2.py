"""Fail-closed LiveScoreFootball result fallback for missing Sportmonks scores.

LiveScoreFootball is a stored snapshot service. Its data is eligible only after
both global metadata freshness and an exact, season-specific competition
crosswalk pass. It can fill only missing full-time scores on an already-known,
completed Sportmonks fixture; it never replaces a valid Sportmonks score.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping

from canonical_data import MatchNormalizationError, canonicalize_livescore_event, match_identity
from competition_crosswalk import build_competition_crosswalk, verified_livescore_slug
from provider_health import assess_livescore_fixture_freshness, assess_livescore_metadata
from sportmonks_canonical import canonicalize_sportmonks_fixture
from sportmonks_layer2 import _CORE_STATISTICS, _provider_id, _state


def _utc_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _has_explicit_current_score_rows(fixture: Mapping[str, Any]) -> bool:
    rows = fixture.get("scores")
    if not isinstance(rows, list):
        return False
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        score_type = row.get("type") if isinstance(row.get("type"), Mapping) else {}
        label = row.get("description") or score_type.get("name") or ""
        if str(label).strip().casefold() == "current":
            return True
    return False


def _fixture_participants(fixture: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]] | None:
    participants = fixture.get("participants")
    if not isinstance(participants, list):
        return None
    by_side = {
        str((row.get("meta") or {}).get("location") or "").casefold(): row
        for row in participants
        if isinstance(row, Mapping)
    }
    home, away = by_side.get("home"), by_side.get("away")
    if not isinstance(home, dict) or not isinstance(away, dict):
        return None
    if _provider_id(home.get("id")) is None or _provider_id(away.get("id")) is None:
        return None
    if not home.get("name") or not away.get("name"):
        return None
    return home, away


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
