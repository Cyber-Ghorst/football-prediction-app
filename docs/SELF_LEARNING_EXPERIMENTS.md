# Layer 5 — Offline Baseline and Candidate Experiments

**Implementation:** `learning_experiments.py`  
**Report schema:** `offline-experiments-v1`

## Purpose

This module compares the saved prediction-time 1X2 probabilities (the incumbent) with a deliberately simple benchmark: a Laplace-smoothed outcome-frequency prior fitted on the chronological training partition only.

The candidate is a reference benchmark, not a feature-trained model or a proposed production replacement. The module is offline and uses only the JSON dataset produced by `learning_dataset.py`. It has no database/provider access and adds no third-party dependencies.

## Leakage controls

- Training labels alone determine the candidate's home/draw/away prior.
- Validation and test labels are used only for scoring, never for fitting.
- The incumbent uses the probability snapshot captured with the original prediction.
- Validation and test results are reported separately.
- Invalid probability distributions and invalid targets are excluded from metric counts.
- The report always sets `production_promotion_permitted` to false.

## Metrics

Both incumbent and candidate are scored with multiclass Brier score and log loss. Accuracy, mean top-outcome confidence and top-outcome calibration error are also reported as secondary diagnostics. Lower Brier/log-loss/calibration error is better; higher accuracy is better. Accuracy alone must not determine a model choice.

## Sample gate and interpretation

The default minimum is 30 unique verified fixtures, matching the dataset builder's offline-experiment gate. Passing it only allows a descriptive offline comparison. It does not establish statistical confidence or production readiness; small chronological holdouts remain weak evidence.

When the gate fails, the report explicitly blocks comparisons and returns null metrics rather than manufacturing evidence. The candidate is not fitted or scored.

## Current evidence limitation

The latest archived prediction-performance report in `reports/prediction_performance/latest.json` records 74 ledger records, 66 valid pre-kickoff records, 21 unique pre-match fixtures and only 1 completed fixture with a valid score. That report is an archived summary, not a fresh query of the live database, and it does not contain the raw snapshot-bearing ledger rows required by the dataset builder. It is therefore not possible to claim a real incumbent-versus-candidate backtest from that summary.

Older predictions without immutable `prediction-features-v1` snapshots are intentionally ineligible. New snapshot-bearing forecasts must mature and receive independently verified results before a credible historical experiment can run.

## Usage

First export an eligible dataset:

```bash
python learning_dataset.py --input ledger.json --output reports/learning_dataset/latest.json
```

Then run the comparison:

```bash
python learning_experiments.py \
  --input reports/learning_dataset/latest.json \
  --output reports/learning_experiments/latest.json
```

The output records the sample-gate status, train/validation/test counts, training-only candidate prior, and separate holdout metrics. No production weights, inference behavior, provider priorities, TVD rules or tactical recency policy are changed.
