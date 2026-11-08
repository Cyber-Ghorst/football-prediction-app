"""Layer 1 prediction engine, extended for Layer 2 missing-data validation.
When all inputs exist, original Layer 1 weights and calculations are preserved.
Unknown components are excluded and remaining known weights are normalized.
"""
from __future__ import annotations
from math import exp, factorial
from typing import Dict, List

WEIGHTS = {"recent_form": 0.20, "goals_scored": 0.10, "goals_conceded": 0.10,
           "home_away": 0.10, "strength_of_schedule": 0.15, "player_availability": 0.05, "tactical": 0.30}
TACTICAL_WEIGHTS = {"playing_style": 0.06, "defensive_structure": 0.07,
                    "attacking_approach": 0.07, "tactical_compatibility": 0.10}
BASE_GOALS = 1.45

def _clamp(value: float, low: float = 0.05, high: float = 3.8) -> float:
    return max(low, min(high, value))

def _validate_team(team: Dict, name: str) -> None:
    matches = team.get("matches")
    if not isinstance(matches, list) or len(matches) < 5:
        raise ValueError(f"{name}: only {len(matches or [])} completed matches available; at least 5 are required (10 recommended).")
    for i, m in enumerate(matches[:10]):
        if m.get("goals_for") is None or m.get("goals_against") is None:
            raise ValueError(f"{name}: match {i+1} is missing goals_for/goals_against.")
        if float(m["goals_for"]) < 0 or float(m["goals_against"]) < 0:
            raise ValueError(f"{name}: goals cannot be negative.")
    for key in ("playing_style", "defensive_structure", "attacking_approach"):
        value = team.get(key)
        if value is not None and not 0 <= float(value) <= 100:
            raise ValueError(f"{name}: {key} must be between 0 and 100.")

def _weighted_recent(values: List[float]) -> float:
    values = values[:10]
    weights = [1.5 if i < 5 else 1.0 for i in range(len(values))]
    return sum(v*w for v, w in zip(values, weights)) / sum(weights)

def _weighted_optional(values: list[float | None]) -> float | None:
    pairs = [(i, float(v)) for i, v in enumerate(values[:10]) if v is not None]
    if not pairs: return None
    weights = [1.5 if i < 5 else 1.0 for i, _ in pairs]
    return sum(v*w for (_, v), w in zip(pairs, weights)) / sum(weights)

def _form_score(team: Dict) -> float:
    pts = [3 if m["goals_for"] > m["goals_against"] else 1 if m["goals_for"] == m["goals_against"] else 0 for m in team["matches"][:10]]
    return _weighted_recent(pts) / 3 * 100

def _goals_score(team: Dict, conceded: bool = False) -> float:
    key = "goals_against" if conceded else "goals_for"
    avg = _weighted_recent([float(m[key]) for m in team["matches"][:10]])
    return max(0.0, min(100.0, 100 - avg / 2.8 * 100 if conceded else avg / 2.8 * 100))

def _schedule_score(team: Dict) -> float | None:
    avg = _weighted_optional([m.get("opponent_strength") for m in team["matches"][:10]])
    return max(0.0, min(100.0, avg)) if avg is not None else None

def _team_components(team: Dict, venue_key: str) -> Dict[str, float]:
    values = {
        "recent_form": _form_score(team),
        "goals_scored": _goals_score(team, False),
        "goals_conceded": _goals_score(team, True),
        "home_away": team.get(venue_key),
        "strength_of_schedule": _schedule_score(team),
        "player_availability": team.get("player_availability"),
    }
    return {k: float(v) for k, v in values.items() if v is not None}

def _tactical_rating(team: Dict, compatibility: float | None) -> tuple[float | None, dict]:
    values = {"playing_style": team.get("playing_style"),
              "defensive_structure": team.get("defensive_structure"),
              "attacking_approach": team.get("attacking_approach"),
              "tactical_compatibility": compatibility if compatibility is not None else team.get("tactical_compatibility")}
    known = {k: float(v) for k, v in values.items() if v is not None}
    if not known: return None, known
    total_weight = sum(TACTICAL_WEIGHTS[k] for k in known)
    return sum(v * TACTICAL_WEIGHTS[k] for k, v in known.items()) / total_weight, known

def _rating(components: dict, tactical: float | None) -> float:
    weighted = sum(components[k] * WEIGHTS[k] for k in components)
    known_weight = sum(WEIGHTS[k] for k in components)
    if tactical is not None:
        weighted += tactical * WEIGHTS["tactical"]
        known_weight += WEIGHTS["tactical"]
    return weighted / known_weight if known_weight else 50.0

def _poisson(lam: float, k: int) -> float:
    return exp(-lam) * (lam ** k) / factorial(k)


