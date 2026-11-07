"""Sportmonks v3 -> existing Layer 2 team-profile contract.

Only exact season/team IDs are used. Missing fields remain None; no synthetic
scores, opponent mappings, or availability ratings are created.
"""
from __future__ import annotations

from typing import Any

from form_analyzer import analyze_form, venue_rating
from tactical_indicators import analyze_tactics


_COMPLETED = {"finished", "ft", "aet", "penalties", "after extra time", "after penalties"}
_STAT_ALIASES = {
    "ball possession": "Ball Possession",
    "pass accuracy": "Passes %",
    "passes %": "Passes %",
    "shots on goal": "Shots on Goal",
    "total shots": "Total Shots",
    "shots on target": "Shots on Target",
    "shots off target": "Shots off Target",
    "tackles": "Tackles",
    "interceptions": "Interceptions",
    "blocked shots": "Blocked Shots",
    "corners": "Corner Kicks",
}


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if isinstance(value, dict):
        data = value.get("data")
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            return [data]
    return []


def _participants(fixture: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    home = away = None
    for participant in _rows(fixture.get("participants")):
        location = str((participant.get("meta") or {}).get("location") or "").casefold()
        if location == "home":
            home = participant
        elif location == "away":
            away = participant
    return home, away


def _state(fixture: dict[str, Any]) -> str:
    state = fixture.get("state") or {}
    label = str(state.get("short_name") or state.get("name") or "").strip().casefold()
    if label in _COMPLETED or any(x in label for x in ("finished", "full time", "after extra", "after penalties")):
        return "finished"
    if any(x in label for x in ("live", "in play", "half time", "1st half", "2nd half", "extra time", "penalty")):
        return "live"
    if any(x in label for x in ("not started", "scheduled", "to be played")):
        return "scheduled"
    return "unknown"


def _scores(fixture: dict[str, Any], home_id: int, away_id: int) -> tuple[int | None, int | None]:
    rows = _rows(fixture.get("scores"))
    current = [r for r in rows if str(r.get("description") or "").casefold() == "current"]
    candidates = current or rows
    if not candidates:
        return None, None
    values: dict[int, int] = {}
    for row in candidates:
        participant_id = row.get("participant_id")
        score = row.get("score")
        goals = score.get("goals") if isinstance(score, dict) else None
        if participant_id is not None and goals is not None:
            try:
                values[int(participant_id)] = int(goals)
            except (TypeError, ValueError):
                continue
    return values.get(home_id), values.get(away_id)


def _team_statistics(fixture: dict[str, Any], team_id: int) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for row in _rows(fixture.get("statistics")):
        if row.get("participant_id") is None:
            continue
        try:
            if int(row["participant_id"]) != team_id:
                continue
        except (TypeError, ValueError):
            continue
        stat_type = row.get("type") or {}
        name = str(stat_type.get("name") or "").strip().casefold()
        key = _STAT_ALIASES.get(name)
        data = row.get("data")
        value = data.get("value") if isinstance(data, dict) else data
        if key and value is not None:
            result[key] = value
    return result


def standings_strength(rows: list[dict[str, Any]]) -> dict[int, float]:
    ranks: dict[int, float] = {}
    for row in rows:
        participant_id = row.get("participant_id")
        rank = row.get("position") or row.get("rank")
        if participant_id is None or rank is None:
            continue
        try:
            ranks[int(participant_id)] = float(rank)
        except (TypeError, ValueError):
            continue
    if not ranks:
        return {}
    maximum = max(ranks.values())
    return {team_id: (maximum - rank + 1) / maximum * 100 for team_id, rank in ranks.items()}


def collect_sportmonks_team_profile(
    team: dict[str, Any],
    season_id: int,
    fixtures: list[dict[str, Any]],
    standings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a profile from one validated Sportmonks season collection."""
    team_id = int(team["id"])
    strength_map = standings_strength(standings)
    matches: list[dict[str, Any]] = []

    for fixture in fixtures:
        home, away = _participants(fixture)
        if not home or not away:
            continue
        try:
            home_id, away_id = int(home["id"]), int(away["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if team_id not in {home_id, away_id} or _state(fixture) != "finished":
            continue
        home_goals, away_goals = _scores(fixture, home_id, away_id)
        if home_goals is None or away_goals is None:
            continue
        is_home = team_id == home_id
        opponent = away if is_home else home
        opponent_id = away_id if is_home else home_id
        matches.append({
            "fixture_id": fixture.get("id"),
            "date": fixture.get("starting_at"),
            "venue": "home" if is_home else "away",
            "opponent_id": opponent_id,
            "opponent_name": opponent.get("name"),
            "goals_for": home_goals if is_home else away_goals,
            "goals_against": away_goals if is_home else home_goals,
            "opponent_strength": strength_map.get(opponent_id),
            "statistics": _team_statistics(fixture, team_id),
        })

    matches.sort(key=lambda row: str(row.get("date") or ""), reverse=True)
    recent = matches[:10]
    form = analyze_form(recent)
    tactics = analyze_tactics(recent)
    return {
        "id": team_id,
        "name": team.get("name") or f"Team {team_id}",
        "logo": team.get("image_path"),
        "matches": recent,
        "home_rating": venue_rating(recent, "home"),
        "away_rating": venue_rating(recent, "away"),
        # Injury data is not assumed from absence in the fixture feed.
        "player_availability": None,
        "playing_style": tactics["playing_style"],
        "defensive_structure": tactics["defensive_structure"],
        "attacking_approach": tactics["attacking_approach"],
        "tactical_compatibility": None,
        "form_summary": form,
        "tactical_summary": tactics,
        "availability": {
            "injury_data_available": False,
            "reported_injuries": None,
            "injuries": [],
            "player_availability": None,
            "note": "No verified injury feed was included in this collection; player availability remains unknown.",
        },
        "lineups": {"lineups_available": False, "teams": [],
                    "note": "Lineups are not used unless a verified lineup response is available."},
        "upcoming_fixture_id": None,
        "data_quality": {
            "provider": "sportmonks",
            "season_id": int(season_id),
            "matches_returned": len(recent),
            "goals_complete": len(recent) >= 5,
            "opponent_strength_matches": sum(m.get("opponent_strength") is not None for m in recent),
            "statistics_matches": sum(bool(m.get("statistics")) for m in recent),
            "fixtures_scanned": len(fixtures),
        },
    }
