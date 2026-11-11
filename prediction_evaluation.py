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
BINARY_MARKET_FIELDS = ("over_1_5", "over_2_5", "btts_yes")


def _valid_binary_probability(value: Any) -> float | None:
    try:
        probability = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(probability) or not 0.0 <= probability <= 100.0:
        return None
    return probability / 100.0


def _score_binary_market(
    records: Iterable[Mapping[str, Any]],
    field: str,
    target,
) -> dict[str, Any]:
    briers, log_losses, correct, confidences = [], [], [], []
    for row in records:
        score = _verified_actual_score(row)
        probability = _valid_binary_probability(row.get(field))
        if score is None or probability is None:
            continue
        actual = 1.0 if target(*score) else 0.0
        predicted = 1.0 if probability >= 0.5 else 0.0
        briers.append((probability - actual) ** 2)
        selected_probability = probability if actual == 1.0 else 1.0 - probability
        log_losses.append(-log(max(selected_probability, 1e-15)))
        correct.append(predicted == actual)
        confidences.append(max(probability, 1.0 - probability))
    count = len(briers)
    return {
        "matches": count,
        "accuracy_pct": round(sum(correct) / count * 100.0, 2) if count else None,
        "brier": round(sum(briers) / count, 5) if count else None,
        "log_loss": round(sum(log_losses) / count, 5) if count else None,
        "mean_binary_confidence_pct": round(sum(confidences) / count * 100.0, 2) if count else None,
    }


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


