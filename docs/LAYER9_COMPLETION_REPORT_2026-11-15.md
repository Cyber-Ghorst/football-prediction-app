# Layer 9 — independent prediction benchmark completion report

**Review date:** 2026-11-15  
**Status:** Implementation and live persistence verification complete; benchmark scoring remains descriptive and sample-dependent.

## Scope delivered

Layer 9 adds TipMaster National crowd consensus as an independent, free, read-only benchmark. It is intentionally a human-consensus comparator, not an independently calibrated statistical model.

The implementation merged through:
- PR #147 — isolated TipMaster feed adapter and provenance validation.
- PR #148 — dedicated Neon persistence and same-fixture benchmark evaluation.
- PR #150 — remote controller operation for live feed and Neon round-trip verification.
- PR #152 — Streamlit benchmark refresh diagnostics and smoke coverage.
- PR #153 — daily scheduled refresh and persistence verification.

PR #149 was superseded by the merged diagnostics work in PR #151/#152 and is not required as a separate merge.

## Live verification — 2026-11-15

The manual `tipmaster_refresh_verify` controller operation completed successfully.

| Check | Result |
|---|---:|
| TipMaster feed | Connected |
| Raw records received | 242 |
| Valid records accepted | 17 |
| Records rejected by adapter validation | 225 |
| Records already stored before refresh | 34 |
| New records saved | 17 |
| Records reloaded after save | 34 |
| Incoming source IDs missing after reload | 0 |
| Prediction ledger touched | No |
| Workflow | Success |

The successful round trip confirms that all 17 accepted source IDs were present after reload. The 34 reloaded records include the previously stored records plus the new observations; they are not 34 new records.

Run: https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43751892160

## Evaluation and interpretation safeguards

- Evaluation compares only the latest valid pre-kickoff model prediction for a fixture with an exact, independently verified final score.
- Matching requires normalized competition, home team, away team and kickoff within 15 minutes. Ambiguous matches are excluded.
- Each cohort is evaluated only on its own uniquely matched fixtures. Missing TipMaster coverage is not counted as a miss.
- Reported measures include cohort hit rate, distributional Brier score, distributional log loss, mean cohort size and model metrics on the same fixture subset.
- TipMaster shares are crowd-agreement distributions, not calibrated probabilities. They must not be described as probability calibration or treated as ground truth.
- The comparison is descriptive only. No benchmark values are used for training, tuning, prediction inputs, model probabilities, weights, recency weighting, feature snapshots or TVD.

## Ongoing observation

The daily refresh workflow is configured for 07:13 East Africa Time, with manual refresh also available. The live controller round trip above verifies the feed and Neon persistence path. The number of completed fixtures eligible for same-fixture scoring will grow only as benchmarked matches finish and the independent result-verification pipeline confirms their scores. A small or zero matched sample is a coverage limitation, not a reason to weaken fixture matching or infer results.

## Closeout decision

Layer 9's source adapter, isolated persistence, conservative same-fixture evaluator, dashboard diagnostics, scheduled refresh and live remote persistence verification are complete. Continue accumulating observations and report the actual eligible comparison sample; do not change the prediction model based on this benchmark.
