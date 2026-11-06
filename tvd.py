"""Rules-based Tactical Vulnerability Detector (TVD) v1.

Scores are diagnostic matchup ratings, not match-win probabilities.
Each input is a 0-100 score. Missing inputs are excluded, never imputed.
"""
from __future__ import annotations
from typing import Any, Dict, Optional

MATCHUPS = [
    {"id": "space_behind", "vulnerability": "space_behind", "weapon": "pace_through_balls",
     "label": "Space behind the defensive line", "threat": "Pace and through balls", "weight": 16},
    {"id": "press_resistance", "vulnerability": "press_resistance", "weapon": "pressing_intensity",
     "label": "Poor press resistance", "threat": "High pressing", "weight": 14},
    {"id": "aerial_defence", "vulnerability": "aerial_defence", "weapon": "aerial_threat",
     "label": "Weak aerial defense", "threat": "Aerial attacks and crosses", "weight": 12},
    {"id": "transition_recovery", "vulnerability": "transition_recovery", "weapon": "counterattack_threat",
     "label": "Slow defensive recovery", "threat": "Fast counterattacks", "weight": 16},
    {"id": "central_compactness", "vulnerability": "central_compactness", "weapon": "midfield_overloads",
     "label": "Weak central compactness", "threat": "Midfield overloads", "weight": 14},
    {"id": "wide_defending", "vulnerability": "wide_defending", "weapon": "wing_threat",
     "label": "Poor wide defending", "threat": "Wing attacks and overlaps", "weight": 14},
    {"id": "central_penetration", "vulnerability": "central_penetration", "weapon": "between_lines_threat",
     "label": "Vulnerability between the lines", "threat": "Central penetration", "weight": 14},
]


def _metric(value: Any, team_name: str, metric_name: str) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = {"score": value, "confidence": 50}
    if not isinstance(value, dict) or "score" not in value:
        raise ValueError(f"{team_name}: {metric_name} must be a 0-100 score or a metric object.")
    score = value["score"]
    confidence = value.get("confidence", 50)
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 100:
        raise ValueError(f"{team_name}: {metric_name} score must be between 0 and 100.")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 100:
        raise ValueError(f"{team_name}: {metric_name} confidence must be between 0 and 100.")
    return {"score": float(score), "confidence": float(confidence), "evidence": value.get("evidence")}


def _risk(score: float) -> str:
    if score >= 70:
        return "HIGH"
    if score >= 45:
        return "MODERATE"
    return "LOW"


def analyze_direction(attacking_team: Dict[str, Any], defending_team: Dict[str, Any]) -> Dict[str, Any]:
    """Rate how effectively attacking_team can target defending_team."""
    findings = []
    weighted_total = 0.0
    effective_weight_total = 0.0

    for rule in MATCHUPS:
        weakness = _metric(
            defending_team.get("vulnerabilities", {}).get(rule["vulnerability"]),
            defending_team.get("name", "Defending team"), rule["vulnerability"])
        weapon = _metric(
            attacking_team.get("weapons", {}).get(rule["weapon"]),
            attacking_team.get("name", "Attacking team"), rule["weapon"])
        if weakness is None or weapon is None:
            continue

        score = weakness["score"] * weapon["score"] / 100.0
        confidence = min(weakness["confidence"], weapon["confidence"])
        effective_weight = rule["weight"] * confidence / 100.0
        if effective_weight > 0:
            weighted_total += score * effective_weight
            effective_weight_total += effective_weight

        findings.append({
            "id": rule["id"],
            "vulnerability": rule["label"],
            "attacking_weapon": rule["threat"],
            "vulnerability_score": round(weakness["score"], 1),
            "weapon_score": round(weapon["score"], 1),
            "matchup_score": round(score, 1),
            "confidence": round(confidence, 1),
            "weight": rule["weight"],
            "risk": _risk(score),
            "evidence": {"vulnerability": weakness["evidence"], "weapon": weapon["evidence"]},
        })

    findings.sort(key=lambda item: item["matchup_score"], reverse=True)
    score = weighted_total / effective_weight_total if effective_weight_total else None
    return {
        "attacking_team": attacking_team.get("name", "Team A"),
        "defending_team": defending_team.get("name", "Team B"),
        "compatibility_score": round(score, 1) if score is not None else None,
        "risk_level": _risk(score) if score is not None else "INSUFFICIENT DATA",
        "data_coverage": round(effective_weight_total, 1),
        "findings": findings,
        "missing_pairings": len(MATCHUPS) - len(findings),
    }


def run_tvd(team_a: Dict[str, Any], team_b: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate both attack directions and return compatibility ratings."""
    a_attacks_b = analyze_direction(team_a, team_b)
    b_attacks_a = analyze_direction(team_b, team_a)
    a_score, b_score = a_attacks_b["compatibility_score"], b_attacks_a["compatibility_score"]
    if a_score is None or b_score is None:
        stronger = "INSUFFICIENT DATA"
    elif a_score > b_score:
        stronger = team_a.get("name", "Team A")
    elif b_score > a_score:
        stronger = team_b.get("name", "Team B")
    else:
        stronger = "EVEN"
    return {
        "team_a_attacks_b": a_attacks_b,
        "team_b_attacks_a": b_attacks_a,
        "tactical_compatibility": {
            team_a.get("name", "Team A"): a_score,
            team_b.get("name", "Team B"): b_score,
        },
        "stronger_tactical_matchup": stronger,
    }
