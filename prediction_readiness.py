"""Transparent prediction-readiness diagnostics for selected football matchups.

This module reports fixture identity, recent-history depth and evidence coverage.
It never fills missing values or changes prediction inputs/model weights.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

FIXTURE_FRESHNESS_THRESHOLD = timedelta(hours=24)


def _utc_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fixture_participants(fixture: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    home = away = None
    participants = fixture.get("participants") or []
    if isinstance(participants, dict):
        participants = participants.get("data") or []
    for participant in participants if isinstance(participants, list) else []:
        if not isinstance(participant, dict):
            continue
        location = str((participant.get("meta") or {}).get("location") or "").casefold()
        if location == "home":
            home = participant
        elif location == "away":
            away = participant
    return home, away


def _fixture_identity_status(
    fixture: dict[str, Any] | None,
    *,
    home_team_id: int,
    away_team_id: int,
    season_id: int | None,
    now: datetime,
) -> dict[str, Any]:
    if not fixture:
        return {
            "verified": False,
            "status": "not_found",
            "reason": "No exact upcoming fixture was returned for the selected home/away pairing.",
            "fixture_id": None,
            "kickoff_utc": None,
            "source_updated_at": None,
            "source_fetched_at": None,
            "source_age_seconds": None,
            "source_age_minutes": None,
            "source_freshness": "unknown",
            "freshness_note": "No successful detailed-fixture retrieval timestamp is attached.",
        }

    try:
        fixture_season = int(fixture.get("season_id"))
        exact_season = season_id is not None and fixture_season == int(season_id)
    except (TypeError, ValueError):
        exact_season = False
    home, away = _fixture_participants(fixture)
    try:
        exact_teams = (
            home is not None and away is not None
            and int(home.get("id")) == int(home_team_id)
            and int(away.get("id")) == int(away_team_id)
        )
    except (TypeError, ValueError):
        exact_teams = False

    state = fixture.get("state") or {}
    state_label = str(state.get("short_name") or state.get("name") or "").strip().casefold()
    scheduled = state_label in {"ns", "not started", "scheduled", "tbd"} or any(
        marker in state_label for marker in ("not started", "scheduled", "to be played")
    )
    kickoff = _utc_datetime(fixture.get("starting_at_timestamp"))
    if kickoff is None:
        kickoff = _utc_datetime(fixture.get("starting_at"))
    kickoff_valid = kickoff is not None and kickoff > now
    verified = bool(exact_season and exact_teams and scheduled and kickoff_valid)
    reasons = []
    if not exact_season:
        reasons.append("season identity is missing or does not match")
    if not exact_teams:
        reasons.append("home/away team IDs do not match the selected orientation")
    if not scheduled:
        reasons.append("fixture state is not confirmed as scheduled")
    if not kickoff_valid:
        reasons.append("kickoff is missing, invalid or not in the future")
    fetched_at = _utc_datetime(fixture.get("fixture_details_fetched_at"))
    timestamp_in_future = fetched_at is not None and fetched_at > now
    age_seconds = (
        (now - fetched_at).total_seconds()
        if fetched_at is not None and not timestamp_in_future else None
    )
    age_minutes = round(age_seconds / 60, 1) if age_seconds is not None else None
    if fetched_at is None:
        source_freshness = "unknown"
        freshness_note = "No successful detailed-fixture retrieval timestamp is attached; freshness cannot be measured."
    elif timestamp_in_future:
        source_freshness = "unknown"
        freshness_note = "The retrieval timestamp is later than the diagnostic clock; check system clock alignment."
    elif age_seconds < FIXTURE_FRESHNESS_THRESHOLD.total_seconds():
        source_freshness = "fresh"
        freshness_note = "Detailed fixture data was retrieved less than 24 hours ago."
    else:
        source_freshness = "stale"
        freshness_note = "Detailed fixture data was retrieved 24 hours ago or earlier; refresh it before relying on it."
    return {
        "verified": verified,
        "status": "verified" if verified else "identity_or_schedule_unverified",
        "reason": "Exact competition-season fixture identity and future kickoff verified." if verified else "; ".join(reasons),
        "fixture_id": fixture.get("id"),
        "kickoff_utc": kickoff.isoformat() if kickoff else None,
        "source_updated_at": fixture.get("updated_at") or fixture.get("updatedAt"),
        "source_fetched_at": fetched_at.isoformat() if fetched_at else None,
        "source_age_seconds": round(age_seconds, 1) if age_seconds is not None else None,
        "source_age_minutes": age_minutes,
        "source_freshness": source_freshness,
        "freshness_note": freshness_note,
    }


def _team_readiness(profile: dict[str, Any]) -> dict[str, Any]:
    matches = profile.get("matches") or []
    quality = profile.get("data_quality") or {}
    count = int(quality.get("matches_returned", len(matches)) or 0)
    recent = matches[:10]
    stats_count = sum(bool(row.get("statistics")) for row in recent if isinstance(row, dict))
    strength_count = sum(
        row.get("opponent_strength") is not None
        for row in recent if isinstance(row, dict)
    )
    tactical = profile.get("tactical_summary") or {}
    tactical_components = {
        key: tactical.get(key) is not None
        for key in ("playing_style", "defensive_structure", "attacking_approach")
    }
    availability = profile.get("availability") or {}
    availability_known = bool(
        availability.get("injury_data_available")
        or profile.get("player_availability") is not None
    )
    lineup = profile.get("lineups") or {}
    lineup_known = bool(lineup.get("lineups_available"))
    return {
        "team": profile.get("name"),
        "completed_matches_available": count,
        "history_minimum": 5,
        "history_target": 10,
        "history_status": "target_met" if count >= 10 else "minimum_met" if count >= 5 else "insufficient",
        "prediction_allowed_by_history": count >= 5,
        "matches_with_statistics": stats_count,
        "matches_with_opponent_strength": strength_count,
        "tactical_components_available": tactical_components,
        "player_availability_evidence": "available" if availability_known else "unknown",
        "confirmed_lineup_evidence": "available" if lineup_known else "unknown",
    }


def build_prediction_readiness(
    home_profile: dict[str, Any],
    away_profile: dict[str, Any],
    *,
    selected_fixture: dict[str, Any] | None,
    home_team_id: int,
    away_team_id: int,
    season_id: int | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a diagnostic readiness report without changing model inputs."""
    current = now or datetime.now(timezone.utc)
    current = current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current.astimezone(timezone.utc)
    fixture = _fixture_identity_status(
        selected_fixture,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        season_id=season_id,
        now=current,
    )
    teams = {
        "home": _team_readiness(home_profile),
        "away": _team_readiness(away_profile),
    }
    history_ok = all(row["completed_matches_available"] >= 5 for row in teams.values())
    history_target_met = all(row["completed_matches_available"] >= 10 for row in teams.values())
    if not history_ok:
        overall = "insufficient_history"
    elif not fixture["verified"]:
        overall = "fixture_unverified"
    elif history_target_met:
        overall = "ready"
    else:
        overall = "limited_history"

    return {
        "overall_status": overall,
        "prediction_minimum_history_met": history_ok,
        "ten_match_history_target_met": history_target_met,
        "history_policy": {
            "minimum_matches_per_team": 5,
            "preferred_target_per_team": 10,
            "target_is_advisory": True,
            "note": "Prediction history eligibility requires five completed, score-valid matches per team. Five to nine matches are allowed with a limited-sample label; ten remains the preferred target.",
        },
        "prediction_allowed_by_history": history_ok,
        "fixture": fixture,
        "teams": teams,
        "model_impact": "Diagnostic only. This report does not change prediction inputs, model weights, recency weighting or TVD rules.",
    }
