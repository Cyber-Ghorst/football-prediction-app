"""Layer 1 prediction engine, extended for Layer 2 missing-data validation.
When all inputs exist, original Layer 1 weights and calculations are preserved.
Unknown components are excluded and remaining known weights are normalized.
"""
from __future__ import annotations
from math import exp, factorial, isfinite
from typing import Dict, List

WEIGHTS = {"recent_form": 0.20, "goals_scored": 0.10, "goals_conceded": 0.10,
           "home_away": 0.10, "strength_of_schedule": 0.15, "player_availability": 0.05, "tactical": 0.30}
TACTICAL_WEIGHTS = {"playing_style": 0.06, "defensive_structure": 0.07,
                    "attacking_approach": 0.07, "tactical_compatibility": 0.10}
BASE_GOALS = 1.45

def _clamp(value: float, low: float = 0.05, high: float = 3.8) -> float:
    return max(low, min(high, value))

def _validated_number(value, field: str, *, minimum: float | None = None,
                      maximum: float | None = None) -> float:
    """Parse a supplied numeric value and reject malformed or non-finite data."""
    if isinstance(value, bool):
        raise ValueError(f"{field} is malformed: boolean values are not numeric observations.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} is malformed: expected a finite number.") from None
    if not isfinite(number):
        raise ValueError(f"{field} is non-finite: expected a finite number.")
    if minimum is not None and number < minimum:
        raise ValueError(f"{field} is out of range: minimum is {minimum}.")
    if maximum is not None and number > maximum:
        raise ValueError(f"{field} is out of range: maximum is {maximum}.")
    return number


def _validate_optional_score(team: Dict, key: str, name: str) -> None:
    value = team.get(key)
    if value is not None:
        _validated_number(value, f"{name}.{key}", minimum=0, maximum=100)


def _validate_team(team: Dict, name: str) -> None:
    if not isinstance(team, dict):
        raise ValueError(f"{name}: team profile must be an object.")
    matches = team.get("matches")
    if not isinstance(matches, list):
        raise ValueError(f"{name}: matches must be a list.")
    if len(matches) < 5:
        raise ValueError(f"{name}: only {len(matches)} completed matches available; at least 5 are required (10 recommended).")

    for i, match in enumerate(matches[:10]):
        prefix = f"{name}.matches[{i}]"
        if not isinstance(match, dict):
            raise ValueError(f"{prefix} is malformed: expected a match object.")
        for key in ("goals_for", "goals_against"):
            if key not in match or match[key] is None:
                raise ValueError(f"{prefix}.{key} is missing.")
            _validated_number(match[key], f"{prefix}.{key}", minimum=0)
        if match.get("opponent_strength") is not None:
            _validated_number(match["opponent_strength"],
                              f"{prefix}.opponent_strength", minimum=0, maximum=100)

    for key in ("home_rating", "away_rating", "player_availability",
                "playing_style", "defensive_structure", "attacking_approach",
                "tactical_compatibility"):
        _validate_optional_score(team, key, name)

def _weighted_recent(values: List[float]) -> float:
    values = values[:10]
    weights = [1.5 if i < 5 else 1.0 for i in range(len(values))]
    return sum(v*w for v, w in zip(values, weights)) / sum(weights)

def _weighted_optional(values: list[float | None]) -> float | None:
    # Keep each observation's original match index so missing values cannot
    # shift older observations into the latest-five weighting window.
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

def build_prediction_component_readiness(home: Dict, away: Dict, tactical_compatibility: Dict[str, float] | None = None) -> Dict:
    """Assess strict standard-prediction eligibility without imputing data."""
    overrides = tactical_compatibility or {}
    required = ["recent_form", "goals_scored", "goals_conceded", "home_away", "strength_of_schedule", "player_availability", "tactical"]
    tactical_required = ["playing_style", "defensive_structure", "attacking_approach", "tactical_compatibility"]
    teams = {}
    for side, profile, venue_key in (("home", home, "home_rating"), ("away", away, "away_rating")):
        errors = []
        try:
            _validate_team(profile, f"{side.title()} team")
            if not isinstance(overrides, dict):
                raise ValueError("tactical_compatibility overrides must be an object.")
            if overrides.get(side) is not None:
                _validated_number(overrides[side], f"tactical_compatibility.{side}", minimum=0, maximum=100)
            components = _team_components(profile, venue_key)
            _, tactical_parts = _tactical_rating(profile, overrides.get(side))
            tactical_status = {key: key in tactical_parts for key in tactical_required}
            status = {key: key in components for key in required if key != "tactical"}
            status["tactical"] = all(tactical_status.values())
        except (ValueError, TypeError, AttributeError) as exc:
            errors.append(str(exc))
            status = {key: False for key in required}
            tactical_status = {key: False for key in tactical_required}
        missing = [key for key in required if not status.get(key, False)]
        missing_tactical = [key for key in tactical_required if not tactical_status.get(key, False)]
        teams[side] = {
            "team": profile.get("name") if isinstance(profile, dict) else None,
            "eligible": not missing and not errors,
            "top_level_components": status,
            "tactical_subcomponents": tactical_status,
            "missing_components": missing,
            "missing_tactical_subcomponents": missing_tactical,
            "available_weight": round(sum(WEIGHTS[key] for key, ok in status.items() if ok), 3),
            "validation_errors": errors,
        }
    eligible = all(item["eligible"] for item in teams.values())
    return {"policy_version": "strict-component-readiness-v1", "prediction_type": "standard",
            "status": "eligible" if eligible else "blocked", "eligible": eligible,
            "required_top_level_components": required, "required_tactical_subcomponents": tactical_required,
            "weights_redistributed": False, "missing_data_imputed": False, "teams": teams}

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