def build_availability_snapshot(
    *,
    home_profile: Mapping[str, Any],
    away_profile: Mapping[str, Any],
    fixture_id: str | int | None,
    season_id: int | str,
    home_team_id: int | str,
    away_team_id: int | str,
    captured_at: str | None = None,
) -> dict[str, Any] | None:
    """Capture the exact Sportmonks availability evidence used for a fixture.

    A team is complete only when its roster, team-season identity, fixture
    identity, sidelined feed and scored player assessment all pass validation.
    Partial evidence is retained for audit but cannot count as a complete
    pre-kickoff snapshot.
    """
    if fixture_id in (None, ""):
        return None
    captured = captured_at or datetime.now(timezone.utc).isoformat()
    teams: dict[str, dict[str, Any]] = {}
    players: list[dict[str, Any]] = []
    complete_teams = 0

    for side, profile, expected_team_id in (
        ("home", home_profile, home_team_id),
        ("away", away_profile, away_team_id),
    ):
        profile = profile if isinstance(profile, Mapping) else {}
        evidence = profile.get("availability")
        assessment = profile.get("player_availability_assessment") if isinstance(profile, Mapping) else None
        evidence = evidence if isinstance(evidence, Mapping) else {}
        assessment = assessment if isinstance(assessment, Mapping) else {}
        squad_players = evidence.get("squad_players")
        valid_identity = (
            str(evidence.get("fixture_id") or "") == str(fixture_id)
            and str(evidence.get("team_id") or "") == str(expected_team_id)
            and str(evidence.get("season_id") or "") == str(season_id)
        )
        try:
            availability_score = float(assessment.get("score"))
        except (TypeError, ValueError):
            availability_score = None
        valid_roster = (
            evidence.get("roster_complete") is True
            and evidence.get("sidelined_feed_available") is True
            and isinstance(squad_players, list)
            and bool(squad_players)
            and assessment.get("status") == "scored"
            and availability_score is not None
            and isfinite(availability_score)
            and 0 <= availability_score <= 100
        )
        seen_player_ids: set[str] = set()
        normalized_players: list[dict[str, Any]] = []
        if isinstance(squad_players, list):
            for player in squad_players:
                if not isinstance(player, Mapping):
                    valid_roster = False
                    break
                player_id = str(player.get("player_id") or "").strip()
                status = str(player.get("status") or "").casefold()
                try:
                    importance = float(player.get("importance"))
                except (TypeError, ValueError):
                    valid_roster = False
                    break
                if (
                    not player_id or player_id in seen_player_ids
                    or status not in {"available", "unavailable"}
                    or not isfinite(importance) or not 0 <= importance <= 100
                ):
                    valid_roster = False
                    break
                seen_player_ids.add(player_id)
                normalized_players.append({
                    "player_id": player_id,
                    "player_name": player.get("player_name"),
                    "status": status,
                    "importance": round(importance, 2),
                    "minutes_played": player.get("minutes_played"),
                    "minutes_evidence_method": player.get("minutes_evidence_method"),
                })
        complete = bool(valid_identity and valid_roster)
        if complete:
            complete_teams += 1
            for player in normalized_players:
                players.append({
                    **player,
                    "side": side,
                    "team_id": str(expected_team_id),
                    "team_name": str(profile.get("name") or profile.get("team_name") or side),
                })
        teams[side] = {
            "team_id": str(expected_team_id),
            "team_name": str(profile.get("name") or profile.get("team_name") or side),
            "fixture_id": str(evidence.get("fixture_id") or ""),
            "season_id": str(evidence.get("season_id") or ""),
            "roster_complete": complete,
            "sidelined_feed_available": evidence.get("sidelined_feed_available") is True,
            "availability_score": assessment.get("score") if complete else None,
            "players": normalized_players if complete else [],
            "reported_sidelined_count": evidence.get("reported_sidelined_count"),
            "reason": (
                evidence.get("reason") if valid_identity and not valid_roster
                else "Fixture, team or season identity did not match the selected prediction."
                if not valid_identity else None
            ),
        }

    status = "complete" if complete_teams == 2 else "partial" if complete_teams == 1 else "unknown"
    return {
        "source": "sportmonks",
        "captured_at": captured,
        "fixture_id": str(fixture_id),
        "season_id": str(season_id),
        "status": status,
        "complete_teams": complete_teams,
        "teams": teams,
        "players": players,
    }


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
    league_id: str | int | None = None,
    season_id: str | int | None = None,
    home_team_id: str | int | None = None,
    away_team_id: str | int | None = None,
    opta_probabilities: Mapping[str, Any] | None = None,
    opta_source_url: str | None = None,
    opta_captured_at: str | None = None,
    player_snapshot: Mapping[str, Any] | None = None,
    availability_snapshot: Mapping[str, Any] | None = None,
    feature_snapshot: Mapping[str, Any] | None = None,
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
    availability = dict(availability_snapshot or {})
    features = dict(feature_snapshot or {})
    feature_snapshot_json = json.dumps(features, ensure_ascii=False, separators=(",", ":"), allow_nan=False) if features else ""
    availability_at = _parse_datetime(availability.get("captured_at"))
    availability_teams = availability.get("teams")
    availability_teams = availability_teams if isinstance(availability_teams, Mapping) else {}
    availability_complete = (
        availability.get("status") == "complete"
        and availability.get("complete_teams") == 2
        and all(
            isinstance(availability_teams.get(side), Mapping)
            and availability_teams[side].get("roster_complete") is True
            for side in ("home", "away")
        )
    )
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
        "league_id": str(league_id or ""),
        "season_id": str(season_id or ""),
        "home_team_id": str(home_team_id or ""),
        "away_team_id": str(away_team_id or ""),
        "model_version": "weighted-football-model-v1",
        "model_recency_policy": "latest_5_60pct_previous_5_40pct",
        "feature_snapshot_schema_version": str(features.get("schema_version") or "") if features else "",
        "feature_snapshot_at": str(features.get("captured_at") or created) if features else "",
        "feature_snapshot_before_kickoff": bool(
            features and kickoff and created_dt and created_dt < kickoff
            and _parse_datetime(features.get("captured_at") or created) is not None
            and _parse_datetime(features.get("captured_at") or created) <= created_dt
            and _parse_datetime(features.get("captured_at") or created) < kickoff
        ),
        "feature_snapshot_json": feature_snapshot_json,
        "model_home_win": round(model["home_win"] * 100, 4),
        "model_draw": round(model["draw"] * 100, 4),
        "model_away_win": round(model["away_win"] * 100, 4),
        "model_over_1_5": (
            round(_valid_binary_probability(probabilities.get("over_1_5")) * 100, 4)
            if _valid_binary_probability(probabilities.get("over_1_5")) is not None else ""
        ),
        "model_over_2_5": (
            round(_valid_binary_probability(probabilities.get("over_2_5")) * 100, 4)
            if _valid_binary_probability(probabilities.get("over_2_5")) is not None else ""
        ),
        "model_btts_yes": (
            round(_valid_binary_probability(probabilities.get("btts_yes")) * 100, 4)
            if _valid_binary_probability(probabilities.get("btts_yes")) is not None else ""
        ),
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
        "availability_snapshot_at": availability.get("captured_at") or "",
        "availability_snapshot_before_kickoff": bool(
            kickoff and availability_at and availability_at < kickoff and availability_complete
        ),
        "availability_snapshot_status": availability.get("status", "unknown"),
        "availability_snapshot_players_count": len(availability.get("players") or []),
        "availability_snapshot_json": json.dumps(availability, ensure_ascii=False, separators=(",", ":")),
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


