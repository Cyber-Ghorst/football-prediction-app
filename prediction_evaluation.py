"""Prediction ledger and leakage-safe model/Opta evaluation.

This module scores saved pre-match forecasts against verified final results.
It does not train the model, tune weights, or feed benchmark probabilities
back into the prediction engine.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite, log
import json
from typing import Any, Iterable, Mapping
import uuid

OUTCOMES = ("home", "draw", "away")
PROBABILITY_FIELDS = ("home_win", "draw", "away_win")


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _valid_probabilities(values: Mapping[str, Any]) -> dict[str, float] | None:
    try:
        result = {key: float(values[key]) for key in PROBABILITY_FIELDS}
    except (KeyError, TypeError, ValueError):
        return None
    if any(not isfinite(value) or value < 0 or value > 100 for value in result.values()):
        return None
    if abs(sum(result.values()) - 100.0) > 0.6:
        return None
    return {key: value / 100.0 for key, value in result.items()}


def outcome_from_score(home_goals: Any, away_goals: Any) -> str | None:
    try:
        home_float, away_float = float(home_goals), float(away_goals)
        if not isfinite(home_float) or not isfinite(away_float):
            return None
        if not home_float.is_integer() or not away_float.is_integer():
            return None
        home, away = int(home_float), int(away_float)
    except (TypeError, ValueError):
        return None
    if home < 0 or away < 0:
        return None
    return "home" if home > away else "away" if home < away else "draw"


def build_prediction_record(
    *,
    competition: str,
    country: str | None,
    season: int | str,
    home_team: str,
    away_team: str,
    probabilities: Mapping[str, Any],
    predicted_at: str | None = None,
    kickoff_at: str | None = None,
    fixture_id: str | int | None = None,
    fixture_provider: str | None = None,
    opta_probabilities: Mapping[str, Any] | None = None,
    opta_source_url: str | None = None,
    opta_captured_at: str | None = None,
    player_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a portable, auditable prediction row."""
    model = _valid_probabilities(probabilities)
    if model is None:
        raise ValueError("Model probabilities must be valid and sum to 100%.")
    created = predicted_at or datetime.now(timezone.utc).isoformat()
    kickoff = _parse_datetime(kickoff_at)
    created_dt = _parse_datetime(created)
    opta = _valid_probabilities(opta_probabilities or {}) if opta_probabilities else None
    snapshot = dict(player_snapshot or {})
    snapshot_at = _parse_datetime(snapshot.get("fetched_at"))
    return {
        "record_id": uuid.uuid4().hex,
        "predicted_at": created,
        "kickoff_at": kickoff_at or "",
        "prediction_before_kickoff": bool(kickoff and created_dt and created_dt < kickoff),
        "competition": competition,
        "country": country or "",
        "season": str(season),
        "home_team": home_team,
        "away_team": away_team,
        "fixture_id": str(fixture_id or ""),
        "fixture_provider": fixture_provider or "",
        "model_version": "weighted-football-model-v1",
        "model_recency_policy": "latest_5_60pct_previous_5_40pct",
        "model_home_win": round(model["home_win"] * 100, 4),
        "model_draw": round(model["draw"] * 100, 4),
        "model_away_win": round(model["away_win"] * 100, 4),
        "opta_home_win": round(opta["home_win"] * 100, 4) if opta else "",
        "opta_draw": round(opta["draw"] * 100, 4) if opta else "",
        "opta_away_win": round(opta["away_win"] * 100, 4) if opta else "",
        "opta_source_url": opta_source_url or "",
        "opta_captured_at": opta_captured_at or "",
        "player_snapshot_at": snapshot.get("fetched_at") or "",
        "player_snapshot_before_kickoff": bool(
            kickoff and snapshot_at and snapshot_at < kickoff
        ),
        "player_snapshot_availability": snapshot.get("availability", "unknown"),
        "player_records_count": len(snapshot.get("players") or []),
        "player_unknown_count": len(snapshot.get("unknown_players") or []),
        "player_snapshot_players_json": json.dumps(snapshot.get("players") or [], ensure_ascii=False, separators=(",", ":")),
        "player_snapshot_teams_json": json.dumps(snapshot.get("teams") or {}, ensure_ascii=False, separators=(",", ":")),
        "actual_home_goals": "",
        "actual_away_goals": "",
        "actual_result": "",
    }


