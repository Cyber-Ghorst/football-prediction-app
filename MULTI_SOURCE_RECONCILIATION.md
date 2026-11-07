# Multi-source reconciliation implementation

## Scope of this milestone

This change adds a provider-neutral reconciliation function for two or more
already-normalized match records, plus a Sportmonks fixture normalizer that
produces the same canonical shape as the existing API Ninjas, Highlightly,
API-Football and LiveScoreFootball normalizers.

Files:
- `multi_source_reconciliation.py` — strict multi-record reconciliation.
- `sportmonks_canonical.py` — Sportmonks fixture normalization.
- `test_multi_source_reconciliation.py` — agreement, conflict, freshness,
  duplicate-source and identity safety tests.
- `test_sportmonks_canonical.py` — participant, score, state and identity tests.

## Reconciliation rules

1. At least two provider records are required.
2. Every record must match the anchor on the explicitly mapped competition key,
   season, home/away team identities and kickoff within five minutes.
3. Duplicate records from one provider reject the group; a provider cannot vote
   more than once.
4. Each provider must have a fetched-at timestamp supplied by the caller or
   attached to the normalized record. Missing timestamps are ineligible, not
   silently treated as fresh.
5. Fields are resolved independently using the existing `PROVIDER_ORDER`.
6. Sportmonks is preferred for supported current-season fields. API-Football
   remains subject to the user's 2022–2024 plan restriction.
7. LiveScoreFootball remains excluded unless the caller explicitly supplies
   `livescore_verified=True` after exact competition/season and freshness
   validation.
8. Agreement and disagreement are both reported with provider names and
   source IDs. Values are never averaged.
9. Missing values remain unknown. No failed, stale or null source can erase a
   valid observation.

## Activation boundary

This is a unit-test-covered reconciliation layer (the latest CI run has not yet been confirmed), not yet an automatic live multi-provider
fetch path in Streamlit. The app currently builds its prediction profiles from
Sportmonks for seasons after 2024 and API-Football for supported historical
seasons. API Ninjas and Highlightly remain connected diagnostic/adaptor sources.

Before the reconciliation layer is allowed to influence a prediction, the app
must have validated competition and season crosswalks for each source, verified
team identity mappings, fetched-at timestamps, and match-level coverage. The
Sportmonks season ID must never be equated to another provider's ID. A provider
that cannot be mapped unambiguously is skipped and shown as unavailable.

The prediction engine, component weights, 60/40 recency rule, Layer 1 and TVD
are not changed by this milestone.
