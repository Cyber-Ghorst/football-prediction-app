"""Evidence-derived tactical matchup profiles from Sportmonks team statistics.

Scores are empirical percentiles within the selected league-season, not tracking
or event-location claims. Missing metrics remain unknown and are never imputed.
"""
from __future__ import annotations

from typing import Any


RECENT_MATCHES = 5
RECENT_WEIGHT = 0.60
PREVIOUS_WEIGHT = 0.40
MIN_TEAM_OBSERVATIONS = 5
MIN_REFERENCE_OBSERVATIONS = 30

# The available team-level feed supports these four matchup dimensions.
# Each dimension is deliberately limited to statistics that directly describe
# the attacking action being counted. Defensive exposure uses the opponent's
# recorded output in the same fixtures.
AUTOMATIC_DIMENSIONS = {
    "counterattack": {
        "weapon_key": "counterattack_threat",
        "vulnerability_key": "transition_recovery",
        "metrics": ("Counter Attacks",),
    },
    "high_quality_chances": {
        "weapon_key": "high_quality_chance_creation",
        "vulnerability_key": "high_quality_chance_exposure",
        "metrics": ("Big Chances Created",),
    },
    "aerial": {
        "weapon_key": "aerial_threat",
        "vulnerability_key": "aerial_defence",
        "metrics": ("Successful Headers",),
    },
    "wide": {
        "weapon_key": "wing_threat",
        "vulnerability_key": "wide_defending",
        "metrics": ("Accurate Crosses", "Successful Dribbles"),
    },
    "central": {
        "weapon_key": "between_lines_threat",
        "vulnerability_key": "central_penetration",
        "metrics": ("Key Passes", "Shots Insidebox"),
    },
}


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _recency_weighted_mean(values: list[float | None]) -> float | None:
    recent = [value for value in values[:RECENT_MATCHES] if value is not None]
    previous = [value for value in values[RECENT_MATCHES:10] if value is not None]
    recent_mean = sum(recent) / len(recent) if recent else None
    previous_mean = sum(previous) / len(previous) if previous else None
    if recent_mean is None:
        return previous_mean
    if previous_mean is None:
        return recent_mean
    return recent_mean * RECENT_WEIGHT + previous_mean * PREVIOUS_WEIGHT


def _percentile(value: float, reference: list[float]) -> float:
    lower = sum(item < value for item in reference)
    equal = sum(item == value for item in reference)
    return round((lower + 0.5 * equal) / len(reference) * 100.0, 1)


def _metric_score(
    matches: list[dict[str, Any]],
    reference: dict[str, list[float]],
    metric_name: str,
    side: str,
) -> dict[str, Any] | None:
    values = [
        _number((match.get(side) or {}).get(metric_name))
        for match in matches[:10]
    ]
    observed = [value for value in values if value is not None]
    population = reference.get(metric_name) or []
    if len(observed) < MIN_TEAM_OBSERVATIONS or len(population) < MIN_REFERENCE_OBSERVATIONS:
        return None
    average = _recency_weighted_mean(values)
    if average is None:
        return None
    return {
        "score": _percentile(average, population),
        "coverage_pct": round(len(observed) / max(1, min(len(matches), 10)) * 100.0, 1),
        "average_value": round(average, 3),
        "observations": len(observed),
        "reference_observations": len(population),
        "reference_method": "empirical mid-rank percentile across team-match observations in the selected league season",
    }


def _dimension_score(
    matches: list[dict[str, Any]],
    reference: dict[str, list[float]],
    metric_names: tuple[str, ...],
    side: str,
) -> dict[str, Any] | None:
    components = []
    for metric_name in metric_names:
        result = _metric_score(matches, reference, metric_name, side)
        if result is not None:
            components.append({"statistic": metric_name, **result})
    if not components:
        return None
    return {
        "score": round(sum(item["score"] for item in components) / len(components), 1),
        "confidence": round(sum(item["coverage_pct"] for item in components) / len(components), 1),
        "evidence": {
            "source": "Sportmonks fixture team statistics",
            "direction": "team output" if side == "statistics" else "opponent output conceded by this team",
            "components": components,
            "recency_weighting": {
                "latest_five_weight": RECENT_WEIGHT,
                "previous_five_weight": PREVIOUS_WEIGHT,
            },
            "interpretation": "Higher percentile means a higher observed rate/count relative to team-match observations in this league season; it is not a match-win probability.",
        },
    }


def build_league_reference_statistics(
    team_match_statistics: list[dict[str, float]],
) -> dict[str, list[float]]:
    """Build season-wide distributions from actual team-match observations."""
    result: dict[str, list[float]] = {}
    for statistics in team_match_statistics:
        for name, raw_value in statistics.items():
            value = _number(raw_value)
            if value is not None:
                result.setdefault(name, []).append(value)
    return result


def build_tactical_evidence_profile(
    matches: list[dict[str, Any]],
    reference: dict[str, list[float]],
    team_name: str,
) -> dict[str, Any]:
    """Create only the tactical dimensions supported by sufficient observations."""
    weapons: dict[str, Any] = {}
    vulnerabilities: dict[str, Any] = {}
    for dimension in AUTOMATIC_DIMENSIONS.values():
        weapon = _dimension_score(matches, reference, dimension["metrics"], "statistics")
        vulnerability = _dimension_score(matches, reference, dimension["metrics"], "opponent_statistics")
        weapons[dimension["weapon_key"]] = weapon
        vulnerabilities[dimension["vulnerability_key"]] = vulnerability

    return {
        "name": team_name,
        "weapons": weapons,
        "vulnerabilities": vulnerabilities,
        "evidence_metadata": {
            "method": "league-season empirical percentile comparison",
            "matches_used": min(len(matches), 10),
            "latest_five_weight": RECENT_WEIGHT,
            "previous_five_weight": PREVIOUS_WEIGHT,
            "minimum_team_observations_per_metric": MIN_TEAM_OBSERVATIONS,
            "minimum_league_reference_observations": MIN_REFERENCE_OBSERVATIONS,
            "available_dimensions": sum(
                weapons.get(dimension["weapon_key"]) is not None
                and vulnerabilities.get(dimension["vulnerability_key"]) is not None
                for dimension in AUTOMATIC_DIMENSIONS.values()
            ),
            "total_dimensions": len(AUTOMATIC_DIMENSIONS),
            "limitations": [
                "These are statistical matchup indicators, not player-tracking or event-location tactical analysis.",
                "Counter-attack compatibility remains unknown when the provider does not supply Counter Attacks.",
                "Big Chances Created measures provider-recorded high-quality chances; it is a separate indicator from shots inside the box and key passes.",
                "No absent statistic is treated as zero or estimated.",
            ],
        },
    }
