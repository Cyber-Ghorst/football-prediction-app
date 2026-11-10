# Layer 5 — Immutable Prediction-Time Feature Snapshots

**Implementation:** `prediction-features-v1`

Each newly generated forecast now stores a JSON feature snapshot in its existing prediction-ledger record. The snapshot is created from the same `home`, `away`, `result` and tactical override values passed to the production prediction call.

## Captured information

- The first ten recent matches for each side, including goals for, goals against and opponent strength (the match inputs consumed by the current engine).
- Home/away rating, player-availability score and the tactical ratings consumed by the engine.
- Available source/provenance metadata already present on each team profile.
- Calculated component ratings, tactical subcomponent ratings, configured model weights, compatibility values, data coverage, expected goals and forecast probabilities.
- Capture timestamp, feature schema version and the existing latest-five 60% / previous-five 40% recency policy.

Unknown numeric values remain JSON `null`; non-finite values are not silently serialized. The snapshot is stored alongside the prediction probabilities in `feature_snapshot_json`.

## Integrity and timing

- The snapshot is captured at the same timestamp used as `predicted_at`.
- `feature_snapshot_before_kickoff` is true only when the capture timestamp is valid, no later than the prediction timestamp, and strictly before kickoff.
- Snapshot fields are immutable under repeated writes for the same stable prediction record ID. Later updates can add outcomes and other missing metadata, but cannot replace the original feature snapshot.
- Existing ledger records are not backfilled from current provider data. Their historical features remain unavailable rather than being reconstructed with hindsight.
- The snapshot is versioned so future schema changes can coexist with older records.

## Current limitations

- Existing predictions do not acquire feature snapshots retroactively.
- Source provenance is recorded only when those metadata fields are present in the team profiles. The current engine inputs do not consistently expose a complete per-statistic source timestamp, so the snapshot must not be treated as proof that every underlying provider field had independently verified provenance.
- This change only records training evidence. It does not train a model, alter inference, change weights, change provider priorities, or promote candidate models.

## Next step

Build a deterministic learning-dataset exporter that accepts only unique pre-kickoff predictions with valid versioned feature snapshots and independently verified final outcomes. It must use chronological splits and reject post-kickoff or unverified data before any training experiment.