def _snapshot_number(value):
    """Return finite numeric feature values; preserve unknowns as None."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def build_prediction_feature_snapshot(
    home: Dict,
    away: Dict,
    result: Dict,
    *,
    tactical_compatibility: Dict[str, float] | None = None,
    captured_at: str | None = None,
) -> Dict:
    """Capture the exact engine inputs and calculated features for one forecast.

    The returned object is an audit snapshot, not a new source of model inputs.
    Only fields consumed by predict_match plus available source metadata are kept.
    """
    overrides = tactical_compatibility or {}

    def team_snapshot(team: Dict, side: str, venue_key: str) -> Dict:
        provenance_keys = (
            "source", "provider", "data_source", "fetched_at",
            "statistics_source", "statistics_fetched_at",
            "matches_source", "matches_fetched_at", "last_updated_at",
        )
        provenance = {
            key: str(team[key]) for key in provenance_keys
            if team.get(key) not in (None, "")
        }
        matches = []
        for match in team.get("matches", [])[:10]:
            matches.append({
                "goals_for": _snapshot_number(match.get("goals_for")),
                "goals_against": _snapshot_number(match.get("goals_against")),
                "opponent_strength": _snapshot_number(match.get("opponent_strength")),
            })
        return {
            "team_name": team.get("name", "Home" if side == "home" else "Away"),
            "team_id": str(team.get("id")) if team.get("id") is not None else None,
            "venue_rating": _snapshot_number(team.get(venue_key)),
            "player_availability": _snapshot_number(team.get("player_availability")),
            "playing_style": _snapshot_number(team.get("playing_style")),
            "defensive_structure": _snapshot_number(team.get("defensive_structure")),
            "attacking_approach": _snapshot_number(team.get("attacking_approach")),
            "tactical_compatibility": _snapshot_number(
                overrides.get(side) if overrides.get(side) is not None
                else team.get("tactical_compatibility")
            ),
            "recent_matches": matches,
            "source_provenance": provenance,
        }

    output_keys = (
        "home_rating", "away_rating", "home_expected_goals",
        "away_expected_goals", "component_ratings", "model_weights",
        "tactical_component_ratings", "tactical_compatibility_used",
        "data_coverage", "probabilities",
    )
    calculated = {key: result.get(key) for key in output_keys if key in result}
    return {
        "schema_version": "prediction-features-v1",
        "captured_at": captured_at or "",
        "recency_policy": "latest_5_60pct_previous_5_40pct",
        "teams": {
            "home": team_snapshot(home, "home", "home_rating"),
            "away": team_snapshot(away, "away", "away_rating"),
        },
        "calculated": calculated,
    }


def predict_match(home: Dict, away: Dict, max_goals: int = 8, tactical_compatibility: Dict[str, float] | None = None) -> Dict:
    readiness = build_prediction_component_readiness(home, away, tactical_compatibility)
    if not readiness["eligible"]:
        reasons = []
        for side, report in readiness["teams"].items():
            if report["missing_components"]:
                reasons.append(f"{side}: {', '.join(report['missing_components'])}")
            if report["missing_tactical_subcomponents"]:
                reasons.append(f"{side} tactical: {', '.join(report['missing_tactical_subcomponents'])}")
            reasons.extend(report["validation_errors"])
        raise ValueError("Standard prediction blocked by strict readiness policy; " + "; ".join(reasons))
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
        "note":"Probabilities are model estimates, not guarantees. Strict readiness requires all agreed components; missing weights are never redistributed. Validate with historical backtesting."
    }
