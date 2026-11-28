# Prediction Engine Integrity Audit

**Audit date:** 2026-11-28  
**Audited branch:** `main` immediately after Blacksmith CI migration PR #603  
**Scope:** `engine.py`, `test_engine.py`, the prediction call path in `app.py`, and the existing self-learning audit.

## Executive finding

The agreed numeric model weights and recency policy are present in code and have regression tests. However, the engine currently produces a forecast when weighted inputs are missing by renormalizing the weights of the available inputs. The same behavior occurs inside the tactical subscore. The output reports known-weight coverage, but this is diagnostic only: it does not gate prediction generation.

This means a forecast can be produced using an effective weighting scheme different from the agreed scheme, while the returned `model_weights` still displays the original agreed weights. This is not a change to the constants; it is a change to their effective influence when data is incomplete.

**No production model code or weights were changed during this audit.** A policy decision is needed before changing prediction eligibility.

## Findings

### P1 — Missing components silently change effective weights

In `engine.py::_rating`, the weighted sum is divided by the sum of weights for only the known components. If tactical is known, its full 30% is also included; if tactical is unknown, the remaining known components are rescaled to 100%.

In `engine.py::_tactical_rating`, known tactical subcomponents are divided by the sum of their own weights. For example, if only playing style (6%) and attacking approach (7%) are present, those two inputs are rescaled to represent the entire 30% tactical component.

The engine returns `data_coverage.home_known_weight` and `away_known_weight`, but `predict_match` does not require full coverage or apply a readiness threshold. The app displays coverage and still records the prediction.

**Impact:** missingness changes effective model influence. The static `model_weights` output can be mistaken for the weights actually applied.

**Recommendation:** define component-level requiredness and a prediction-readiness policy before changing this behavior. Keep original weights fixed; do not silently redistribute missing weight. The policy must explicitly state which missing components block a forecast, which permit a labelled partial forecast (if any), and whether any tactical subcomponent is mandatory.

### P1 — Strength-of-schedule recency weights can shift when values are missing

`_weighted_optional` first removes missing values into indexed pairs, then constructs recency weights from the compacted list rather than each value's original match index. If early/recent matches are missing, an older value can receive a latest-five weight.

**Impact:** the 60% latest-five / 40% previous-five policy can be applied to the wrong matches for optional opponent-strength observations.

**Recommendation:** retain each observation's original match index when assigning recency weights. Add tests for missing values in both the latest five and previous five. Do not replace missing opponent-strength values with zero.

### P1 — Feature snapshot is not yet a complete match-level provenance record

`build_prediction_feature_snapshot` records up to ten goals-for, goals-against and opponent-strength values, plus a limited set of team-level provenance strings. It does not retain per-match fixture IDs, kickoff timestamps, venue, source identifiers, source update timestamps, or the individual match-level provenance needed to independently reconstruct the exact historical feature window.

**Impact:** the snapshot is useful but cannot always prove which source observations and match ordering produced a historical feature.

**Recommendation:** extend the versioned snapshot schema in a separate change to preserve stable match identity, kickoff, home/away context and source provenance for every contributing observation. Keep raw source evidence immutable and distinguish missing from invalid data.

### P2 — Input validation does not cover all model inputs consistently

`_validate_team` checks that at least five matches exist and that goals are present and non-negative. It does not consistently validate finite numeric ranges for venue ratings, player availability, opponent strength, tactical compatibility, or the shape/type of every match record. Invalid optional values may be dropped or may fail later during numeric conversion.

`_snapshot_number` converts non-numeric and non-finite values to `None`, which preserves an unknown value in the snapshot but does not explain whether the source was missing, malformed, or non-finite.

**Impact:** malformed input can be conflated with ordinary missingness, or fail late with a less actionable error.

**Recommendation:** validate every supplied numeric input at the boundary; preserve a distinct validation diagnostic for absent, malformed, out-of-range and non-finite values. Never coerce malformed data to a valid score.

### P2 — Forecast generation is not readiness-gated

The current minimum history check is five completed matches, with ten recommended in the error text. It is not a complete readiness contract for the weighted components. The app calls `predict_match`, then builds and persists a ledger record whenever the function returns successfully.

**Impact:** a forecast may be saved despite substantial missing weighted evidence.

**Recommendation:** implement an explicit readiness result before the forecast/ledger write. Store the readiness decision, component coverage, missing reasons and policy version with the prediction. A blocked fixture should not be written as an ordinary eligible prediction.

## Confirmed constraints

The code and tests currently contain the agreed constants:

| Component | Weight |
|---|---:|
| Recent form | 20% |
| Goals scored | 10% |
| Goals conceded | 10% |
| Home/away | 10% |
| Strength of schedule | 15% |
| Player availability | 5% |
| Tactical analysis | 30% |

Tactical subweights: playing style 6%, defensive structure 7%, attacking approach 7%, tactical compatibility 10%.

The `_weighted_recent` function applies relative weights of 1.5 to the first five supplied matches and 1.0 to the next five, yielding 60% / 40% when ten observations are present. Existing tests cover this behavior for complete ten-match arrays.

## Recommended implementation order

1. **Agree readiness policy:** define requiredness for each top-level component and tactical subcomponent, plus rules for partial forecasts. This is a product/model decision; do not infer it from current implementation.
2. **Fix the optional-observation indexing defect:** apply recency weights by original match position and add regression tests.
3. **Add explicit input validation:** reject malformed/non-finite/out-of-range values with field-specific diagnostics.
4. **Add a readiness evaluator:** calculate coverage and missing reasons without modifying weights; gate prediction and ledger persistence according to the approved policy.
5. **Upgrade immutable feature snapshots:** include match-level identities, timestamps, venue and provenance; version the schema.
6. **Backtest the readiness policy:** compare the eligible fixture population and missingness patterns before enabling it in production.

## Explicitly out of scope for this audit

- Changing any agreed weight or tactical subweight.
- Changing the 60% / 40% recency policy.
- Replacing or recalibrating the prediction formula.
- Changing TVD calculations or provider priorities.
- Imputing missing data.
- Enabling automatic learning or model-weight updates.
- Modifying the live prediction ledger or existing records.

## Decision required before readiness implementation

Please approve the intended missing-component policy. The recommended conservative default is: a forecast is **eligible only when every agreed top-level component is present for both teams and every tactical subcomponent required by the approved tactical policy is present**; otherwise it is blocked and the missing evidence is reported. If you want partial forecasts, define them as a separate, explicitly labelled mode with no weight redistribution and no mixing into the standard eligible prediction/evaluation population.
