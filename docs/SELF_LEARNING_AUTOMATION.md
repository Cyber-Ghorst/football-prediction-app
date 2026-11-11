# Automated learning-readiness audit

The Prediction Lab Controller now runs a read-only learning audit after scheduled
verified-result synchronization. It is also available as the manual
`learning_audit` controller operation.

The audit reads the Neon prediction ledger through
`load_prediction_ledger`, applies the existing leakage-safe
`build_learning_dataset` eligibility and chronological split rules, and runs
the existing offline baseline comparison only when its minimum sample gate is
met.

The archived summary contains ledger counts, excluded-record reasons,
independently verified unique fixture counts, chronological split counts and
offline experiment status/metrics. It does not publish raw ledger records or
feature vectors.

## Safety

- Reads the ledger only; writes no prediction or result records.
- Uses only independently verified outcomes and immutable pre-kickoff
  `prediction-features-v1` snapshots.
- Keeps outcomes outside the feature vector and partitions fixtures
  chronologically.
- The offline candidate is a training-only smoothed outcome prior, not a
  feature-trained production model.
- `production_promotion_permitted` remains false.
- Live prediction weights, tactical recency, TVD and inference remain
  unchanged.

A successful audit with fewer than 30 unique verified fixtures remains
`insufficient_sample`; it is a readiness report, not evidence of predictive
quality. The sample gate itself is not a production-promotion gate.
