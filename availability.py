
def analyze_availability(api, fixture_id, home_id, away_id):
    """Identify unavailable players for both teams."""

    injuries = api.injuries(fixture_id)

    result = {
        "home": [],
        "away": [],
        "total_unavailable": 0,
        "data_available": bool(injuries)
    }

    for item in injuries:
        team = item.get("team", {})
        player = item.get("player", {})

        team_id = team.get("id")

        record = {
            "name": player.get("name"),
            "type": player.get("type"),
            "reason": player.get("reason")
        }

        if team_id == home_id:
            result["home"].append(record)

        elif team_id == away_id:
            result["away"].append(record)

    result["total_unavailable"] = (
        len(result["home"]) + len(result["away"])
    )

    return result
