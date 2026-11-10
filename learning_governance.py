"""Fail-closed model promotion and post-release monitoring policy.

This module is an offline decision helper. It never deploys, changes a model,
writes to production, or rolls back automatically.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Mapping

POLICY_VERSION = "football-model-governance-v1"
MINIMUM_TOTAL_FIXTURES = 200
MINIMUM_VALIDATION_FIXTURES = 50
MINIMUM_TEST_FIXTURES = 50
MINIMUM_RELATIVE_BRIER_IMPROVEMENT = 0.02
MAXIMUM_RELATIVE_LOG_LOSS_REGRESSION = 0.01
MAXIMUM_CALIBRATION_ERROR_REGRESSION = 0.01
MONITORING_MINIMUM_WINDOW_MATCHES = 30
MONITORING_WARNING_DEGRADATION = 0.15
MONITORING_ROLLBACK_DEGRADATION = 0.30


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _metric(report: Mapping[str, Any], split: str, model: str, key: str) -> float | None:
    results = report.get("results")
    if not isinstance(results, Mapping):
        return None
    partition = results.get(split)
    if not isinstance(partition, Mapping):
        return None
    metrics = partition.get(model)
    if not isinstance(metrics, Mapping):
        return None
    return _number(metrics.get(key))


def assess_promotion(
    experiment_report: Mapping[str, Any],
    candidate: Mapping[str, Any],
    approval: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate evidence and explicit approval; fail closed on missing fields."""
    approval = approval if isinstance(approval, Mapping) else {}
    gate = experiment_report.get("sample_gate")
    gate = gate if isinstance(gate, Mapping) else {}
    train_count = _number(gate.get("valid_targets_by_split", {}).get("train")) if isinstance(gate.get("valid_targets_by_split"), Mapping) else None
    validation_count = _number(gate.get("valid_targets_by_split", {}).get("validation")) if isinstance(gate.get("valid_targets_by_split"), Mapping) else None
    test_count = _number(gate.get("valid_targets_by_split", {}).get("test")) if isinstance(gate.get("valid_targets_by_split"), Mapping) else None
    counts_valid = all(value is not None and value >= 0 for value in (train_count, validation_count, test_count))
    total = (train_count + validation_count + test_count) if counts_valid else 0

    reasons: list[str] = []
    if experiment_report.get("status") != "ready_for_offline_comparison":
        reasons.append("offline_experiment_not_ready")
    if not counts_valid or total < MINIMUM_TOTAL_FIXTURES:
        reasons.append("insufficient_total_verified_fixtures")
    if not counts_valid or validation_count < MINIMUM_VALIDATION_FIXTURES:
        reasons.append("insufficient_validation_fixtures")
    if not counts_valid or test_count < MINIMUM_TEST_FIXTURES:
        reasons.append("insufficient_test_fixtures")

    if candidate.get("candidate_type") != "trained_feature_model":
        reasons.append("candidate_is_not_a_trained_feature_model")
    if not str(candidate.get("model_version") or "").strip():
        reasons.append("missing_candidate_model_version")
    digest = str(candidate.get("artifact_sha256") or "").strip().lower()
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        reasons.append("missing_or_invalid_candidate_artifact_sha256")

    comparisons: dict[str, Any] = {}
    for split in ("validation", "test"):
        incumbent_brier = _metric(experiment_report, split, "incumbent", "multiclass_brier")
        candidate_brier = _metric(experiment_report, split, "candidate", "multiclass_brier")
        incumbent_log = _metric(experiment_report, split, "incumbent", "log_loss")
        candidate_log = _metric(experiment_report, split, "candidate", "log_loss")
        incumbent_cal = _metric(experiment_report, split, "incumbent", "top_outcome_calibration_error")
        candidate_cal = _metric(experiment_report, split, "candidate", "top_outcome_calibration_error")
        metrics = (incumbent_brier, candidate_brier, incumbent_log, candidate_log, incumbent_cal, candidate_cal)
        if any(value is None or value < 0 for value in metrics):
            reasons.append(f"missing_or_invalid_{split}_metrics")
            comparisons[split] = {"passed": False}
            continue
        brier_improvement = (incumbent_brier - candidate_brier) / incumbent_brier if incumbent_brier > 0 else None
        log_regression = (candidate_log - incumbent_log) / incumbent_log if incumbent_log > 0 else None
        calibration_delta = candidate_cal - incumbent_cal
        passed = (
            brier_improvement is not None
            and brier_improvement >= MINIMUM_RELATIVE_BRIER_IMPROVEMENT
            and log_regression is not None
            and log_regression <= MAXIMUM_RELATIVE_LOG_LOSS_REGRESSION
            and calibration_delta <= MAXIMUM_CALIBRATION_ERROR_REGRESSION
        )
        comparisons[split] = {
            "relative_brier_improvement": round(brier_improvement, 6) if brier_improvement is not None else None,
            "relative_log_loss_regression": round(log_regression, 6) if log_regression is not None else None,
            "calibration_error_delta": round(calibration_delta, 6),
            "passed": passed,
        }
        if not passed:
            reasons.append(f"{split}_performance_gate_failed")

    if not str(approval.get("approved_by") or "").strip():
        reasons.append("missing_human_approval")
    if not _timestamp(approval.get("approved_at")):
        reasons.append("missing_or_invalid_approval_timestamp")
    if approval.get("rollback_plan_confirmed") is not True:
        reasons.append("rollback_plan_not_confirmed")
    if approval.get("monitoring_plan_confirmed") is not True:
        reasons.append("monitoring_plan_not_confirmed")

    passed = not reasons
    return {
        "policy_version": POLICY_VERSION,
        "decision": "eligible_for_manual_release_review" if passed else "blocked",
        "promotion_authorized": False,
        "candidate_model_version": candidate.get("model_version"),
        "sample_counts": {
            "train": train_count, "validation": validation_count,
            "test": test_count, "total": total,
        },
        "comparisons": comparisons,
        "reasons": reasons,
        "note": (
            "Passing this checklist is not an automated deployment authorization. "
            "A separate release owner must review the evidence and execute deployment."
        ),
    }


