"""Provider-neutral Layer 2 team-season profiles from canonical repository rows.

This module deliberately consumes canonical IDs and normalized repository data;
it does not parse or infer provider IDs, crosswalks, injuries, or lineups.
Unavailable evidence remains None/empty rather than being imputed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from form_analyzer import analyze_form, venue_rating
from tactical_indicators import analyze_tactics


_COMPLETED = {"finished", "complete", "completed", "ft", "full time", "5"}


def _utc_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _non_negative_score(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if str(value).strip() not in {str(number), f"{number}.0"} or number < 0:
        return None
    return number


def build_provider_neutral_team_profile(
    team: dict[str, Any],
    fixtures: list[dict[str, Any]],
    *,
    season_id: str,
    statistics: list[dict[str, Any]] | None = None,
    opponent_strength: dict[str, float] | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Build the existing Layer 2 profile contract from canonical repository data.

    Fixture rows must already have approved canonical fixture/team/season IDs.
    Statistics must be normalized rows keyed by canonical fixture_id/team_id.
    """
    team_id = str(team.get("team_id") or team.get("id") or "").strip()
    if not team_id:
        raise ValueError("A canonical team_id is required.")
    canonical_season_id = str(season_id or "").strip()
    if not canonical_season_id:
        raise ValueError("A canonical season_id is required.")
    safe_limit = max(1, min(int(limit), 10))

    stats_by_fixture: dict[str, dict[str, Any]] = {}
    stats_provenance: dict[str, list[dict[str, Any]]] = {}
    for row in statistics or []:
        if not isinstance(row, dict):
            continue
        fixture_id = str(row.get("fixture_id") or "").strip()
        statistic_team_id = str(row.get("team_id") or "").strip()
        statistic_type = str(row.get("statistic_type") or "").strip()
        value = row.get("statistic_value")
        if not fixture_id or statistic_team_id != team_id or not statistic_type or value is None:
            continue
        stats_by_fixture.setdefault(fixture_id, {})[statistic_type] = value
        stats_provenance.setdefault(fixture_id, []).append({
            "provider": row.get("provider"),
            "provider_statistic_id": row.get("provider_statistic_id"),
            "statistic_type": statistic_type,
        })

    matches: list[dict[str, Any]] = []
    excluded = {"wrong_season": 0, "not_completed": 0, "invalid_identity": 0,
                "invalid_kickoff": 0, "invalid_score": 0}
    for fixture in fixtures or []:
        if str(fixture.get("season_id") or "") != canonical_season_id:
            excluded["wrong_season"] += 1
            continue
        status = str(fixture.get("status") or "").strip().casefold()
        if status not in _COMPLETED:
            excluded["not_completed"] += 1
            continue
        home_id = str(fixture.get("home_team_id") or "").strip()
        away_id = str(fixture.get("away_team_id") or "").strip()
        if not home_id or not away_id or home_id == away_id or team_id not in {home_id, away_id}:
            excluded["invalid_identity"] += 1
            continue
        kickoff = _utc_datetime(fixture.get("starting_at"))
        if kickoff is None or kickoff >= datetime.now(timezone.utc):
            excluded["invalid_kickoff"] += 1
            continue
        home_goals = _non_negative_score(fixture.get("home_goals"))
        away_goals = _non_negative_score(fixture.get("away_goals"))
        if home_goals is None or away_goals is None:
            excluded["invalid_score"] += 1
            continue
        is_home = team_id == home_id
        opponent_id = away_id if is_home else home_id
        match = {
            "fixture_id": str(fixture.get("fixture_id") or ""),
            "date": kickoff.isoformat(),
            "venue": "home" if is_home else "away",
            "opponent_id": opponent_id,
            "opponent_name": fixture.get("away_team" if is_home else "home_team"),
            "goals_for": home_goals if is_home else away_goals,
            "goals_against": away_goals if is_home else home_goals,
            "opponent_strength": (opponent_strength or {}).get(opponent_id),
            "statistics": stats_by_fixture.get(str(fixture.get("fixture_id") or ""), {}),
            "statistics_provenance": stats_provenance.get(str(fixture.get("fixture_id") or ""), []),
            "source_provider": fixture.get("source_provider"),
        }
        matches.append(match)

    matches.sort(key=lambda row: row["date"], reverse=True)
    recent = matches[:safe_limit]
    form = analyze_form(recent)
    tactics = analyze_tactics(recent)
    return {
        "id": team_id,
        "name": team.get("name") or f"Team {team_id}",
        "logo": team.get("logo_url") or team.get("logo"),
        "matches": recent,
        "home_rating": venue_rating(recent, "home"),
        "away_rating": venue_rating(recent, "away"),
        "player_availability": None,
        "playing_style": tactics.get("playing_style"),
        "defensive_structure": tactics.get("defensive_structure"),
        "attacking_approach": tactics.get("attacking_approach"),
        "tactical_compatibility": None,
        "form_summary": form,
        "tactical_summary": tactics,
        "availability": {
            "injury_data_available": False, "reported_injuries": None,
            "injuries": [], "player_availability": None,
            "note": "No verified availability feed supplied; player availability remains unknown.",
        },
        "lineups": {
            "lineups_available": False, "teams": [],
            "note": "No verified fixture-specific lineup supplied.",
        },
        "upcoming_fixture_id": None,
        "data_quality": {
            "provider": "canonical_repository",
            "season_id": canonical_season_id,
            "matches_scanned": len(fixtures or []),
            "matches_returned": len(recent),
            "goals_complete": len(recent) >= 5,
            "opponent_strength_matches": sum(m.get("opponent_strength") is not None for m in recent),
            "statistics_matches": sum(bool(m.get("statistics")) for m in recent),
            "history_shortfall": max(0, 10 - len(recent)),
            "excluded": excluded,
        },
    }