def _score_records(records: Iterable[Mapping[str, Any]], prefix: str) -> dict[str, Any]:
    briers, log_losses, correct, confidences, confidence_hits = [], [], [], [], []
    evaluated = 0
    for row in records:
        actual = outcome_from_score(row.get("actual_home_goals"), row.get("actual_away_goals"))
        probs = _valid_probabilities({
            "home_win": row.get(f"{prefix}_home_win"),
            "draw": row.get(f"{prefix}_draw"),
            "away_win": row.get(f"{prefix}_away_win"),
        })
        if actual is None or probs is None:
            continue
        evaluated += 1
        actual_vector = {name: 1.0 if name == actual else 0.0 for name in OUTCOMES}
        p = [probs["home_win"], probs["draw"], probs["away_win"]]
        y = [actual_vector[name] for name in OUTCOMES]
        briers.append(sum((pi - yi) ** 2 for pi, yi in zip(p, y)))
        actual_probability = probs["home_win"] if actual == "home" else probs["draw"] if actual == "draw" else probs["away_win"]
        log_losses.append(-log(max(actual_probability, 1e-15)))
        picked = max(probs, key=probs.get)
        confidence = probs[picked]
        confidences.append(confidence)
        confidence_hits.append(1.0 if picked == actual else 0.0)
        correct.append(picked == actual)
    return {
        "matches": evaluated,
        "accuracy_pct": round(sum(correct) / evaluated * 100, 2) if evaluated else None,
        "multiclass_brier": round(sum(briers) / evaluated, 5) if evaluated else None,
        "log_loss": round(sum(log_losses) / evaluated, 5) if evaluated else None,
        "mean_top_outcome_confidence_pct": round(sum(confidences) / evaluated * 100, 2) if evaluated else None,
        "top_outcome_hit_rate_pct": round(sum(confidence_hits) / evaluated * 100, 2) if evaluated else None,
    }


def evaluate_prediction_ledger(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Compare model vs Opta on identical completed fixtures; report coverage."""
    rows = [dict(row) for row in records]
    eligible = [row for row in rows if str(row.get("prediction_before_kickoff", "")).lower() in ("true", "1")]
    completed = [row for row in eligible if outcome_from_score(
        row.get("actual_home_goals"), row.get("actual_away_goals")
    ) is not None]
    opta_rows = [
        row for row in completed
        if _valid_probabilities({
            "home_win": row.get("opta_home_win"), "draw": row.get("opta_draw"),
            "away_win": row.get("opta_away_win"),
        }) is not None
        and _parse_datetime(row.get("opta_captured_at")) is not None
        and _parse_datetime(row.get("kickoff_at")) is not None
        and _parse_datetime(row.get("opta_captured_at")) < _parse_datetime(row.get("kickoff_at"))
    ]
    player_snapshots = [row for row in eligible if str(
        row.get("player_snapshot_before_kickoff", "")
    ).lower() in ("true", "1")]
    return {
        "records_total": len(rows),
        "pre_match_predictions": len(eligible),
        "completed_pre_match_predictions": len(completed),
        "player_snapshots_pre_kickoff": len(player_snapshots),
        "player_snapshot_competitions": len({
            str(row.get("competition") or "") for row in player_snapshots
        }),
        "player_snapshot_coverage_by_competition": {
            competition: sum(1 for row in player_snapshots
                             if str(row.get("competition") or "") == competition)
            for competition in sorted({str(row.get("competition") or "")
                                        for row in player_snapshots})
        },
        "model_metrics_by_competition": {
            competition: _score_records(
                [row for row in completed if str(row.get("competition") or "") == competition],
                "model",
            )
            for competition in sorted({str(row.get("competition") or "") for row in completed})
        },
        "model": _score_records(completed, "model"),
        "opta_same_fixtures": _score_records(opta_rows, "opta"),
        "opta_comparable_fixtures": len(opta_rows),
        "opta_comparison_note": "Opta is scored only on the exact same completed fixtures as the model.",
    }


def merge_prediction_records(
    existing: Iterable[Mapping[str, Any]], incoming: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Merge exported ledgers by stable record ID without overwriting known outcomes."""
    merged: dict[str, dict[str, Any]] = {}
    for row in list(existing) + list(incoming):
        record = dict(row)
        key = str(record.get("record_id") or "")
        if not key:
            continue
        if key not in merged:
            merged[key] = record
            continue
        for field, value in record.items():
            if value not in (None, ""):
                merged[key][field] = value
    return list(merged.values())
