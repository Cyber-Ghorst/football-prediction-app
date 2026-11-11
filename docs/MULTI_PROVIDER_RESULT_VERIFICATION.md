# Multi-provider result verification

The scheduled result synchronizer now supports promoted fixtures from OpenLigaDB, LiveScoreFootball and Bzzoiro in addition to the existing Sportmonks path.

## Verification requirements

- The prediction ledger must contain a provider-scoped fixture ID and a past, timezone-aware kickoff.
- The CockroachDB football_fixture_sources provenance link must exist for the exact provider fixture ID.
- The source API response must identify the exact fixture ID, home and away teams, competition, season and a completed match.
- The source must provide an unambiguous regulation-time/full-time score. Ambiguous extra-time, penalty-shootout or incomplete score payloads are not written.
- Existing manual or previously stored scores are never overwritten.

OpenLigaDB results are selected from the explicit full-time result type, not by array position. LiveScoreFootball requires a completed event with an explicit full-time detail and rejects extra-time/penalty detail. Bzzoiro requires a finished event and an explicit full-time score object; it does not infer a score from commentary or a score string.

OpenFootball and Open Matchday remain unsupported as automatic result sources in this implementation. Their future-fixture observations can be promoted only after the normal crosswalk/licence checks, but the result synchronizer will not invent a result endpoint or infer scores from static schedules.

## Credentials and schedule

- OpenLigaDB: public API; no credential.
- LiveScoreFootball: public read endpoint; optional LIVESCORE_FOOTBALL_BASE_URL selects the verified host.
- Bzzoiro: BZZOIRO_API_TOKEN is required.
- PROVIDER_DATABASE_URL is required to resolve provider provenance.
- DATABASE_URL is the Neon prediction ledger.

The lab controller's scheduled result-sync operation passes these credentials to sync_prediction_results.py. Result collection updates only blank actual-result fields and then recalculates evaluation metrics from the saved prediction/result pairs. It does not alter prediction probabilities, model weights, recency policy, TVD or training data.
