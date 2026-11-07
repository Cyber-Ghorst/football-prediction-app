"""Fetch and normalize API-Football v3 histories into the Layer 2 profile."""
from __future__ import annotations

from typing import Any
from api_football import APIFootballClient
from tactical_indicators import analyze_tactics
from form_analyzer import analyze_form, venue_rating
from availability import summarize_injuries, summarize_lineups


def _stat_map(rows: list[dict], team_id: int) -> dict[str, Any]:
    for row in rows:
        if (row.get("team") or {}).get("id") == team_id:
            return {x.get("type"): x.get("value") for x in row.get("statistics", []) if x.get("type")}
    return {}


def _standings_rank_map(rows: list[dict]) -> dict[int, float]:
    """Convert API-Football's nested standings response to team-id -> normalized strength."""
    ranks: dict[int, float] = {}
    for league_row in rows or []:
        league = league_row.get("league") or {}
        for group in league.get("standings") or []:
            for entry in group:
                team_id = (entry.get("team") or {}).get("id")
                rank = entry.get("rank")
                if team_id is not None and rank is not None:
                    ranks[int(team_id)] = float(rank)
    if not ranks:
        return {}
    # Higher score means stronger table position; ranks are comparable only
    # within the single competition/season passed to this collector.
    maximum = max(ranks.values())
    return {team_id: (maximum - rank + 1) / maximum * 100 for team_id, rank in ranks.items()}


def collect_team_profile(client: APIFootballClient, team: dict, league_id: int, season: int,
                         standings: list[dict] | dict[int, float], include_match_statistics: bool = True) -> dict[str, Any]:
    team_id = int(team["id"])
    strength_map = standings if isinstance(standings, dict) else _standings_rank_map(standings)
    fixtures = client.last_fixtures(team_id, season, last=10, league_id=league_id)
    matches = []
    for fixture in fixtures:
        fixture_info = fixture.get("fixture") or {}
        teams = fixture.get("teams") or {}
        goals = fixture.get("goals") or {}
        home = teams.get("home") or {}
        away = teams.get("away") or {}
        if home.get("id") == team_id:
            is_home, opponent = True, away
        elif away.get("id") == team_id:
            is_home, opponent = False, home
        else:
            continue
        team_goals = goals.get("home") if is_home else goals.get("away")
        opponent_goals = goals.get("away") if is_home else goals.get("home")
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
            "opponent_strength": strength_map.get(int(opponent_id)) if opponent_id is not None else None,
            "statistics": {},
        }
        if include_match_statistics and fixture_info.get("id"):
            stat_rows = client.fixture_statistics(int(fixture_info["id"]))
            match["statistics"] = _stat_map(stat_rows, team_id)
        matches.append(match)

    matches.sort(key=lambda x: x.get("date") or "", reverse=True)
    form = analyze_form(matches)
    tactics = analyze_tactics(matches)
    try:
        injury_rows = client.injuries(team_id, season)
    except Exception:
        injury_rows = []
    availability = summarize_injuries(injury_rows)
    try:
        upcoming = client.next_fixture(team_id, season, league_id=league_id)
        upcoming_id = ((upcoming or {}).get("fixture") or {}).get("id")
        lineup_rows = client.fixture_lineups(int(upcoming_id)) if upcoming_id else []
    except Exception:
        upcoming_id, lineup_rows = None, []
    lineups = summarize_lineups(lineup_rows)
    recent = matches[:10]
    return {
        "id": team_id,
        "name": team.get("name", f"Team {team_id}"),
        "logo": team.get("logo"),
        "matches": recent,
        "home_rating": venue_rating(recent, "home"),
        "away_rating": venue_rating(recent, "away"),
        "player_availability": availability["player_availability"],
        "playing_style": tactics["playing_style"],
        "defensive_structure": tactics["defensive_structure"],
        "attacking_approach": tactics["attacking_approach"],
        "tactical_compatibility": None,
        "form_summary": form,
        "tactical_summary": tactics,
        "availability": availability,
        "lineups": lineups,
        "upcoming_fixture_id": upcoming_id,
        "data_quality": {
            "matches_returned": len(recent),
            "goals_complete": len(recent) >= 5,
            "opponent_strength_matches": sum(m.get("opponent_strength") is not None for m in recent),
            "statistics_matches": sum(bool(m.get("statistics")) for m in recent),
        },
    }
