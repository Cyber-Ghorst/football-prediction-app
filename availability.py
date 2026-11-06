"""Optional squad availability retrieval. Does not invent an availability score."""
from __future__ import annotations
from typing import Any


def summarize_injuries(injury_rows: list[dict[str, Any]]) -> dict[str, Any]:
    names = []
    for row in injury_rows:
        player = row.get("player") or {}
        team = row.get("team") or {}
        names.append({
            "player": player.get("name", "Unknown player"),
            "team": team.get("name"),
            "type": (row.get("player") or {}).get("type"),
            "reason": (row.get("player") or {}).get("reason"),
        })
    return {
        "injury_data_available": bool(injury_rows),
        "reported_injuries": len(injury_rows),
        "injuries": names,
        # A squad denominator/minutes impact is not provided consistently by this feed.
        # Therefore player_availability remains unknown rather than guessed.
        "player_availability": None,
        "note": "Injury reports are displayed, but no availability rating is calculated without a verified squad-impact denominator.",
    }


def summarize_lineups(lineup_rows: list[dict[str, Any]]) -> dict[str, Any]:
    teams = []
    for row in lineup_rows:
        teams.append({
            "team": (row.get("team") or {}).get("name"),
            "formation": row.get("formation"),
            "starting_xi": [p.get("player", {}).get("name") for p in row.get("startXI", [])],
            "substitutes": [p.get("player", {}).get("name") for p in row.get("substitutes", [])],
        })
    return {"lineups_available": bool(teams), "teams": teams}
