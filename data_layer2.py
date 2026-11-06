
"""Layer 2: Automatic football data collection and team profiling."""

from __future__ import annotations

from typing import Any

from api_football import APIFootballClient
from availability import summarize_injuries, summarize_lineups
from form_analyzer import analyze_form, venue_rating
from tactical_indicators import analyze_tactics


def _statistics_map(rows: list[dict], team_id: int) -> dict[str, Any]:
    """Extract statistics belonging to the selected team."""
    for row in rows or []:
        team = row.get("team") or {}

        if team.get("id") == team_id:
            return {
                item.get("type"): item.get("value")
                for item in row.get("statistics", [])
                if item.get("type")
            }

    return {}


def _standings_strength_map(standings: list[dict]) -> dict[int, float]:
    """Convert API-Football standings into opponent-strength ratings."""
    points_by_team = {}

    for competition in standings or []:
        league = competition.get("league") or {}

        for group in league.get("standings") or []:
            for row in group:
                team_id = (row.get("team") or {}).get("id")
                points = row.get("points")

                if team_id is not None and points is not None:
                    points_by_team[int(team_id)] = float(points)

    if not points_by_team:
        return {}

    leader_points = max(points_by_team.values())

    if leader_points <= 0:
        return {}

    return {
        team_id: round(points / leader_points * 100, 1)
        for team_id, points in points_by_team.items()
    }


def collect_team_profile(
    client: APIFootballClient,
    team: dict,
    league_id: int,
    season: int,
    standings: list[dict],
    include_match_statistics: bool = True,
) -> dict[str, Any]:
    """Collect recent matches and build a validated team profile."""

    team_id = int(team["id"])
    strength_map = _standings_strength_map(standings)

    # Retrieve up to ten recent fixtures.
    fixtures = client.last_fixtures(
        team_id,
        season,
        count=10,
    )

    matches = []

    for fixture in fixtures or []:
        fixture_info = fixture.get("fixture") or {}
        teams = fixture.get("teams") or {}
        goals = fixture.get("goals") or {}

        home = teams.get("home") or {}
        away = teams.get("away") or {}

        is_home = home.get("id") == team_id
        opponent = away if is_home else home

        team_goals = goals.get("home") if is_home else goals.get("away")
        opponent_goals = goals.get("away") if is_home else goals.get("home")

        # Do not invent scores for incomplete fixtures.
        if team_goals is None or opponent_goals is None:
            continue

        opponent_id = opponent.get("id")

        match = {
            "fixture_id": fixture_info.get("id"),
            "date": fixture_info.get("date"),
            "venue": "home" if is_home else "away",
            "opponent_id": opponent_id,
            "opponent_name": opponent.get("name"),
            "goals_for": int(team_goals),
            "goals_against": int(opponent_goals),
            "opponent_strength": (
                strength_map.get(int(opponent_id))
                if opponent_id is not None
                else None
            ),
            "statistics": {},
        }

        # Match statistics are optional and depend on API coverage.
        if include_match_statistics and fixture_info.get("id"):
            try:
                stat_rows = client.fixture_statistics(
                    int(fixture_info["id"])
                )
                match["statistics"] = _statistics_map(
                    stat_rows,
                    team_id,
                )
            except Exception:
                match["statistics"] = {}

        matches.append(match)

    # Newest match first.
    matches.sort(
        key=lambda item: item.get("date") or "",
        reverse=True,
    )
    matches = matches[:10]

    form = analyze_form(matches)
    tactics = analyze_tactics(matches)

    # Optional upcoming fixture information.
    upcoming_id = None
    injury_rows = []
    lineup_rows = []

    try:
        upcoming = client.next_fixture(team_id, count=1)

        if upcoming:
            upcoming_id = (
                (upcoming[0].get("fixture") or {}).get("id")
            )

        if upcoming_id:
            try:
                injury_rows = client.injuries(int(upcoming_id))
            except Exception:
                injury_rows = []

            try:
                lineup_rows = client.fixture_lineups(
                    int(upcoming_id)
                )
            except Exception:
                lineup_rows = []

    except Exception:
        pass

    availability = summarize_injuries(injury_rows or [])
    lineups = summarize_lineups(lineup_rows or [])

    profile = {
        "id": team_id,
        "name": team.get("name", f"Team {team_id}"),
        "logo": team.get("logo"),
        "matches": matches,

        "home_rating": venue_rating(matches, "home"),
        "away_rating": venue_rating(matches, "away"),

        "player_availability": availability.get(
            "player_availability"
        ),

        "playing_style": tactics.get("playing_style"),
        "defensive_structure": tactics.get(
            "defensive_structure"
        ),
        "attacking_approach": tactics.get(
            "attacking_approach"
        ),

        # Compatibility score is supplied by TVD or other
        # evidence-based tactical analysis, not fabricated here.
        "tactical_compatibility": None,

        "form_summary": form,
        "tactical_summary": tactics,
        "availability": availability,
        "lineups": lineups,
        "upcoming_fixture_id": upcoming_id,

        "data_quality": {
            "matches_returned": len(matches),
            "goals_complete": len(matches) >= 5,
            "opponent_strength_matches": sum(
                item.get("opponent_strength") is not None
                for item in matches
            ),
            "statistics_matches": sum(
                bool(item.get("statistics"))
                for item in matches
            ),
        },
    }

    return profile
