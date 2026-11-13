"""Provider-neutral Layer 2 team-season profiles from canonical repository rows.

This module consumes canonical IDs and normalized repository data. It does not
infer provider IDs or crosswalks. Missing or conflicting evidence stays missing.
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


def _same_statistic_value(left: Any, right: Any) -> bool:
    try:
        return float(str(left).replace("%", "").replace(",", "")) == float(
            str(right).replace("%", "").replace(",", "")
        )
    except (TypeError, ValueError):
        return left == right


def build_provider_neutral_team_profile(
    team: dict[str, Any],
    fixtures: list[dict[str, Any]],
    *,
    season_id: str,
    statistics: list[dict[str, Any]] | None = None,
    opponent_strength: dict[str, float] | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Build the existing Layer 2 profile contract from canonical repository data."""
    team_id = str(team.get("team_id") or team.get("id") or "").strip()
    if not team_id:
        raise ValueError("A canonical team_id is required.")
    canonical_season_id = str(season_id or "").strip()
    if not canonical_season_id:
        raise ValueError("A canonical season_id is required.")
    safe_limit = max(1, min(int(limit), 10))

    stat_candidates: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in statistics or []:
        if not isinstance(row, dict):
            continue
        fixture_id = str(row.get("fixture_id") or "").strip()
        statistic_team_id = str(row.get("team_id") or "").strip()
        statistic_type = str(row.get("statistic_type") or "").strip()
        value = row.get("statistic_value")
        if fixture_id and statistic_team_id == team_id and statistic_type and value is not None:
            stat_candidates.setdefault((fixture_id, statistic_type), []).append(row)

    stats_by_fixture: dict[str, dict[str, Any]] = {}
    stats_provenance: dict[str, list[dict[str, Any]]] = {}
    statistic_conflicts: dict[str, list[str]] = {}
    for (fixture_id, statistic_type), candidates in stat_candidates.items():
        values = [row.get("statistic_value") for row in candidates]
        provenance = [{
            "provider": row.get("provider") or row.get("source_provider"),
            "provider_statistic_id": row.get("provider_statistic_id"),
            "statistic_type": statistic_type,
        } for row in candidates]
        if any(not _same_statistic_value(values[0], value) for value in values[1:]):
            statistic_conflicts.setdefault(fixture_id, []).append(statistic_type)
            continue
        stats_by_fixture.setdefault(fixture_id, {})[statistic_type] = values[0]
        stats_provenance.setdefault(fixture_id, []).extend(provenance)

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
        fixture_id = str(fixture.get("fixture_id") or "").strip()
        home_id = str(fixture.get("home_team_id") or "").strip()
        away_id = str(fixture.get("away_team_id") or "").strip()
        if not fixture_id or not home_id or not away_id or home_id == away_id or team_id not in {home_id, away_id}:
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
        matches.append({
            "fixture_id": fixture_id,
            "date": kickoff.isoformat(),
            "venue": "home" if is_home else "away",
            "opponent_id": opponent_id,
            "opponent_name": fixture.get("away_team" if is_home else "home_team"),
            "goals_for": home_goals if is_home else away_goals,
            "goals_against": away_goals if is_home else home_goals,
            "opponent_strength": (opponent_strength or {}).get(opponent_id),
            "statistics": stats_by_fixture.get(fixture_id, {}),
            "statistics_provenance": stats_provenance.get(fixture_id, []),
            "statistics_conflicts": statistic_conflicts.get(fixture_id, []),
            "source_provider": fixture.get("source_provider"),
        })

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
            "statistics_conflict_count": sum(len(m.get("statistics_conflicts") or []) for m in recent),
            "history_shortfall": max(0, 10 - len(recent)),
            "excluded": excluded,
        },
    }


def build_repository_team_profiles(
    snapshot: dict[str, Any],
    team_ids: list[str] | tuple[str, ...],
    season_id: str,
    *,
    opponent_strength: dict[str, float] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build profiles for selected canonical teams from one repository snapshot."""
    canonical_season_id = str(season_id)
    if str(snapshot.get("season_id") or "") != canonical_season_id:
        raise ValueError("Repository snapshot season does not match the requested canonical season.")
    requested_ids = list(dict.fromkeys(str(value) for value in team_ids))
    team_rows = {
        str(row.get("team_id")): row
        for row in snapshot.get("teams", [])
        if str(row.get("team_id")) in requested_ids
    }
    missing = [team_id for team_id in requested_ids if team_id not in team_rows]
    if missing:
        raise ValueError("Canonical team(s) missing from season snapshot: " + ", ".join(missing))
    fixtures = snapshot.get("fixtures") or []
    statistics = snapshot.get("statistics") or []
    return {
        team_id: build_provider_neutral_team_profile(
            team_rows[team_id], fixtures, season_id=canonical_season_id,
            statistics=statistics, opponent_strength=opponent_strength,
        )
        for team_id in requested_ids
    }


def load_repository_team_profiles(
    database_url: str,
    team_ids: list[str] | tuple[str, ...],
    season_id: str,
    *,
    snapshot: dict[str, Any] | None = None,
    opponent_strength: dict[str, float] | None = None,
) -> dict[str, dict[str, Any]]:
    """Load one CockroachDB season snapshot and build selected team profiles."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    if snapshot is None:
        from football_repository import get_repository_season_snapshot
        snapshot = get_repository_season_snapshot(
            database_url, str(season_id), fixture_limit=2000
        )
        snapshot = {**snapshot, "season_id": str(season_id)}
    return build_repository_team_profiles(
        snapshot, team_ids, str(season_id), opponent_strength=opponent_strength
    )
