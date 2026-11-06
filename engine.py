"""Layer 1 football prediction engine.

Inputs are pre-match team profiles. Match history must be ordered newest first.
All ratings are on a 0-100 scale. This is a transparent baseline model, not
a trained/calibrated betting model.
"""
from __future__ import annotations
from math import exp, factorial
from typing import Dict, List, Tuple

WEIGHTS = {
    "recent_form": 0.20,
    "goals_scored": 0.10,
    "goals_conceded": 0.10,
    "home_away": 0.10,
    "strength_of_schedule": 0.15,
    "player_availability": 0.05,
    "tactical": 0.30,
}
TACTICAL_WEIGHTS = {
    "playing_style": 0.06,
    "defensive_structure": 0.07,
    "attacking_approach": 0.07,
    "tactical_compatibility": 0.10,
}
BASE_GOALS = 1.45

def _clamp(value: float, low: float = 0.05, high: float = 3.8) -> float:
    return max(low, min(high, value))

def _validate_team(team: Dict, name: str) -> None:
    if not isinstance(team.get("matches"), list) or len(team["matches"]) < 5:
        raise ValueError(f"{name}: provide at least 5 recent matches (10 recommended).")
    for i, m in enumerate(team["matches"][:10]):
        if m.get("goals_for") is None or m.get("goals_against") is None:
            raise ValueError(f"{name}: match {i+1} is missing goals_for/goals_against.")
        if min(float(m["goals_for"]), float(m["goals_against"])) < 0:
            raise ValueError(f"{name}: goals cannot be negative.")
    for key in ("playing_style", "defensive_structure", "attacking_approach"):
        if key not in team:
            raise ValueError(f"{name}: missing tactical rating '{key}'.")

def _weighted_recent(values: List[float]) -> float:
    values = values[:10]
    # Newest five receive 1.5x the weight of matches 6-10.
    weights = [1.5 if i < 5 else 1.0 for i in range(len(values))]
    return sum(v*w for v, w in zip(values, weights)) / sum(weights)

def _form_score(team: Dict) -> float:
    points = []
    for m in team["matches"][:10]:
        gf, ga = float(m["goals_for"]), float(m["goals_against"])
        points.append(3 if gf > ga else 1 if gf == ga else 0)
    return _weighted_recent(points) / 3 * 100

def _goals_score(team: Dict, conceded: bool = False) -> float:
    key = "goals_against" if conceded else "goals_for"
    avg = _weighted_recent([float(m[key]) for m in team["matches"][:10]])
    # Higher is better for scoring; lower is better for conceding.
    return max(0.0, min(100.0, (avg / 2.8 * 100) if not conceded else (100 - avg / 2.8 * 100)))

def _schedule_score(team: Dict) -> float:
    vals = [float(m.get("opponent_strength", 50)) for m in team["matches"][:10]]
    return max(0.0, min(100.0, _weighted_recent(vals)))

def _team_components(team: Dict, venue_key: str) -> Dict[str, float]:
    return {
        "recent_form": _form_score(team),
        "goals_scored": _goals_score(team, False),
        "goals_conceded": _goals_score(team, True),
        "home_away": float(team.get(venue_key, 50)),
        "strength_of_schedule": _schedule_score(team),
        "player_availability": float(team.get("player_availability", 90)),
    }

def _weighted_team_rating(components: Dict[str, float], tactical: float) -> float:
    total = sum(components[k] * WEIGHTS[k] for k in components)
    return total + tactical * WEIGHTS["tactical"]

def _poisson(lam: float, k: int) -> float:
    return exp(-lam) * (lam ** k) / factorial(k)

