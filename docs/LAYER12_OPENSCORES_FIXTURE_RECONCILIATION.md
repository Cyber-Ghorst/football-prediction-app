# OpenScores fixture normalization and reconciliation

## Normalization

`openscores_normalizer.py` converts the observed OpenScores fixture shape into
provider observations:
- fixture, league and season IDs remain namespaced as OpenScores provider IDs;
- nested `home_team` and `away_team` IDs/names are retained separately;
- `scheduled_kickoff_at` is parsed into UTC;
- status, exact available score fields, external `source_ids`, retrieval time
  and the complete raw provider record are preserved;
- invalid or duplicate records are rejected with reason counts.

The normalizer does not assume OpenScores numeric IDs are Sportmonks IDs and
does not use team names as an identity key.

## Staging and crosswalks

`provider_fixture_observations` is a separate provider-observation table.
Initial ingestion writes only to this table; it does not write or update
`football_fixtures`, model inputs, statistics, or the prediction ledger.

The existing `provider_entity_links` table is the explicit crosswalk.
Each crosswalk must also have a matching row in
`provider_entity_link_verifications`, recording its verification status,
method, evidence and timestamp. Reconciliation reads only links whose
verification status is `verified`; a bare provider link is not sufficient.
The reconciliation operation records evidence for exact competition/country,
same-league season-year, and unique exact team-name matches. Conflicting or
previously rejected mappings are not overwritten.

A reconciliation attempt requires verified OpenScores-to-canonical mappings
for league, season, home team and away team. It then checks the canonical
fixture fingerprint: competition, season, ordered home/away canonical IDs and
kickoff within a configurable five-minute default tolerance.

Exactly one match creates an OpenScores fixture crosswalk. Zero matches remain
unmatched; multiple matches are flagged ambiguous; a conflicting existing
fixture crosswalk is preserved and flagged. No fuzzy matching or score/stat
averaging is performed.

## Current activation state

This is a staging and reconciliation capability, not production prediction
activation. OpenScores remains disabled as a production co-primary until:
1. the initial live observation batch is staged successfully;
2. verified entity crosswalks are created for relevant competitions/seasons/teams;
3. fixture reconciliation passes without ambiguous or conflicting matches;
4. provider coverage and pagination limits are measured;
5. a separate reviewed integration enables OpenScores contributions by category.

No prediction weights, tactical recency rules, canonical Sportmonks fixtures,
or historical prediction records are changed by the staging operation.