def _json_complete_availability_snapshot(row: Mapping[str, Any]) -> bool:
    try:
        value = json.loads(row.get("availability_snapshot_json") or "{}")
    except (TypeError, ValueError):
        return False
    teams = value.get("teams") if isinstance(value, dict) else None
    return bool(
        isinstance(value, dict)
        and value.get("status") == "complete"
        and value.get("complete_teams") == 2
        and isinstance(teams, dict)
        and all(
            isinstance(teams.get(side), dict)
            and teams[side].get("roster_complete") is True
            and bool(teams[side].get("players"))
            for side in ("home", "away")
        )
    )


def _top_outcome_calibration(
    records: Iterable[Mapping[str, Any]],
    prefix: str = "model",
) -> dict[str, Any]:
    """Summarize top-outcome confidence against observed hit rate by bucket."""
    boundaries = ((0, 40), (40, 50), (50, 60), (60, 70), (70, 80), (80, 90), (90, 100.0001))
    buckets = [
        {"lower": lower, "upper": upper, "confidences": [], "hits": []}
        for lower, upper in boundaries
    ]
    total = 0
    for row in records:
        actual = outcome_from_score(row.get("actual_home_goals"), row.get("actual_away_goals"))
        probabilities = _valid_probabilities({
            "home_win": row.get(f"{prefix}_home_win"),
            "draw": row.get(f"{prefix}_draw"),
            "away_win": row.get(f"{prefix}_away_win"),
        })
        if actual is None or probabilities is None:
            continue
        predicted_key = max(probabilities, key=probabilities.get)
        predicted_outcome = {
            "home_win": "home", "draw": "draw", "away_win": "away"
        }[predicted_key]
        confidence_pct = probabilities[predicted_key] * 100.0
        for bucket in buckets:
            if bucket["lower"] <= confidence_pct < bucket["upper"]:
                bucket["confidences"].append(confidence_pct)
                bucket["hits"].append(1.0 if predicted_outcome == actual else 0.0)
                total += 1
                break

    rows = []
    for bucket in buckets:
        count = len(bucket["confidences"])
        lower, upper = bucket["lower"], bucket["upper"]
        label = f"{lower}–{int(upper)}%" if upper < 100 else "90–100%"
        mean_confidence = (
            round(sum(bucket["confidences"]) / count, 2) if count else None
        )
        hit_rate = (
            round(sum(bucket["hits"]) / count * 100.0, 2) if count else None
        )
        rows.append({
            "confidence_bucket": label,
            "matches": count,
            "mean_confidence_pct": mean_confidence,
            "observed_hit_rate_pct": hit_rate,
            "absolute_calibration_gap_pct": (
                round(abs(mean_confidence - hit_rate), 2)
                if mean_confidence is not None and hit_rate is not None else None
            ),
            "sample_status": "sparse" if 0 < count < 20 else "populated" if count >= 20 else "empty",
        })
    return {
        "method": "top predicted outcome confidence compared with observed hit rate",
        "matches": total,
        "bins": rows,
        "note": (
            "Descriptive reliability view only. Empty or sparse bins do not establish "
            "calibration; accumulate more independently verified completed fixtures "
            "before drawing calibration conclusions."
        ),
    }


MINIMUM_DESCRIPTIVE_EVALUATION_FIXTURES = 30


