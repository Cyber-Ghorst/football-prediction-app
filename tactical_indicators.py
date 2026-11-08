"""Conservative tactical indicators derived only from returned match statistics."""
from __future__ import annotations
from typing import Any


RECENT_MATCH_COUNT = 5
RECENT_WEIGHT = 0.60
PREVIOUS_WEIGHT = 0.40


def _number(stats: dict, *keys: str) -> float | None:
    for key in keys:
        value = stats.get(key)
        if value is not None:
            try:
                return float(str(value).replace("%", "").replace(",", ""))
            except (TypeError, ValueError):
                pass
    return None


def _mean(values: list[float | None]) -> float | None:
    known = [v for v in values if v is not None]
    return sum(known) / len(known) if known else None


def _recency_weighted_mean(values: list[float | None]) -> float | None:
    """Combine latest-five and previous-five means using 60% / 40%.

    Missing observations stay missing. If one time window has no observations
    for a metric, the available window is renormalized rather than treated as 0.
    """
    recent = _mean(values[:RECENT_MATCH_COUNT])
    previous = _mean(values[RECENT_MATCH_COUNT:10])
    if recent is None and previous is None:
        return None
    if recent is None:
        return previous
    if previous is None:
        return recent
    return recent * RECENT_WEIGHT + previous * PREVIOUS_WEIGHT


def _scale(value: float | None, low: float, high: float, inverse: bool = False) -> float | None:
    if value is None:
        return None
    score = max(0.0, min(100.0, (value - low) / (high - low) * 100))
    return round(100 - score if inverse else score, 1)


def analyze_tactics(matches: list[dict]) -> dict[str, Any]:
    # Callers provide matches newest first. Keep the agreed ten-match window.
    stats = [m.get("statistics") or {} for m in matches[:10]]
    possession = _recency_weighted_mean([_number(s, "Ball Possession", "ball_possession") for s in stats])
    pass_accuracy = _recency_weighted_mean([_number(s, "Passes %", "Passes accuracy", "passes_accuracy") for s in stats])
    shots = _recency_weighted_mean([_number(s, "Total Shots", "total_shots") for s in stats])
    shots_on_target = _recency_weighted_mean([_number(s, "Shots on Goal", "Shots on Target", "shots_on_target") for s in stats])
    tackles = _recency_weighted_mean([_number(s, "Tackles", "tackles") for s in stats])
    interceptions = _recency_weighted_mean([_number(s, "Interceptions", "interceptions") for s in stats])
    blocks = _recency_weighted_mean([_number(s, "Blocked Shots", "blocked_shots") for s in stats])
    corners = _recency_weighted_mean([_number(s, "Corner Kicks", "corners") for s in stats])

    style_parts = [_scale(possession, 30, 70), _scale(pass_accuracy, 60, 95)]
    attack_parts = [_scale(shots, 5, 22), _scale(shots_on_target, 1, 9), _scale(corners, 1, 9)]
    defence_parts = [_scale(tackles, 8, 28), _scale(interceptions, 3, 18), _scale(blocks, 0, 8)]
    style = _mean(style_parts)
    attack = _mean(attack_parts)
    defence = _mean(defence_parts)
    coverage = sum(v is not None for v in [possession, pass_accuracy, shots, shots_on_target, tackles, interceptions, blocks, corners])
    return {
        "playing_style": style,
        "attacking_approach": attack,
        "defensive_structure": defence,
        "coverage_metrics": coverage,
        "available_metrics": {
            "average_possession": round(possession, 1) if possession is not None else None,
            "average_pass_accuracy": round(pass_accuracy, 1) if pass_accuracy is not None else None,
            "average_shots": round(shots, 1) if shots is not None else None,
            "average_shots_on_target": round(shots_on_target, 1) if shots_on_target is not None else None,
            "average_tackles": round(tackles, 1) if tackles is not None else None,
            "average_interceptions": round(interceptions, 1) if interceptions is not None else None,
            "average_blocked_shots": round(blocks, 1) if blocks is not None else None,
            "average_corners": round(corners, 1) if corners is not None else None,
        },
        "recency_weighting": {
            "matches_used": len(stats),
            "recent_matches": min(len(stats), RECENT_MATCH_COUNT),
            "recent_weight": RECENT_WEIGHT,
            "previous_matches": max(0, len(stats) - RECENT_MATCH_COUNT),
            "previous_weight": PREVIOUS_WEIGHT,
            "note": "Latest five matches carry 60%; previous five carry 40%. If a metric is absent from one window, the available window is renormalized.",
        },
        "note": "Tactical ratings are shown only when the underlying statistics are present; unavailable metrics remain unknown.",
    }
