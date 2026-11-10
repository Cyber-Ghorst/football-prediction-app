"""Leakage-safe offline comparison of saved forecasts and a simple prior baseline.

This module consumes only the exported learning dataset. It does not connect to
providers/databases, alter production inference, train a feature model, or
promote candidates.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping

OUTCOMES = ("home", "draw", "away")
PROBABILITY_KEYS = ("home_win", "draw", "away_win")
DEFAULT_MINIMUM_FIXTURES = 30


def _valid_distribution(values: Mapping[str, Any]) -> dict[str, float] | None:
    try:
        probs = {key: float(values[key]) / 100.0 for key in PROBABILITY_KEYS}
    except (KeyError, TypeError, ValueError):
        return None
    if any(not math.isfinite(value) or value < 0.0 or value > 1.0 for value in probs.values()):
        return None
    if abs(sum(probs.values()) - 1.0) > 0.006:
        return None
    total = sum(probs.values())
    return {key: value / total for key, value in probs.items()}


def _target(row: Mapping[str, Any]) -> str | None:
    target = row.get("target")
    outcome = target.get("outcome") if isinstance(target, Mapping) else None
    return outcome if outcome in OUTCOMES else None


def _score(rows: list[Mapping[str, Any]], probability_getter) -> dict[str, Any]:
    briers: list[float] = []
    log_losses: list[float] = []
    correct: list[bool] = []
    confidence: list[float] = []
    calibration_errors: list[float] = []
    for row in rows:
        actual = _target(row)
        probs = probability_getter(row)
        if actual is None or probs is None:
            continue
        actual_key = {"home": "home_win", "draw": "draw", "away": "away_win"}[actual]
        vector = [probs[key] for key in PROBABILITY_KEYS]
        target_vector = [1.0 if key == actual_key else 0.0 for key in PROBABILITY_KEYS]
        briers.append(sum((p - y) ** 2 for p, y in zip(vector, target_vector)))
        log_losses.append(-math.log(max(probs[actual_key], 1e-15)))
        picked_key = max(PROBABILITY_KEYS, key=lambda key: probs[key])
        picked = {"home_win": "home", "draw": "draw", "away_win": "away"}[picked_key]
        confidence.append(probs[picked_key])
        correct.append(picked == actual)
        calibration_errors.append(abs(probs[picked_key] - (1.0 if picked == actual else 0.0)))
    count = len(briers)
    return {
        "matches": count,
        "accuracy_pct": round(sum(correct) / count * 100.0, 2) if count else None,
        "multiclass_brier": round(sum(briers) / count, 6) if count else None,
        "log_loss": round(sum(log_losses) / count, 6) if count else None,
        "mean_top_outcome_confidence_pct": round(sum(confidence) / count * 100.0, 2) if count else None,
        "top_outcome_calibration_error": round(sum(calibration_errors) / count, 6) if count else None,
    }


def _training_prior(rows: list[Mapping[str, Any]], smoothing: float = 1.0) -> dict[str, float]:
    counts = {outcome: smoothing for outcome in OUTCOMES}
    for row in rows:
        actual = _target(row)
        if actual is not None:
            counts[actual] += 1.0
    total = sum(counts.values())
    return {outcome: counts[outcome] / total for outcome in OUTCOMES}


def run_offline_experiments(
    dataset: Mapping[str, Any],
    *,
    minimum_fixtures: int = DEFAULT_MINIMUM_FIXTURES,
) -> dict[str, Any]:
    """Compare the saved model with a train-only outcome-prior benchmark.

    Validation and test are scored separately. The candidate benchmark is a
    Laplace-smoothed outcome-frequency prior fitted only on the train partition.
    It is a diagnostic comparator, not a proposed production model.
    """
    if not isinstance(minimum_fixtures, int) or minimum_fixtures < 1:
        raise ValueError("minimum_fixtures must be a positive integer")
    rows = dataset.get("rows")
    if not isinstance(rows, list):
        raise ValueError("dataset must contain a rows list")
    usable = [row for row in rows if isinstance(row, Mapping)]
    counts = {
        split: sum(1 for row in usable if row.get("split") == split and _target(row) is not None)
        for split in ("train", "validation", "test")
    }
    total = sum(counts.values())
    gate_passed = total >= minimum_fixtures and counts["train"] > 0
    base = {
        "experiment_schema_version": "offline-experiments-v1",
        "status": "ready_for_offline_comparison" if gate_passed else "blocked_insufficient_sample",
        "sample_gate": {
            "minimum_fixtures": minimum_fixtures,
            "verified_fixtures": total,
            "valid_targets_by_split": counts,
            "passed": gate_passed,
        },
        "method": {
            "incumbent": "saved_prediction_time_1x2_probabilities",
            "candidate": "Laplace-smoothed training-set outcome-frequency prior",
            "candidate_fit_data": "train partition only",
            "scored_partitions": ["validation", "test"],
            "metrics": ["multiclass_brier", "log_loss", "accuracy_pct", "top_outcome_calibration_error"],
            "production_promotion_permitted": False,
        },
        "results": {},
        "interpretation": (
            "The outcome-prior candidate is a simple reference benchmark, not a feature-trained model. "
            "A small holdout is descriptive only; no production change is authorized."
        ),
    }
    if not gate_passed:
        base["results"] = {
            split: {"incumbent": None, "candidate": None}
            for split in ("validation", "test")
        }
        return base

    train_rows = [row for row in usable if row.get("split") == "train" and _target(row) is not None]
    candidate_prior = _training_prior(train_rows)
    candidate_pct = {
        "home_win": candidate_prior["home"] * 100.0,
        "draw": candidate_prior["draw"] * 100.0,
        "away_win": candidate_prior["away"] * 100.0,
    }
    base["candidate_training_prior_pct"] = {
        key: round(value, 6) for key, value in candidate_pct.items()
    }

    for split in ("validation", "test"):
        split_rows = [row for row in usable if row.get("split") == split]
        incumbent = _score(
            split_rows,
            lambda row: _valid_distribution(row.get("baseline_probabilities", {})),
        )
        candidate = _score(
            split_rows,
            lambda _row: _valid_distribution(candidate_pct),
        )
        base["results"][split] = {"incumbent": incumbent, "candidate": candidate}
    return base


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare saved pre-match forecasts with a train-only outcome-prior benchmark."
    )
    parser.add_argument("--input", required=True, help="Leakage-safe dataset JSON from learning_dataset.py.")
    parser.add_argument("--output", required=True, help="Destination experiment report JSON.")
    parser.add_argument("--minimum-fixtures", type=int, default=DEFAULT_MINIMUM_FIXTURES)
    args = parser.parse_args()
    dataset = json.loads(Path(args.input).read_text(encoding="utf-8"))
    report = run_offline_experiments(dataset, minimum_fixtures=args.minimum_fixtures)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(destination),
        "status": report["status"],
        "verified_fixtures": report["sample_gate"]["verified_fixtures"],
        "split_counts": report["sample_gate"]["valid_targets_by_split"],
        "production_promotion_permitted": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