def _evaluation_sample_assessment(verified_fixture_count: int) -> dict[str, Any]:
    """Label evaluation evidence without implying that a small sample validates the model."""
    count = max(0, int(verified_fixture_count))
    if count == 0:
        status = "no_verified_results"
        message = "No independently verified completed pre-kickoff fixtures are available; model performance is not yet measurable."
    elif count < MINIMUM_DESCRIPTIVE_EVALUATION_FIXTURES:
        status = "insufficient_sample"
        message = (
            f"Only {count} unique verified fixture(s) are available. Treat accuracy, "
            "Brier score and log loss as highly provisional; do not claim model "
            "accuracy or calibration from this sample."
        )
    else:
        status = "descriptive_sample"
        message = (
            f"{count} unique verified fixtures are available. Metrics are descriptive "
            "monitoring evidence only; this threshold does not establish calibration, "
            "generalization or predictive reliability."
        )
    return {
        "status": status,
        "verified_unique_fixtures": count,
        "minimum_descriptive_fixtures": MINIMUM_DESCRIPTIVE_EVALUATION_FIXTURES,
        "message": message,
    }


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
    availability_snapshots = [
        row for row in eligible
        if _is_before_kickoff(row, "availability_snapshot_at")
        and _json_complete_availability_snapshot(row)
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
        "availability_snapshots_pre_kickoff": len(availability_snapshots),
        "availability_snapshot_coverage_by_competition": {
            competition: sum(
                1 for row in availability_snapshots
                if str(row.get("competition") or "") == competition
            )
            for competition in sorted({
                str(row.get("competition") or "") for row in availability_snapshots
            })
        },
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
        "evaluation_sample_assessment": _evaluation_sample_assessment(len(completed)),
        "model": _score_records(completed, "model"),
        "market_metrics": {
            "over_1_5": _score_binary_market(
                completed, "model_over_1_5", lambda home, away: home + away >= 2
            ),
            "over_2_5": _score_binary_market(
                completed, "model_over_2_5", lambda home, away: home + away >= 3
            ),
            "btts_yes": _score_binary_market(
                completed, "model_btts_yes", lambda home, away: home > 0 and away > 0
            ),
        },
        "top_outcome_calibration": _top_outcome_calibration(completed, "model"),
        "confidence_bucket_hit_rate": _top_outcome_calibration(completed, "model")["bins"],
        "performance_history": performance_history,
        "opta_same_fixtures": _score_records(opta_rows, "opta"),
        "opta_comparable_fixtures": len(opta_rows),
        "opta_comparison_note": "Opta is scored only on the same deduplicated completed fixtures as the model.",
    }


IMMUTABLE_PREDICTION_FIELDS = frozenset({
    "feature_snapshot_schema_version", "feature_snapshot_at",
    "feature_snapshot_before_kickoff", "feature_snapshot_json",
})


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
            if field in IMMUTABLE_PREDICTION_FIELDS and merged[key].get(field) not in (None, ""):
                continue
            if value is None or value == "":
                continue
            try:
                if value != value:  # pandas/numpy NaN from imported CSV cells
                    continue
            except (TypeError, ValueError):
                pass
            merged[key][field] = value
    return list(merged.values())


