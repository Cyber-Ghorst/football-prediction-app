
def analyze_form(matches):
    """Calculate weighted team form."""

    if not matches:
        return {
            "form_score": None,
            "points": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "goals_for": 0,
            "goals_against": 0,
            "goal_difference": 0,
            "matches": 0
        }

    latest = matches[:5]
    previous = matches[5:10]

    def average_points(group):
        if not group:
            return None

        points = {
            "W": 3,
            "D": 1,
            "L": 0
        }

        return sum(
            points.get(m["result"], 0)
            for m in group
        ) / len(group)

    recent_score = average_points(latest)
    older_score = average_points(previous)

    if older_score is None:
        form_score = recent_score / 3 * 100
    else:
        form_score = (
            (recent_score * 0.60)
            + (older_score * 0.40)
        ) / 3 * 100

    wins = sum(m["result"] == "W" for m in matches)
    draws = sum(m["result"] == "D" for m in matches)
    losses = sum(m["result"] == "L" for m in matches)

    gf = sum(m["goals_for"] for m in matches)
    ga = sum(m["goals_against"] for m in matches)

    return {
        "form_score": round(form_score, 2),
        "points": wins * 3 + draws,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "goals_for": gf,
        "goals_against": ga,
        "goal_difference": gf - ga,
        "matches": len(matches),
        "recent_form": "".join(
            m["result"] for m in matches
        )
    }
