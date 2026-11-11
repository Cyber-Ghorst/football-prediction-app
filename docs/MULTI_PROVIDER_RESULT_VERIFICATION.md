# Multi-provider result verification

The scheduled result synchronizer now supports promoted fixtures from OpenLigaDB, LiveScoreFootball and Bzzoiro in addition to the existing Sportmonks path.

## Verification requirements

- The prediction ledger must contain a provider-scoped fixture ID and a past, timezone-aware kickoff.
- The CockroachDB football_fixture_sources provenance link must exist for the exact provider fixture ID.
- The source API response must identify the exact fixture ID, home and away teams, competition, season and a completed match.
- The source must provide an unambiguous regulation-time/full-time score. Ambiguous extra-time, penalty-shootout or incomplete score payloads are not written.
- Existing manual or previously stored scores are never overwritten.

OpenLigaDB results are selected from the explicit full-time result type, not by array position. LiveScoreFootball requires a completed event with an explicit full-time detail and rejects extra-time/penalty detail. Bzzoiro requires a finished event and an explicit full-time score object; it does not infer a score from commentary or a score string.

Open Matchday is supported through its paired results_<season>.csv dataset. The results file is treated as a finished-match source, and the synchronizer requires the same deterministic fixture identity, exact teams/competition/season/kickoff, explicit ft_home/ft_away values and a consistent ft_result. Cup competitions are excluded because the CSV does not expose separate extra-time/penalty fields. OpenFootball result verification is conditional on the exact fixture having been promoted from a row with an explicit timezone offset or IANA timezone. The synchronizer refetches the same season JSON and requires the same deterministic fixture key, exact source teams/competition/season/kickoff and an explicit score.ft pair. Rows with naive kickoff times, missing FT scores or extra-time/penalty data are not promoted or evaluated.

## Credentials and schedule

- OpenLigaDB: public API; no credential.
- LiveScoreFootball: public read endpoint; optional LIVESCORE_FOOTBALL_BASE_URL selects the verified host.
- Bzzoiro: BZZOIRO_API_TOKEN is required.
- PROVIDER_DATABASE_URL is required to resolve provider provenance.
- DATABASE_URL is the Neon prediction ledger.

The lab controller's scheduled result-sync operation passes these credentials to sync_prediction_results.py. Result collection updates only blank actual-result fields and then recalculates evaluation metrics from the saved prediction/result pairs. It does not alter prediction probabilities, model weights, recency policy, TVD or training data.