def _benchmark_text_key(value: Any) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def evaluate_tipmaster_benchmark(
    records: Iterable[Mapping[str, Any]],
    benchmark_records: Iterable[Mapping[str, Any]],
    *,
    kickoff_tolerance_minutes: int = 15,
) -> dict[str, Any]:
    """Score TipMaster crowd shares against verified results on exact matched fixtures.

    Fixture matching requires exact normalized competition, home and away names,
    plus kickoff within the configured tolerance. Ambiguous matches are excluded.
    Shares are crowd agreement distributions, not calibrated probabilities.
    This function is descriptive only and is never called by prediction code.
    """
    if kickoff_tolerance_minutes < 0:
        raise ValueError("kickoff_tolerance_minutes cannot be negative.")

    rows = [dict(row) for row in records]
    timestamp_eligible = []
    for row in rows:
        probs = _valid_probabilities({
            "home_win": row.get("model_home_win"),
            "draw": row.get("model_draw"),
            "away_win": row.get("model_away_win"),
        })
        predicted_at = _parse_datetime(row.get("predicted_at"))
        kickoff = _parse_datetime(row.get("kickoff_at"))
        if probs is None or predicted_at is None or kickoff is None or predicted_at >= kickoff:
            continue
        timestamp_eligible.append(row)

    latest_by_fixture: dict[str, dict[str, Any]] = {}
    for row in timestamp_eligible:
        identity = _fixture_identity(row)
        if not identity:
            continue
        previous = latest_by_fixture.get(identity)
        current_at = _parse_datetime(row.get("predicted_at"))
        previous_at = _parse_datetime(previous.get("predicted_at")) if previous else None
        if previous is None or (current_at and (previous_at is None or current_at > previous_at)):
            latest_by_fixture[identity] = row

    completed = [row for row in latest_by_fixture.values() if _verified_actual_score(row)]
    candidates = []
    invalid_benchmark = 0
    for raw in benchmark_records:
        item = dict(raw)
        if item.get("source") != "tipmaster" or item.get("prediction_inputs_eligible") is not False:
            invalid_benchmark += 1
            continue
        kickoff = _parse_datetime(item.get("kickoff_at"))
        locked = _parse_datetime(item.get("prediction_locked_at"))
        groups = item.get("groups")
        if kickoff is None or locked is None or locked >= kickoff or not isinstance(groups, dict):
            invalid_benchmark += 1
            continue
        candidates.append(item)

    used_ids: set[str] = set()
    matched_pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    ambiguous = 0
    for prediction in completed:
        pred_kickoff = _parse_datetime(prediction.get("kickoff_at"))
        pred_key = (
            _benchmark_text_key(prediction.get("competition")),
            _benchmark_text_key(prediction.get("home_team")),
            _benchmark_text_key(prediction.get("away_team")),
        )
        if pred_kickoff is None or not all(pred_key):
            continue
        matches = []
        for item in candidates:
            source_id = str(item.get("source_match_id") or "")
            if not source_id or source_id in used_ids:
                continue
            item_key = (
                _benchmark_text_key(item.get("competition")),
                _benchmark_text_key(item.get("home_team")),
                _benchmark_text_key(item.get("away_team")),
            )
            item_kickoff = _parse_datetime(item.get("kickoff_at"))
            if item_key != pred_key or item_kickoff is None:
                continue
            delta = abs((item_kickoff - pred_kickoff).total_seconds()) / 60.0
            if delta <= kickoff_tolerance_minutes:
                matches.append(item)
        if len(matches) > 1:
            ambiguous += 1
            continue
        if len(matches) == 1:
            chosen = matches[0]
            used_ids.add(str(chosen["source_match_id"]))
            matched_pairs.append((prediction, chosen))

    group_rows: dict[str, list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]] = {}
    for prediction, item in matched_pairs:
        actual = outcome_from_score(
            prediction.get("actual_home_goals"), prediction.get("actual_away_goals")
        )
        if actual is None:
            continue
        for group_id, group in item.get("groups", {}).items():
            if not isinstance(group, dict):
                continue
            shares = group.get("shares")
            if not isinstance(shares, dict):
                continue
            try:
                probs = {name: float(shares[name]) for name in OUTCOMES}
            except (KeyError, TypeError, ValueError):
                continue
            if any(not isfinite(value) or value < 0 or value > 1 for value in probs.values()):
                continue
            if abs(sum(probs.values()) - 1.0) > 0.02:
                continue
            group_rows.setdefault(str(group_id), []).append((prediction, item, {
                "probs": probs, "actual": actual, "sample": int(group.get("sample") or 0)
            }))

    metrics = {}
    for group_id, observations in sorted(group_rows.items()):
        briers, losses, correct, samples = [], [], [], []
        model_rows = []
        for prediction, item, observation in observations:
            probs = observation["probs"]
            actual = observation["actual"]
            briers.append(sum(
                (probs[outcome] - (1.0 if outcome == actual else 0.0)) ** 2
                for outcome in OUTCOMES
            ))
            losses.append(-log(max(probs[actual], 1e-15)))
            correct.append(max(probs, key=probs.get) == actual)
            samples.append(observation["sample"])
            model_rows.append(prediction)
        metrics[group_id] = {
            "matches": len(observations),
            "crowd_consensus_accuracy_pct": round(sum(correct) / len(correct) * 100.0, 2),
            "distributional_brier": round(sum(briers) / len(briers), 5),
            "distributional_log_loss": round(sum(losses) / len(losses), 5),
            "mean_cohort_size": round(sum(samples) / len(samples), 1),
            "model_same_fixtures": _score_records(model_rows, "model"),
            "interpretation": "Crowd agreement distribution only; not calibrated probabilities.",
        }

    return {
        "source": "TipMaster National consensus",
        "source_url": "https://tipmaster.de/agents/",
        "matched_verified_fixtures": len(matched_pairs),
        "completed_verified_model_fixtures": len(completed),
        "unmatched_verified_fixtures": max(0, len(completed) - len(matched_pairs)),
        "ambiguous_fixture_matches_excluded": ambiguous,
        "invalid_benchmark_records_excluded": invalid_benchmark,
        "kickoff_tolerance_minutes": kickoff_tolerance_minutes,
        "groups": metrics,
        "prediction_inputs_eligible": False,
        "note": (
            "TipMaster outcome shares represent crowd agreement, not calibrated "
            "probabilities. Scores are descriptive and calculated only on the "
            "same uniquely matched fixtures with exact Sportmonks-verified results. "
            "No benchmark value enters prediction generation, model weights or TVD."
        ),
    }
