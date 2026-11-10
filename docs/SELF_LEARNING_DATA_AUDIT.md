# Layer 5 — Self-Learning Data Audit

**Audit date:** 2026-11-10  
**Audited branch:** `main` at `6d3d5326b9c52c627078837ef9e288bd5a4e3e55`

## Executive summary

The application already records predictions, persists them in Neon, synchronizes verified final scores, and computes descriptive performance metrics. This is a strong foundation for a self-learning system, but the current evidence volume is not sufficient to train or validate a more adaptive model.

The latest archived `reports/prediction_performance/latest.json` report, generated at `2026-11-10T11:19:44Z`, reports:

| Measure | Observed |
|---|---:|
| Saved prediction records | 74 |
| Records with valid pre-kickoff timestamps and probabilities | 66 |
| Unique pre-match fixtures after deduplication | 21 |
| Duplicate records excluded | 45 |
| Completed fixtures with independently verified scores | 1 |
| Fixtures awaiting a valid score | 20 |
| Pre-kickoff player snapshots | 0 |
| Pre-kickoff team snapshots | 0 |

The one verified fixture is not a meaningful training or validation sample. The report correctly labels the evidence as insufficient and warns against claims about accuracy or calibration.

**Important access limitation:** these counts come from the latest archived report in the repository, not a fresh direct query of the live Neon database. The live database credential is held in deployment secrets and was not accessed during this audit.

## Existing data and infrastructure

### Prediction ledger

- `prediction_storage.py` persists records in Neon/PostgreSQL using a JSONB payload and stable `record_id`.
- The app loads and saves the ledger through `load_prediction_ledger` and `save_prediction_records`.
- `prediction_evaluation.py::build_prediction_record` stores the forecast probabilities for 1X2 and selected binary markets, fixture identity, competition, teams, season, prediction timestamp, kickoff, model version and recency policy.
- Player/team snapshots and a detailed availability snapshot can also be serialized into a prediction record.
- `merge_prediction_records` preserves known non-empty fields when merging repeated records.

### Verified outcomes

- `prediction_results.py` accepts only completed Sportmonks fixtures with matching fixture ID, home/away team identity, competition and season, and an unambiguous final 90-minute score.
- `sync_prediction_results.py` updates only blank outcome fields and records the verification provider, fixture ID, timestamp and verification reason.
- The evaluator rejects manually entered or otherwise unverified scores from model metrics.
- Repeated forecasts for one fixture are deduplicated for evaluation, retaining the latest valid pre-kickoff forecast.

### Existing evaluation

`evaluate_prediction_ledger` already calculates:
- 1X2 accuracy, multiclass Brier score and log loss;
- selected binary-market metrics;
- top-outcome confidence calibration buckets;
- competition-level descriptive metrics;
- a sample-size status, with 30 unique verified fixtures as the minimum for descriptive monitoring (not model validation).

This is evaluation and monitoring only. It does not train the model or feed changes back into prediction generation.

### Prediction feature computation

`engine.py::predict_match` returns useful internal evidence including:
- home and away component ratings;
- tactical component ratings;
- model weights;
- tactical compatibility used;
- expected goals and output probabilities;
- data-coverage weights.

However, `build_prediction_record` currently receives the probabilities and snapshots, not the full engine result or a versioned feature vector. The saved ledger therefore does not consistently preserve the exact component values and feature provenance that produced each forecast.

## Gaps to close before learning

1. **Persist an immutable feature snapshot for each forecast.** Store the exact pre-match component values, tactical subcomponents, known/missing indicators, data coverage, source provenance and timestamps used by that prediction. Never reconstruct historical inputs from current provider data.
2. **Keep prediction-time information separate from outcomes.** Outcome fields must never enter the feature vector. All feature timestamps must be before kickoff, and training data must be built with chronological cutoffs.
3. **Increase verified outcome coverage.** The current one-fixture verified sample is insufficient. Continue collecting predictions and automatically verified results; do not train from unverified or duplicate fixtures.
4. **Separate training from production inference.** A candidate learner must be trained offline and must not modify the active model, weights, provider priority, TVD logic or recency policy.
5. **Add walk-forward validation and a promotion gate.** Candidate versions must be tested on later, unseen fixtures against the unchanged baseline. Require adequate sample size and improvement in proper scoring rules (especially log loss and Brier score), not accuracy alone.
6. **Track model versions and rollback.** Every forecast must identify its model version and feature schema version. Promotion must be explicit, auditable and reversible.

## Recommended implementation sequence

### Objective 1 — Audit (this document)
Document existing ledger, outcome verification, evaluation and missing feature history.

### Objective 2 — Immutable prediction feature snapshots
Extend the ledger to capture the exact engine component outputs and feature provenance at prediction time. Add schema/version fields and tests for missing values, timestamps, duplicate records and serialization. Keep inference unchanged.

### Objective 3 — Learning dataset builder
Build a deterministic, leakage-safe dataset from uniquely identified forecasts with verified outcomes. Enforce pre-kickoff feature timestamps and chronological train/validation/test partitions.

### Objective 4 — Offline baseline and candidate experiments
Establish a reproducible baseline and test a small, interpretable calibration/learning candidate. Do not enable automatic weight changes.

### Objective 5 — Promotion and monitoring
Compare candidates on unseen chronological data, enforce sample and performance gates, version the approved model, and support rollback.

## Protected constraints

- No paid services or subscriptions; the project budget remains $0.
- Preserve the existing model weights: recent form 20%, goals scored 10%, goals conceded 10%, home/away 10%, strength of schedule 15%, player availability 5%, tactical analysis 30%.
- Preserve the tactical subweights and latest-five 60% / previous-five 40% recency policy.
- Do not alter provider priorities, TVD rules or production predictions during the audit and feature-snapshot objectives.
- Missing, stale, ambiguous or unverified data remains unknown; never silently impute it as zero.
- No automatic model promotion without chronological out-of-sample validation.

## Conclusion

The app has prediction memory and outcome verification, but it does not yet have a safe training loop. The immediate engineering priority is to save a faithful, immutable record of the exact features used for each prediction. Once the app accumulates enough verified results, it can learn and test candidate improvements without allowing unvalidated changes to affect live forecasts.
