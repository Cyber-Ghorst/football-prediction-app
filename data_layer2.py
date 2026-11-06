"""Fetch and normalize team histories from API-Football."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from api_football import APIFootballClient
from strength_analyzer import attach_opponent_strength
from tactical_indicators import analyze_tactics
from form_analyzer import analyze_form, venue_rating
from availability import summarize_injuries, summarize_lineups


def _stat_map(rows: list[dict], team_id: int) -> dict[str, Any]:
    for row in rows:
        if (row.get("team") or {}).get("id") == team_id:
            return {x.get("type"): x.get("value") for x in row.get("statistics", []) if x.get("type")}
    return {}


def collect_team_profile(client: APIFootballClient, team: dict, league_id: int, season: int,
                         standings: dict[int, float], include_match_statistics: bool = True) -> dict[str, Any]:
    team_id = int(team["id"])
    fixtures = client.last_fixtures(team_id, season, last=10)
    matches = []
    for fixture in fixtures:
        fixture_info = fixture.get("fixture") or {}
        teams = fixture.get("teams") or {}
        goals = fixture.get("goals") or {}
        home = teams.get("home") or {}
        away = teams.get("away") or {}
        is_home = home.get("id") == team_id
        opponent = away if is_home else home
        team_goals = goals.get("home") if is_home else goals.get("away")
        opponent_goals = goals.get("away") if is_home else goals.get("home")
        if team_goals is None or opponent_goals is None:
            continue
        match = {
            "fixture_id": fixture_info.get("id"),
            "date": fixture_info.get("date"),
            "venue": "home" if is_home else "away",
            "opponent_id": opponent.get("id"),
            "opponent_name": opponent.get("name"),
            "goals_for": int(team_goals),
            "goals_against": int(opponent_goals),
            "opponent_strength": standings.get(int(opponent["id"])) if opponent.get("id") is not None else None,
            "statistics": {},
        }
        if include_match_statistics and fixture_info.get("id"):
            stat_rows = client.fixture_statistics(int(fixture_info["id"]))
            match["statistics"] = _stat_map(stat_rows, team_id)
        matches.append(match)

    # API returns latest first; sort defensively by ISO fixture date descending.
    matches.sort(key=lambda x: x.get("date") or "", reverse=True)
    form = analyze_form(matches)
    tactics = analyze_tactics(matches)
    try:
        injury_rows = client.injuries(team_id, season)
    except Exception:
        injury_rows = []
    availability = summarize_injuries(injury_rows)
    try:
        upcoming = client.next_fixture(team_id, season)
        upcoming_id = (upcoming[0].get("fixture") or {}).get("id") if upcoming else None
        lineup_rows = client.fixture_lineups(int(upcoming_id)) if upcoming_id else []
    except Exception:
        upcoming_id, lineup_rows = None, []
    lineups = summarize_lineups(lineup_rows)
    profile = {
        "id": team_id,
        "name": team.get("name", f"Team {team_id}"),
        "logo": team.get("logo"),
        "matches": matches[:10],
        "home_rating": venue_rating(matches, "home"),
        "away_rating": venue_rating(matches, "away"),
        "player_availability": availability["player_availability"],
        "playing_style": tactics["playing_style"],
        "defensive_structure": tactics["defensive_structure"],
        "attacking_approach": tactics["attacking_approach"],
        # Pairwise TVD or manual evidence can supply this later; do not invent it.
        "tactical_compatibility": None,
        "form_summary": form,
        "tactical_summary": tactics,
        "availability": availability,
        "lineups": lineups,
        "upcoming_fixture_id": upcoming_id,
        "data_quality": {
            "matches_returned": len(matches[:10]),
            "goals_complete": len(matches[:10]) >= 5,
            "opponent_strength_matches": sum(m.get("opponent_strength") is not None for m in matches[:10]),
            "statistics_matches": sum(bool(m.get("statistics")) for m in matches[:10]),
        },
    }
    return profile
