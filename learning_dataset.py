"""Deterministic, leakage-safe export of verified prediction-learning rows.

This module is deliberately offline: callers provide ledger records and receive
an auditable dataset. It never connects to a database, trains a model, or changes
production inference.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

from prediction_evaluation import (
    _fixture_identity,
    _parse_datetime,
    _valid_probabilities,
    _verified_actual_score,
    outcome_from_score,
)

DATASET_SCHEMA_VERSION = "football-learning-dataset-v1"
FEATURE_SCHEMA_VERSION = "prediction-features-v1"
MINIMUM_OFFLINE_EXPERIMENT_FIXTURES = 30


def _load_feature_snapshot(row: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    raw = row.get("feature_snapshot_json")
    if not isinstance(raw, str) or not raw.strip():
        return None, "missing_feature_snapshot"
    try:
        snapshot = json.loads(raw)
    except (TypeError, ValueError):
        return None, "invalid_feature_snapshot_json"
    if not isinstance(snapshot, dict):
        return None, "invalid_feature_snapshot_shape"
    if snapshot.get("schema_version") != FEATURE_SCHEMA_VERSION:
        return None, "unsupported_feature_schema"
    captured_at = _parse_datetime(snapshot.get("captured_at"))
    predicted_at = _parse_datetime(row.get("predicted_at"))
    kickoff_at = _parse_datetime(row.get("kickoff_at"))
    if captured_at is None:
        return None, "invalid_snapshot_timestamp"
    if predicted_at is None or kickoff_at is None:
        return None, "invalid_prediction_or_kickoff_timestamp"
    if captured_at > predicted_at or captured_at >= kickoff_at:
        return None, "snapshot_not_strictly_pre_kickoff"
    teams = snapshot.get("teams")
    calculated = snapshot.get("calculated")
    if not isinstance(teams, dict) or not all(
        isinstance(teams.get(side), dict) for side in ("home", "away")
    ):
        return None, "incomplete_team_features"
    if not isinstance(calculated, dict):
        return None, "missing_calculated_features"
    probabilities = _valid_probabilities(calculated.get("probabilities", {}))
    if probabilities is None:
        return None, "invalid_snapshot_baseline_probabilities"

    # Keep the exact prediction-time inputs and component features, but separate
    # the baseline forecast from the feature vector. Outcome/verification fields
    # are never read from the snapshot or copied into features.
    calculated_features = {
        key: value for key, value in calculated.items() if key != "probabilities"
    }
    features = {
        "recency_policy": snapshot.get("recency_policy"),
        "teams": teams,
        "calculated": calculated_features,
    }
    try:
        # Reject NaN/Infinity and ensure the exported feature payload is JSON-safe.
        features = json.loads(json.dumps(
            features, ensure_ascii=False, allow_nan=False, sort_keys=True
        ))
    except (TypeError, ValueError, OverflowError):
        return None, "non_finite_or_non_json_feature"
    baseline = {
        "home_win": round(probabilities["home_win"] * 100.0, 6),
        "draw": round(probabilities["draw"] * 100.0, 6),
        "away_win": round(probabilities["away_win"] * 100.0, 6),
    }
    return {
        "captured_at": captured_at.isoformat(),
        "features": features,
        "baseline_probabilities": baseline,
    }, None


def _eligible_row(row: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    if str(row.get("fixture_provider") or "").strip().casefold() != "sportmonks":
        return None, "unsupported_fixture_provider"
    if not str(row.get("fixture_id") or "").strip():
        return None, "missing_fixture_id"
    if not str(row.get("record_id") or "").strip():
        return None, "missing_record_id"
    predicted_at = _parse_datetime(row.get("predicted_at"))
    kickoff_at = _parse_datetime(row.get("kickoff_at"))
    if predicted_at is None or kickoff_at is None:
        return None, "invalid_prediction_or_kickoff_timestamp"
    if predicted_at >= kickoff_at:
        return None, "prediction_not_pre_kickoff"
    verified_at = _parse_datetime(row.get("actual_result_verified_at"))
    if verified_at is None or verified_at < kickoff_at:
        return None, "missing_or_invalid_result_verification_timestamp"
    score = _verified_actual_score(row)
    if score is None:
        return None, "result_not_independently_verified"
    snapshot, snapshot_error = _load_feature_snapshot(row)
    if snapshot is None:
        return None, snapshot_error
    identity = _fixture_identity(row)
    if identity is None:
        return None, "unidentifiable_fixture"
    return {
        "record_id": str(row["record_id"]),
        "fixture_identity": identity,
        "kickoff_at": kickoff_at.isoformat(),
        "predicted_at": predicted_at.isoformat(),
        "feature_snapshot_at": snapshot["captured_at"],
        "competition": str(row.get("competition") or "Unknown"),
        "country": str(row.get("country") or ""),
        "season": str(row.get("season") or ""),
        "home_team": str(row.get("home_team") or "Unknown"),
        "away_team": str(row.get("away_team") or "Unknown"),
        "baseline_probabilities": snapshot["baseline_probabilities"],
        "features": snapshot["features"],
        "target": {
            "outcome": outcome_from_score(*score),
            "home_goals": score[0],
            "away_goals": score[1],
        },
    }, None


def build_learning_dataset(
    records: Iterable[Mapping[str, Any]],
    *,
    minimum_experiment_fixtures: int = MINIMUM_OFFLINE_EXPERIMENT_FIXTURES,
) -> dict[str, Any]:
    """Build a reproducible fixture-deduplicated dataset with chronological splits.

    The latest valid pre-kickoff snapshot for each independently verified
    Sportmonks fixture is retained. Conflicting verified scores fail closed.
    Splits are ordered by kickoff time: 70% train, 15% validation, 15% test.
    """
    if not isinstance(minimum_experiment_fixtures, int) or minimum_experiment_fixtures < 1:
        raise ValueError("minimum_experiment_fixtures must be a positive integer")

    source_rows = [dict(row) for row in records if isinstance(row, Mapping)]
    audit: dict[str, Any] = {
        "records_received": len(source_rows),
        "eligible_records_before_deduplication": 0,
        "excluded_records": 0,
        "excluded_reasons": {},
        "duplicate_fixture_records_excluded": 0,
        "conflicting_verified_fixtures_excluded": 0,
        "unique_verified_fixtures": 0,
    }
    by_fixture: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        eligible, reason = _eligible_row(row)
        if eligible is None:
            audit["excluded_records"] += 1
            audit["excluded_reasons"][reason or "unknown"] = (
                audit["excluded_reasons"].get(reason or "unknown", 0) + 1
            )
            continue
        audit["eligible_records_before_deduplication"] += 1
        by_fixture[eligible["fixture_identity"]].append(eligible)

    selected: list[dict[str, Any]] = []
    for identity, candidates in by_fixture.items():
        scores = {
            (candidate["target"]["home_goals"], candidate["target"]["away_goals"])
            for candidate in candidates
        }
        if len(scores) != 1:
            audit["conflicting_verified_fixtures_excluded"] += 1
            continue
        # Deterministic tie-break: latest forecast, then lexicographically smallest ID.
        candidates.sort(key=lambda item: (
            item["predicted_at"], item["feature_snapshot_at"], item["record_id"]
        ))
        selected.append(candidates[-1])
        audit["duplicate_fixture_records_excluded"] += len(candidates) - 1

    selected.sort(key=lambda item: (item["kickoff_at"], item["fixture_identity"]))
    count = len(selected)
    audit["unique_verified_fixtures"] = count

    # Chronological partitioning; tiny datasets are retained for inspection but
    # naturally have empty holdout partitions and cannot pass the sample gate.
    if count == 0:
        train_end = validation_end = 0
    elif count == 1:
        train_end = validation_end = 1
    else:
        train_end = max(1, min(count - 1, math.floor(count * 0.70)))
        validation_end = max(train_end, min(count, math.floor(count * 0.85)))
    for index, item in enumerate(selected):
        item["split"] = (
            "train" if index < train_end
            else "validation" if index < validation_end
            else "test"
        )

    split_ids = {
        name: [item["fixture_identity"] for item in selected if item["split"] == name]
        for name in ("train", "validation", "test")
    }
    enough_for_offline_experiment = count >= minimum_experiment_fixtures
    return {
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "split_policy": {
            "method": "chronological_by_kickoff",
            "train_fraction": 0.70,
            "validation_fraction": 0.15,
            "test_fraction": 0.15,
            "ordering": "ascending_kickoff_then_fixture_identity",
        },
        "sample_gate": {
            "minimum_fixtures_for_offline_experiment": minimum_experiment_fixtures,
            "verified_fixtures": count,
            "status": (
                "available_for_offline_experiment_only"
                if enough_for_offline_experiment else "insufficient_sample"
            ),
            "offline_experiment_allowed": enough_for_offline_experiment,
            "production_promotion_permitted": False,
            "note": (
                "Passing this sample gate permits offline experiments only; it does "
                "not establish model validity, calibration, or production readiness."
            ),
        },
        "audit": audit,
        "split_fixture_identities": split_ids,
        "rows": selected,
    }


def export_learning_dataset(
    records: Iterable[Mapping[str, Any]],
    output_path: str | Path,
    *,
    minimum_experiment_fixtures: int = MINIMUM_OFFLINE_EXPERIMENT_FIXTURES,
) -> dict[str, Any]:
    """Write a deterministic UTF-8 JSON dataset and return the exported payload."""
    dataset = build_learning_dataset(
        records, minimum_experiment_fixtures=minimum_experiment_fixtures
    )
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return dataset


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export a leakage-safe learning dataset from a prediction-ledger JSON file."
    )
    parser.add_argument("--input", required=True, help="JSON file containing a list of ledger records or an object with a records list.")
    parser.add_argument("--output", required=True, help="Destination JSON file.")
    parser.add_argument("--minimum-experiment-fixtures", type=int, default=MINIMUM_OFFLINE_EXPERIMENT_FIXTURES)
    args = parser.parse_args()
    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    records = source.get("records") if isinstance(source, dict) else source
    if not isinstance(records, list):
        parser.error("Input JSON must be a list of records or an object containing a records list.")
    dataset = export_learning_dataset(
        records, args.output,
        minimum_experiment_fixtures=args.minimum_experiment_fixtures,
    )
    print(json.dumps({
        "output": str(Path(args.output)),
        "verified_unique_fixtures": dataset["audit"]["unique_verified_fixtures"],
        "sample_status": dataset["sample_gate"]["status"],
        "split_counts": {name: len(ids) for name, ids in dataset["split_fixture_identities"].items()},
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
