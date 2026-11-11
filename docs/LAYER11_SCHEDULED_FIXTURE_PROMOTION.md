# Scheduled Layer 11 fixture promotion

The six-hour fixture workflow can automatically promote cross-provider fixtures
after the owner has explicitly approved the provider entity crosswalks and
reviewed each provider's terms. This is deliberately opt-in.

## Default behavior

Every switch is disabled when missing. The scheduled runner therefore reports
providers as skipped and performs **zero canonical writes and zero Neon staging
writes** until the owner configures the GitHub Actions repository secrets.

## Required GitHub Actions secrets

Set these only after reviewing the provider's terms and confirming the intended
use is permitted:

- `FREE_FIXTURE_AUTO_PROMOTION_ENABLED=true` — global master switch.
- `FREE_FIXTURE_AUTO_PROMOTE_OPENLIGADB=true` and
  `FREE_FIXTURE_TERMS_ACK_OPENLIGADB=true`.
- `FREE_FIXTURE_AUTO_PROMOTE_HIGHLIGHTLY=true` and
  `FREE_FIXTURE_TERMS_ACK_HIGHLIGHTLY=true`.
- `FREE_FIXTURE_AUTO_PROMOTE_LIVESCORE=true` and
  `FREE_FIXTURE_TERMS_ACK_LIVESCORE=true`.
- `FREE_FIXTURE_AUTO_PROMOTE_OPENFOOTBALL=true` and
  `FREE_FIXTURE_TERMS_ACK_OPENFOOTBALL=true`.
- `FREE_FIXTURE_AUTO_PROMOTE_BZZOIRO=true` and
  `FREE_FIXTURE_TERMS_ACK_BZZOIRO=true`.
- `FREE_FIXTURE_AUTO_PROMOTE_API_NINJAS=true`,
  `FREE_FIXTURE_TERMS_ACK_API_NINJAS=true`, and
  `FREE_FIXTURE_NONCOMMERCIAL_ACK_API_NINJAS=true` only if the app and this
  use are non-commercial under the free-plan terms.
- Open Matchday additionally requires
  `FREE_FIXTURE_NONCOMMERCIAL_ACK_OPEN_MATCHDAY=true`; it remains disabled
  unless its non-commercial licence is explicitly accepted.

The provider-specific switches are independent. Do not enable a provider just
because its observations appear in a coverage report.

## Promotion gates

The runner does not create or approve crosswalks. It consumes only links
already explicitly saved in CockroachDB and reuses the existing checks for
provider freshness, scheduled status, timezone-aware kickoff, seven-day
window, exact league/season/home-team/away-team identity, canonical conflicts,
and provider licence acknowledgements.

Fixtures passing those checks are written to the canonical CockroachDB
repository and then additively staged in the Neon upcoming-fixture catalogue.
A Neon staging failure is reported separately; a later run can retry staging
idempotently. The prediction ledger is never modified by this workflow.

OpenScores remains excluded from future-fixture discovery. Prediction weights,
TVD and model inference are unchanged.