def predict_match(home: Dict, away: Dict, max_goals: int = 8, tactical_compatibility: Dict[str, float] | None = None) -> Dict:
    """Return probabilities and explanatory ratings for a home-v-away match."""
    _validate_team(home, "Home team")
    _validate_team(away, "Away team")

    home_comp = _team_components(home, "home_rating")
    away_comp = _team_components(away, "away_rating")

    # Tactical inputs are absolute team ratings. Compatibility is a matchup
    # rating supplied by the user/data layer for this specific pairing.
    # Optional TVD overrides are matchup-specific directional scores.
    # If absent, preserve Layer 1 manual compatibility inputs.
    tactical_compatibility = tactical_compatibility or {}
    home_compat = tactical_compatibility.get("home", home.get("tactical_compatibility", 50))
    away_compat = tactical_compatibility.get("away", away.get("tactical_compatibility", 50))
    h_tac = (
        float(home["playing_style"]) * TACTICAL_WEIGHTS["playing_style"] / WEIGHTS["tactical"]
        + float(home["defensive_structure"]) * TACTICAL_WEIGHTS["defensive_structure"] / WEIGHTS["tactical"]
        + float(home["attacking_approach"]) * TACTICAL_WEIGHTS["attacking_approach"] / WEIGHTS["tactical"]
        + float(home_compat) * TACTICAL_WEIGHTS["tactical_compatibility"] / WEIGHTS["tactical"]
    )
    a_tac = (
        float(away["playing_style"]) * TACTICAL_WEIGHTS["playing_style"] / WEIGHTS["tactical"]
        + float(away["defensive_structure"]) * TACTICAL_WEIGHTS["defensive_structure"] / WEIGHTS["tactical"]
        + float(away["attacking_approach"]) * TACTICAL_WEIGHTS["attacking_approach"] / WEIGHTS["tactical"]
        + float(away_compat) * TACTICAL_WEIGHTS["tactical_compatibility"] / WEIGHTS["tactical"]
    )
    home_rating = _weighted_team_rating(home_comp, h_tac)
    away_rating = _weighted_team_rating(away_comp, a_tac)

    # Attack-vs-defence expected goals; rating edge is a restrained adjustment.
    h_gf = _weighted_recent([float(m["goals_for"]) for m in home["matches"][:10]])
    h_ga = _weighted_recent([float(m["goals_against"]) for m in home["matches"][:10]])
    a_gf = _weighted_recent([float(m["goals_for"]) for m in away["matches"][:10]])
    a_ga = _weighted_recent([float(m["goals_against"]) for m in away["matches"][:10]])

    home_attack = max(0.35, h_gf / BASE_GOALS)
    away_defence = max(0.35, a_ga / BASE_GOALS)
    away_attack = max(0.35, a_gf / BASE_GOALS)
    home_defence = max(0.35, h_ga / BASE_GOALS)
    rating_edge = (home_rating - away_rating) / 100

    home_xg = _clamp(BASE_GOALS * (home_attack * away_defence) ** 0.5 * 1.10 * (1 + 0.18 * rating_edge))
    away_xg = _clamp(BASE_GOALS * (away_attack * home_defence) ** 0.5 * 0.90 * (1 - 0.18 * rating_edge))

    score_probs = {}
    home_win = draw = away_win = 0.0
    over15 = over25 = btts = 0.0
    for hg in range(max_goals + 1):
        for ag in range(max_goals + 1):
            p = _poisson(home_xg, hg) * _poisson(away_xg, ag)
            score_probs[f"{hg}-{ag}"] = p
            if hg > ag: home_win += p
            elif hg == ag: draw += p
            else: away_win += p
            if hg + ag >= 2: over15 += p
            if hg + ag >= 3: over25 += p
            if hg > 0 and ag > 0: btts += p

    # Normalize because score grid is truncated at max_goals.
    total = sum(score_probs.values())
    home_win, draw, away_win = [x / total for x in (home_win, draw, away_win)]
    over15, over25, btts = [x / total for x in (over15, over25, btts)]
    top_scores = sorted(
        [{"score": s, "probability": p / total} for s, p in score_probs.items()],
        key=lambda x: x["probability"], reverse=True
    )[:5]

    return {
        "home_team": home.get("name", "Home"),
        "away_team": away.get("name", "Away"),
        "home_rating": round(home_rating, 1),
        "away_rating": round(away_rating, 1),
        "home_expected_goals": round(home_xg, 2),
        "away_expected_goals": round(away_xg, 2),
        "probabilities": {
            "home_win": round(home_win * 100, 1),
            "draw": round(draw * 100, 1),
            "away_win": round(away_win * 100, 1),
            "over_1_5": round(over15 * 100, 1),
            "over_2_5": round(over25 * 100, 1),
            "btts_yes": round(btts * 100, 1),
        },
        "most_likely_scores": [
            {"score": x["score"], "probability": round(x["probability"] * 100, 1)}
            for x in top_scores
        ],
        "component_ratings": {"home": home_comp, "away": away_comp},
        "model_weights": WEIGHTS.copy(),
        "tactical_compatibility_used": {"home": round(float(home_compat), 1), "away": round(float(away_compat), 1)},
        "note": "Probabilities are model estimates, not guarantees. Validate with historical backtesting."
    }
