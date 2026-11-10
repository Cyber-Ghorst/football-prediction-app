# Layer 12 — OpenScores entity mapping audit

## Purpose

The initial OpenScores live sync staged 300 normalized fixture observations
across six provider leagues/seasons. All 300 remained pending because verified
league, season and team crosswalks were not present.

This audit produces a read-only candidate report to help review those entity
identities against the existing canonical Sportmonks-backed repository.

## Candidate policy

- Competitions: exact normalized competition name **and country** are required
  to produce a candidate.
- Seasons: a candidate is shown only after a unique competition candidate and
  an exact normalized season name or exact start/end date match.
- Teams: exact normalized names produce review candidates; duplicate canonical
  names remain ambiguous.
- All candidate statuses explicitly say they require review.
- Candidate generation never inserts, updates or deletes
  `provider_entity_links`.
- No canonical football table, fixture, provider observation or prediction
  ledger record is changed by this audit.

Name matches are not proof of identity. A later, separately reviewed mapping
operation must create explicit crosswalks only after confirming provider
identity evidence (preferably shared external source IDs) and validating
competition, season and team context. Once mappings are approved, fixture
reconciliation still requires ordered home/away canonical IDs and kickoff
within the five-minute tolerance.

## Running the audit

Use the Prediction Lab Controller operation:

`openscores_entity_mapping_audit`

The controller report and downloadable workflow artifact contain
`openscores-entity-mapping-audit.json`, including observation counts,
canonical entity counts, candidate lists, ambiguity statuses and explicit
zero-write safety indicators.

## Activation status

OpenScores remains a staged co-primary candidate, not enabled for production
prediction routing. This audit does not activate it or change Sportmonks'
current primary status.


## Season and fixture freshness diagnostics

The read-only audit also reports all seasons returned per OpenScores league,
their start/end/current fields, and the stored observation kickoff range. It
counts fixtures in the future and inside the next seven days using the
CockroachDB server clock. This prevents a historical season sample from being
mistaken for a current upcoming-fixture feed.


## Strict upcoming-fixture collection

The sync requests only `scheduled` fixtures using the provider's live
`date_from` / `date_to` filters, bounded from the UTC collection time through
exactly seven days later. It requests up to 200 records per competition and
checks the kickoff window again locally. Historical observations are retained
for audit but marked `outside_upcoming_window` and excluded from reconciliation.


The seven-day sync does not pin fixture retrieval to the first season returned
by the provider. It queries the date window across all seasons, then uses each
fixture's own season ID for normalization. This avoids missing a current season
when the provider's season catalogue is incomplete or stale.
