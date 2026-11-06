
from datetime import datetime, timezone


def prepare_team_data(api, team_id, limit=10):
    """Collect and validate a team's recent match data."""

    matches = api.recent_matches(team_id, limit)

    valid_matches = []

    for match in matches:
        if (
            match.get("goals_for") is None
            or match.get("goals_against") is None
        ):
            continue

        valid_matches.append(match)

    valid_matches.sort(
        key=lambda x: x.get("date") or "",
        reverse=True
    )

    return {
        "team_id": team_id,
        "matches": valid_matches[:limit],
        "matches_found": len(valid_matches[:limit]),
        "data_complete": len(valid_matches) >= limit,
        "collected_at": datetime.now(
            timezone.utc
        ).isoformat()
    }


def prepare_match_data(api, home_id, away_id, limit=10):
    """Collect data for both teams."""

    home = prepare_team_data(api, home_id, limit)
    away = prepare_team_data(api, away_id, limit)

    return {
        "home": home,
        "away": away,
        "ready": (
            home["matches_found"] > 0
            and away["matches_found"] > 0
        )
    }
