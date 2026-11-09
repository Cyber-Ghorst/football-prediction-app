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
            and bool(snapshot.get("players"))
        ),
        "team_snapshot_before_kickoff": bool(
            kickoff and snapshot_at and snapshot_at < kickoff
            and any(team.get("season_statistics") for team in
                    (snapshot.get("teams") or {}).values())
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
        picked_key = max(probs, key=probs.get)
        picked = {"home_win": "home", "draw": "draw", "away_win": "away"}[picked_key]
        confidence = probs[picked_key]
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


def _verified_actual_score(row: Mapping[str, Any]) -> tuple[int, int] | None:
    """Accept only scores carrying the exact automatic Sportmonks verification trail."""
    if str(row.get("actual_result_verification") or "") != (
        "exact_fixture_team_competition_season_and_score"
    ):
        return None
    if str(row.get("actual_result_provider") or "").casefold() != "sportmonks":
        return None
    if str(row.get("fixture_provider") or "").casefold() != "sportmonks":
        return None
    fixture_id = str(row.get("fixture_id") or "").strip()
    verified_fixture_id = str(row.get("actual_result_fixture_id") or "").strip()
    if not fixture_id or verified_fixture_id != fixture_id:
        return None
    if _parse_datetime(row.get("actual_result_verified_at")) is None:
        return None
    if outcome_from_score(row.get("actual_home_goals"), row.get("actual_away_goals")) is None:
        return None
    try:
        return int(row["actual_home_goals"]), int(row["actual_away_goals"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def _is_before_kickoff(row: Mapping[str, Any], timestamp_field: str) -> bool:
    kickoff = _parse_datetime(row.get("kickoff_at"))
    observed = _parse_datetime(row.get(timestamp_field))
    return bool(kickoff and observed and observed < kickoff)


def _fixture_identity(row: Mapping[str, Any]) -> str | None:
    kickoff = _parse_datetime(row.get("kickoff_at"))
    if kickoff is None:
        return None
    provider = str(row.get("fixture_provider") or "").strip().casefold()
    fixture_id = str(row.get("fixture_id") or "").strip()
    if provider and fixture_id:
        return f"id:{provider}:{fixture_id}"
    parts = (
        str(row.get("competition") or "").strip().casefold(),
        str(row.get("country") or "").strip().casefold(),
        str(row.get("season") or "").strip(),
        str(row.get("home_team") or "").strip().casefold(),
        str(row.get("away_team") or "").strip().casefold(),
        kickoff.isoformat(),
    )
    if not all(parts):
        return None
    return "fixture:" + "|".join(parts)


def _json_player_records(row: Mapping[str, Any]) -> bool:
    try:
        value = json.loads(row.get("player_snapshot_players_json") or "[]")
    except (TypeError, ValueError):
        return False
    return isinstance(value, list) and bool(value)


def _json_team_season_records(row: Mapping[str, Any]) -> bool:
    try:
        value = json.loads(row.get("player_snapshot_teams_json") or "{}")
    except (TypeError, ValueError):
        return False
    return isinstance(value, dict) and any(
        isinstance(team, dict) and bool(team.get("season_statistics"))
        for team in value.values()
    )


def evaluate_prediction_ledger(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Evaluate one latest valid pre-kickoff forecast per identifiable fixture.

    Timestamp fields and serialized snapshot contents are the source of truth;
    imported boolean flags are not trusted for leakage protection.
    """
    rows = [dict(row) for row in records]
    eligibility_audit = {
        "records_total": len(rows),
        "invalid_probabilities": 0,
        "missing_prediction_timestamp": 0,
        "missing_kickoff_timestamp": 0,
        "at_or_after_kickoff": 0,
        "valid_pre_kickoff_records": 0,
    }
    timestamp_eligible = []
    for row in rows:
        probabilities = _valid_probabilities({
            "home_win": row.get("model_home_win"),
            "draw": row.get("model_draw"),
            "away_win": row.get("model_away_win"),
        })
        if probabilities is None:
            eligibility_audit["invalid_probabilities"] += 1
            continue
        predicted_at = _parse_datetime(row.get("predicted_at"))
        if predicted_at is None:
            eligibility_audit["missing_prediction_timestamp"] += 1
            continue
        kickoff_at = _parse_datetime(row.get("kickoff_at"))
        if kickoff_at is None:
            eligibility_audit["missing_kickoff_timestamp"] += 1
            continue
        if predicted_at >= kickoff_at:
            eligibility_audit["at_or_after_kickoff"] += 1
            continue
        eligibility_audit["valid_pre_kickoff_records"] += 1
        timestamp_eligible.append(row)

    # Repeated runs for the same fixture must not inflate the backtest sample.
    # Keep the latest valid pre-match forecast for each fixture identity.
    latest_by_fixture: dict[str, dict[str, Any]] = {}
    unidentifiable: list[dict[str, Any]] = []
    for row in timestamp_eligible:
        identity = _fixture_identity(row)
        if identity is None:
            unidentifiable.append(row)
            continue
        previous = latest_by_fixture.get(identity)
        current_time = _parse_datetime(row.get("predicted_at"))
        previous_time = _parse_datetime(previous.get("predicted_at")) if previous else None
        if previous is None or (current_time and (previous_time is None or current_time > previous_time)):
            latest_by_fixture[identity] = row

    eligible = list(latest_by_fixture.values())
    score_present = [
        row for row in eligible
        if outcome_from_score(row.get("actual_home_goals"), row.get("actual_away_goals")) is not None
    ]
    completed = [row for row in score_present if _verified_actual_score(row) is not None]
    unverified_score_rows = [row for row in score_present if _verified_actual_score(row) is None]
    opta_rows = [
        row for row in completed
        if _valid_probabilities({
            "home_win": row.get("opta_home_win"), "draw": row.get("opta_draw"),
            "away_win": row.get("opta_away_win"),
        }) is not None
        and _is_before_kickoff(row, "opta_captured_at")
    ]

    # One chronological row per identifiable, completed pre-match fixture.
    # This is descriptive history only; it never feeds the prediction engine.
    performance_history = []
    for row in completed:
        probabilities = _valid_probabilities({
            "home_win": row.get("model_home_win"),
            "draw": row.get("model_draw"),
            "away_win": row.get("model_away_win"),
        })
        actual = outcome_from_score(
            row.get("actual_home_goals"), row.get("actual_away_goals")
        )
        if probabilities is None or actual is None:
            continue
        picked_key = max(probabilities, key=probabilities.get)
        picked = {
            "home_win": "home", "draw": "draw", "away_win": "away"
        }[picked_key]
        one_match = _score_records([row], "model")
        performance_history.append({
            "kickoff_at": str(row.get("kickoff_at") or ""),
            "predicted_at": str(row.get("predicted_at") or ""),
            "competition": str(row.get("competition") or "Unknown"),
            "home_team": str(row.get("home_team") or "Unknown"),
            "away_team": str(row.get("away_team") or "Unknown"),
            "score": f"{row.get('actual_home_goals')}-{row.get('actual_away_goals')}",
            "actual_outcome": actual,
            "predicted_outcome": picked,
            "correct": picked == actual,
            "top_confidence_pct": round(probabilities[picked_key] * 100, 2),
            "brier": one_match["multiclass_brier"],
            "log_loss": one_match["log_loss"],
        })
    performance_history.sort(
        key=lambda item: _parse_datetime(item["kickoff_at"]) or datetime.min.replace(tzinfo=timezone.utc)
    )
    player_snapshots = [
        row for row in eligible
        if _is_before_kickoff(row, "player_snapshot_at") and _json_player_records(row)
    ]
    team_snapshots = [
        row for row in eligible
        if _is_before_kickoff(row, "player_snapshot_at") and _json_team_season_records(row)
    ]
    eligibility_audit.update({
        "unidentifiable_pre_match_records": len(unidentifiable),
        "duplicate_records_excluded": len(timestamp_eligible) - len(eligible) - len(unidentifiable),
        "unique_pre_match_fixtures": len(eligible),
        "completed_with_verified_scores": len(completed),
        "scores_present_but_unverified": len(unverified_score_rows),
        "awaiting_valid_score": len(eligible) - len(score_present),
    })
    return {
        "records_total": len(rows),
        "eligibility_audit": eligibility_audit,
        "pre_match_prediction_records": len(timestamp_eligible),
        "pre_match_predictions": len(eligible),
        "duplicate_records_excluded": len(timestamp_eligible) - len(eligible) - len(unidentifiable),
        "unidentifiable_pre_match_records": len(unidentifiable),
        "completed_pre_match_predictions": len(completed),
        "unverified_score_records": len(unverified_score_rows),
        "player_snapshots_pre_kickoff": len(player_snapshots),
        "team_snapshots_pre_kickoff": len(team_snapshots),
        "team_snapshot_competitions": len({str(row.get("competition") or "") for row in team_snapshots}),
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
        "performance_history": performance_history,
        "opta_same_fixtures": _score_records(opta_rows, "opta"),
        "opta_comparable_fixtures": len(opta_rows),
        "opta_comparison_note": "Opta is scored only on the same deduplicated completed fixtures as the model.",
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
            if value is None or value == "":
                continue
            try:
                if value != value:  # pandas/numpy NaN from imported CSV cells
                    continue
            except (TypeError, ValueError):
                pass
            merged[key][field] = value
    return list(merged.values())
