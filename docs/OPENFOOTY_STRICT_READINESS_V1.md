# OpenFooty v1 strict readiness adapter

## Scope and ownership

`openfooty_readiness.py` consumes the validated `openfooty-prediction-data-v1` response in the prediction app. The engine remains the owner of collection, canonical data, normalization and source provenance. The app owns readiness decisions.

This module is an offline, read-only assessment. It does not call providers, access either repository's database, create prediction scores, call `predict_match`, write the prediction ledger, or enable the live path.

## Pinned contract source

- Engine repository: `OpenFooty-Data-Engine/OpenFooty-Data-Engine`
- Engine main revision reviewed for this adapter: `9aa4179b3abf13e0086a18a247e3d659d9655036`
- Contract: `openfooty-prediction-data-v1`
- App schema: `contracts/prediction-data-response.v1.schema.json`
- App golden response: `contracts/examples/prediction-data-response.v1.example.json`

Contract changes require coordinated updates and cross-repository compatibility tests; the app must not silently fork the engine schema.

## Readiness rules

The adapter preserves the response's request ID, contract version, fixture identity, status and diagnostics. It rejects request-correlation or structural failures through the existing contract validator.

The assessment fails closed when:
- the response is not `DATA_AVAILABLE`, the fixture is not scheduled, or engine diagnostics contain missing, invalid or conflicting observations;
- fixture or availability freshness policy is not supplied, provenance is not eligible, timestamps are invalid/future, or evidence exceeds its caller-supplied age limit;
- fewer than five valid pre-kickoff history rows exist, history is not newest-first, or any history row is at/after kickoff;
- opponent-strength coverage or recent-match statistics are absent;
- availability is unknown/unverified or a validated availability impact score is not available;
- the approved home/away rating or tactical evidence is absent.

The caller must supply separate maximum-age limits for fixture evidence, availability evidence and every recent-match history row. No default age threshold is invented. The current v1 response contains recent-match venue labels and raw statistics, but does not define an approved home/away score, player-availability impact score, playing-style score, defensive-structure score, attacking-approach score or fixture-specific tactical-compatibility score. The adapter therefore reports those components as missing; it does not invent calculations.

## Fixed model policy

The adapter reports the existing seven top-level components and four tactical subcomponents. It does not alter weights, redistribute missing weights, impute values, or change the latest-five 60% / previous-five 40% recency policy. Tactical compatibility remains fixture-specific.

## Activation status

This PR adds the assessment and offline tests only. It does not wire the assessment into live fixture selection or prediction execution. Prediction execution and ledger writes remain disabled for this integration milestone.