def most_likely_outcome(probabilities: Dict[str, float], home_name: str = "Home", away_name: str = "Away") -> Dict[str, object]:
    """Return a plain-language label for the highest 1X2 probability."""
    outcomes = [
        (f"Predicted winner: {home_name}", float(probabilities["home_win"])),
        ("Most likely outcome: Draw", float(probabilities["draw"])),
        (f"Predicted winner: {away_name}", float(probabilities["away_win"])),
    ]
    highest = max(value for _, value in outcomes)
    leaders = [label for label, value in outcomes if value == highest]
    label = leaders[0] if len(leaders) == 1 else "No single most likely outcome (tied probabilities)"
    return {"label": label, "probability": highest}


def predict_match(home: Dict, away: Dict, max_goals: int = 8, tactical_compatibility: Dict[str, float] | None = None) -> Dict:
    _validate_team(home, "Home team"); _validate_team(away, "Away team")
    home_comp = _team_components(home, "home_rating")
    away_comp = _team_components(away, "away_rating")
    overrides = tactical_compatibility or {}
    home_tac, home_tac_parts = _tactical_rating(home, overrides.get("home"))
    away_tac, away_tac_parts = _tactical_rating(away, overrides.get("away"))
    home_rating = _rating(home_comp, home_tac)
    away_rating = _rating(away_comp, away_tac)
    h_gf = _weighted_recent([float(m["goals_for"]) for m in home["matches"][:10]])
    h_ga = _weighted_recent([float(m["goals_against"]) for m in home["matches"][:10]])
    a_gf = _weighted_recent([float(m["goals_for"]) for m in away["matches"][:10]])
    a_ga = _weighted_recent([float(m["goals_against"]) for m in away["matches"][:10]])
    home_attack, away_defence = max(0.35, h_gf / BASE_GOALS), max(0.35, a_ga / BASE_GOALS)
    away_attack, home_defence = max(0.35, a_gf / BASE_GOALS), max(0.35, h_ga / BASE_GOALS)
    edge = (home_rating - away_rating) / 100
    home_xg = _clamp(BASE_GOALS * (home_attack * away_defence) ** 0.5 * 1.10 * (1 + 0.18 * edge))
    away_xg = _clamp(BASE_GOALS * (away_attack * home_defence) ** 0.5 * 0.90 * (1 - 0.18 * edge))
    score_probs = {}; hw = dr = aw = over15 = over25 = btts = 0.0
    for hg in range(max_goals + 1):
        for ag in range(max_goals + 1):
            p = _poisson(home_xg, hg) * _poisson(away_xg, ag); score_probs[f"{hg}-{ag}"] = p
            if hg > ag: hw += p
            elif hg == ag: dr += p
            else: aw += p
            if hg + ag >= 2: over15 += p
            if hg + ag >= 3: over25 += p
            if hg > 0 and ag > 0: btts += p
    total = sum(score_probs.values()); hw, dr, aw, over15, over25, btts = [x/total for x in (hw, dr, aw, over15, over25, btts)]
    top = sorted([{"score": s, "probability": p/total} for s,p in score_probs.items()], key=lambda x:x["probability"], reverse=True)[:5]
    used = {"home": home_tac_parts.get("tactical_compatibility"), "away": away_tac_parts.get("tactical_compatibility")}
    if overrides.get("home") is not None: used["home"] = float(overrides["home"])
    if overrides.get("away") is not None: used["away"] = float(overrides["away"])
    return {
        "home_team": home.get("name", "Home"), "away_team": away.get("name", "Away"),
        "home_rating": round(home_rating,1), "away_rating": round(away_rating,1),
        "home_expected_goals": round(home_xg,2), "away_expected_goals": round(away_xg,2),
        "probabilities": {"home_win":round(hw*100,1),"draw":round(dr*100,1),"away_win":round(aw*100,1),"over_1_5":round(over15*100,1),"over_2_5":round(over25*100,1),"btts_yes":round(btts*100,1)},
        "most_likely_scores":[{"score":x["score"],"probability":round(x["probability"]*100,1)} for x in top],
        "component_ratings":{"home":home_comp,"away":away_comp}, "model_weights":WEIGHTS.copy(),
        "tactical_component_ratings":{"home":home_tac_parts,"away":away_tac_parts},
        "tactical_compatibility_used":{k:round(v,1) if v is not None else None for k,v in used.items()},
        "data_coverage":{"home_known_weight":round(sum(WEIGHTS[k] for k in home_comp)+(WEIGHTS['tactical'] if home_tac is not None else 0),3),
                         "away_known_weight":round(sum(WEIGHTS[k] for k in away_comp)+(WEIGHTS['tactical'] if away_tac is not None else 0),3)},
        "note":"Probabilities are model estimates, not guarantees. Missing components were excluded and remaining known weights normalized. Validate with historical backtesting."
    }
