# Layer 5 — Leakage-Safe Learning Dataset

**Implementation:** `learning_dataset.py`  
**Dataset schema:** `football-learning-dataset-v1`  
**Accepted feature schema:** `prediction-features-v1`

## Purpose

The builder converts prediction-ledger records into a deterministic, fixture-deduplicated JSON dataset for offline experiments. It is intentionally separate from production prediction inference and does not train or promote a model.

## Eligibility rules

A row is accepted only when all of the following are true:

- It has a stable prediction record ID and a fixture ID from Sportmonks or one of the five supported free fixture providers.
- The prediction timestamp is valid and strictly before kickoff.
- The result has the exact independently verified provider-specific verification marker, matching result provider and source fixture ID, valid verification timestamp, and a valid non-negative integer final 90-minute score. Free-source fixture IDs must match the ledger's provider-namespaced ID.
- The versioned feature snapshot is valid JSON with schema `prediction-features-v1`.
- The snapshot timestamp is valid, no later than the prediction timestamp, and strictly before kickoff.
- Both team feature objects and the calculated feature object are present.
- The snapshot contains valid 1X2 baseline probabilities and no NaN/Infinity values.

The builder recomputes eligibility from timestamps and verification fields. It does not trust imported boolean flags. It never reconstructs historical features from current provider data.

## Deduplication and conflicts

- When canonical league, season, home-team and away-team IDs are present, one row is retained per canonical fixture identity across providers.
- Otherwise, one row is retained per provider-scoped fixture identity.
- The latest eligible pre-kickoff forecast is selected.
- If timestamps tie, the lexicographically smallest stable record ID wins.
- If independently verified rows for one fixture disagree on the final score, the entire fixture is excluded.
- Rows without reliable fixture identity are excluded.

## Feature/target separation

The feature vector contains the captured team inputs and calculated component features. The baseline 1X2 probabilities are kept in a separate `baseline_probabilities` field for later calibration comparisons.

Actual goals, actual outcome, result verification metadata, and other post-kickoff ledger fields are never copied into the feature vector. Actual goals and outcome are included only under the separate `target` object.

## Chronological partitions

Unique fixtures are sorted by kickoff time and fixture identity, then partitioned in chronological order:

- 70% training
- 15% validation
- 15% test

The split manifest stores fixture identities, making overlap and ordering auditable. Very small datasets may have empty validation or test partitions; they are not silently randomized.

## Sample gate and production safety

The default minimum of 30 unique verified fixtures is only a gate for beginning offline experiments. It is not evidence of model validity, calibration, or production readiness.

The export always sets `production_promotion_permitted` to false. The builder does not change model weights, provider priorities, TVD logic, recency policy, or live prediction behavior.

## Usage

The module API accepts an iterable of ledger mappings:

```python
from learning_dataset import build_learning_dataset, export_learning_dataset

dataset = build_learning_dataset(ledger_records)
export_learning_dataset(ledger_records, "reports/learning_dataset/latest.json")
```

For an offline JSON ledger export, use:

```bash
python learning_dataset.py --input ledger.json --output reports/learning_dataset/latest.json
```

The input can be a JSON list of ledger records or an object containing a `records` list. No database credentials or paid services are required by this module.

## Current data limitation

The latest live audit found 74 ledger records but zero rows currently pass all learning gates: 65 lack a valid result-verification timestamp, four are not pre-kickoff predictions, four use unsupported fixture providers in the prior implementation, and one lacks a feature snapshot. The free-provider verification path is now supported, but only exact source-ID/team/competition/season/90-minute-score verification is accepted. The offline experiment remains blocked until at least 30 unique canonical fixtures have eligible pre-kickoff snapshots and verified results.