def evaluate_monitoring_window(window: Mapping[str, Any]) -> dict[str, Any]:
    """Classify a completed production window against its fixed release reference."""
    matches = _number(window.get("matches"))
    current_brier = _number(window.get("multiclass_brier"))
    reference_brier = _number(window.get("reference_multiclass_brier"))
    current_log = _number(window.get("log_loss"))
    reference_log = _number(window.get("reference_log_loss"))
    reasons: list[str] = []
    if not str(window.get("model_version") or "").strip():
        reasons.append("missing_model_version")
    if matches is None or matches < MONITORING_MINIMUM_WINDOW_MATCHES:
        reasons.append("insufficient_monitoring_window")
    values = (current_brier, reference_brier, current_log, reference_log)
    if any(value is None or value <= 0 for value in values):
        reasons.append("missing_or_invalid_monitoring_metrics")
    if reasons:
        return {
            "policy_version": POLICY_VERSION,
            "status": "insufficient_evidence",
            "rollback_recommended": False,
            "reasons": reasons,
        }

    brier_ratio = current_brier / reference_brier
    log_ratio = current_log / reference_log
    worst_ratio = max(brier_ratio, log_ratio)
    if worst_ratio >= 1.0 + MONITORING_ROLLBACK_DEGRADATION:
        status = "rollback_review_required"
        rollback = True
    elif worst_ratio >= 1.0 + MONITORING_WARNING_DEGRADATION:
        status = "degradation_warning"
        rollback = False
    else:
        status = "within_monitoring_thresholds"
        rollback = False
    return {
        "policy_version": POLICY_VERSION,
        "status": status,
        "model_version": window.get("model_version"),
        "matches": int(matches),
        "brier_degradation_ratio": round(brier_ratio, 6),
        "log_loss_degradation_ratio": round(log_ratio, 6),
        "rollback_recommended": rollback,
        "automatic_rollback_performed": False,
        "reasons": [],
        "note": "A rollback recommendation requires human review; this evaluator never changes production.",
    }
