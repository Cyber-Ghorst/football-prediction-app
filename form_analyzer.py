"""Recent form calculations. Input matches must be newest first."""
from __future__ import annotations
from typing import Any


def weighted_average(values: list[float | None]) -> float | None:
    known = [(i, float(v)) for i, v in enumerate(values[:10]) if v is not None]
    if not known:
        return None
    # Exactly 60% of total weight for the latest five and 40% for matches 6-10.
    # Within each block, matches share that block's weight equally.
    weights = []
    for i, _ in known:
        weights.append(0.12 if i < 5 else 0.08)
    total = sum(weights)
    return sum(v * w for (_, v), w in zip(known, weights)) / total if total else None


def analyze_form(matches: list[dict[str, Any]]) -> dict[str, Any]:
    matches = matches[:10]
    points = []
    for m in matches:
        gf, ga = m.get("goals_for"), m.get("goals_against")
        if gf is None or ga is None:
            points.append(None)
        else:
            points.append(3 if gf > ga else 1 if gf == ga else 0)
    avg_points = weighted_average(points)
    gf = weighted_average([m.get("goals_for") for m in matches])
    ga = weighted_average([m.get("goals_against") for m in matches])
    strengths = weighted_average([m.get("opponent_strength") for m in matches])
    return {
        "matches_used": len(matches),
        "known_results": sum(x is not None for x in points),
        "form_rating": round(avg_points / 3 * 100, 1) if avg_points is not None else None,
        "average_goals_for": round(gf, 2) if gf is not None else None,
        "average_goals_against": round(ga, 2) if ga is not None else None,
        "opponent_strength_rating": round(strengths, 1) if strengths is not None else None,
    }


def venue_rating(matches: list[dict], venue: str) -> float | None:
    selected = [m for m in matches[:10] if m.get("venue") == venue]
    if not selected:
        return None
    points = []
    for m in selected:
        gf, ga = m.get("goals_for"), m.get("goals_against")
        if gf is not None and ga is not None:
            points.append(3 if gf > ga else 1 if gf == ga else 0)
    if not points:
        return None
    return round(sum(points) / (3 * len(points)) * 100, 1)
