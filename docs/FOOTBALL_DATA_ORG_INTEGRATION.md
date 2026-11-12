# football-data.org independent provider integration

## Decision

football-data.org belongs to the independent data-provider group, separate from
the future-fixture discovery group and separate from Sportmonks. Sportmonks
continues to operate independently. Neither adapter consumes the other's
response, IDs, catalogue or credentials. The integration does not change the
prediction model or authorize automatic canonical promotion.

## Adapter contract

- API: football-data.org v4, authenticated with `X-Auth-Token`.
- Credential: `FOOTBALL_DATA_ORG_API_TOKEN` (legacy alias
  `FOOTBALL_DATA_ORG_TOKEN` is accepted).
- Catalogue: `GET /competitions`; fixture collection:
  `GET /matches` with bounded `dateFrom`, `dateTo`, optional competition
  codes and bounded page pagination. Scheduled statuses are filtered locally so the adapter does not rely on undocumented multi-status query syntax.
- Provider competition, season, fixture and team IDs remain namespaced as
  football-data.org identities. No numeric ID is compared across providers.
- `TIMED` and `SCHEDULED` are normalized as scheduled; only offset-aware
  `utcDate` values strictly in the future are eligible for review.
- Observations are archived in the independent provider observation stream. They
  are available for crosswalk review and corroboration only; this is not a
  canonical fixture write and does not make a fixture prediction-ready.

## Independence and safeguards

Sportmonks remains an independently collected source in its own provider group. football-data.org is assigned to `independent_data`; it is excluded from `future_fixtures` discovery and must not be counted toward fixture-discovery coverage. Each provider's request
success, observation count, eligible count, coverage, freshness and identity
mapping must be measured separately. Reconciliation happens only after both
providers have produced normalized observations. Disagreements retain source
provenance and are not averaged or silently overwritten.

Canonical promotion remains disabled until competition/country, season, team,
fixture identity, kickoff precision, freshness, reuse terms and database
round-trip checks pass. Unmapped or conflicting records remain review-only.
Layer 1, Layer 2, model weights, 60/40 recent-match weighting, tactical
analysis and TVD are unchanged.

## Verification

Unit tests use mocked football-data.org v4 payloads. A live authenticated audit
is still required after `FOOTBALL_DATA_ORG_API_TOKEN` is configured. The
adapter's existence or successful mock tests do not establish account coverage
or live fixture availability.
