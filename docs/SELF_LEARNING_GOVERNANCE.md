# Layer 5 — Model Promotion and Monitoring Governance

**Implementation:** `learning_governance.py`  
**Policy schema:** `football-model-governance-v1`

## Safety boundary

This module is a fail-closed decision helper. It does not deploy, modify, activate, or roll back production models. A passing assessment means only **eligible for manual release review**. A release owner must separately review the evidence and perform any deployment through the established release process.

The current outcome-frequency candidate from `learning_experiments.py` is explicitly a diagnostic baseline, not a trained feature model. It is rejected by the promotion policy. Production inference remains unchanged.

## Promotion gates

A candidate is blocked unless all requirements are met:

- At least 200 independently verified unique fixtures overall.
- At least 50 fixtures in validation and 50 in the untouched chronological test partition.
- Candidate is identified as a trained feature model and has a model version and valid SHA-256 artifact digest.
- Both validation and test show at least 2% relative multiclass Brier improvement over the incumbent.
- Relative log-loss regression is no worse than 1% on either holdout.
- Top-outcome calibration error does not worsen by more than 0.01 on either holdout.
- A named human approver and timestamp are supplied.
- Rollback and monitoring plans are explicitly confirmed.

Metrics must be finite and non-negative. Missing evidence fails closed. These thresholds are conservative initial release-policy defaults, not claims that a model is statistically superior. Results still require expert review, sufficient competition/season coverage, and scrutiny for selection bias and data quality.

## API

```python
from learning_governance import assess_promotion

decision = assess_promotion(
    experiment_report,
    candidate={
        "candidate_type": "trained_feature_model",
        "model_version": "candidate-v2",
        "artifact_sha256": "<64-character SHA-256 digest>",
    },
    approval={
        "approved_by": "named release owner",
        "approved_at": "2026-11-10T12:00:00+00:00",
        "rollback_plan_confirmed": True,
        "monitoring_plan_confirmed": True,
    },
)
```

The returned `promotion_authorized` is always false. A passing decision is a checklist result for a separate manual release review.

## Post-release monitoring

Call `evaluate_monitoring_window` with a completed, fixture-deduplicated performance window and a fixed reference metric set from the approved champion/release baseline:

```python
from learning_governance import evaluate_monitoring_window

status = evaluate_monitoring_window({
    "model_version": "champion-v1",
    "matches": 40,
    "multiclass_brier": 0.52,
    "reference_multiclass_brier": 0.50,
    "log_loss": 0.95,
    "reference_log_loss": 0.90,
})
```

- Fewer than 30 completed verified fixtures: `insufficient_evidence`.
- 15% or greater degradation in either Brier or log loss: `degradation_warning`.
- 30% or greater degradation in either metric: `rollback_review_required`.
- Otherwise: `within_monitoring_thresholds`.

The reference values must be fixed before the monitoring window is evaluated; do not choose a more favorable reference after seeing results. Monitoring windows must use verified outcomes, one scored prediction per fixture, consistent metric definitions, and a documented model version. Evaluate consecutive, non-overlapping windows where practical.

A rollback recommendation is not an automatic rollback. A human release owner should inspect data/provider incidents, sample composition, calibration and recent match coverage, then use the existing release mechanism to revert if warranted. This module does not yet provide a persistent monitoring store, alert delivery, deployment integration, or automatic rollback.

## Current project readiness

- Immutable pre-kickoff feature snapshots: implemented.
- Leakage-safe chronological dataset export: implemented.
- Offline incumbent/reference comparison: implemented.
- Promotion checklist and monitoring-window evaluator: implemented here.
- Live candidate training, sufficient matured snapshot-bearing verified fixtures, automated monitoring ingestion, alert delivery and deployment/rollback integration: not yet established.

Do not promote any candidate until those evidence and operational gaps are closed. No production weights, provider priorities, TVD rules, tactical recency policy, or inference behavior are changed by this module.
