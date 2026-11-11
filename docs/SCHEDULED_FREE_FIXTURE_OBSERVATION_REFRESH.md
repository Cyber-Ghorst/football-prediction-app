# Scheduled free-fixture observation refresh

The existing six-hour upcoming-fixture workflow now has an optional secondary
staging step. The primary Sportmonks collection and persistence step runs first
and is not changed.

## Automated sources

- OpenLigaDB: discovers league/season scopes for the current and next calendar
  year, then polls a bounded rotating batch of at most 45 scopes per run. Each
  match-data request is paced at just over one second to stay below the
  documented 60-requests-per-minute ceiling.
- OpenFootball: discovers JSON files in the current football.json season
  directory and archives each dataset. Date-only or timezone-less kickoffs
  remain ineligible.
- LiveScoreFootball: discovers available club and international competition slugs, then polls a
  rotating batch of at most 30 leagues for the next seven days.
- Bzzoiro: polls the authenticated v2 upcoming-events endpoint, up to 20 pages,
  when BZZOIRO_API_TOKEN is configured.
- Open Matchday: deliberately skipped by unattended refresh because its
  upstream licence is non-commercial-only. The manual Streamlit staging form
  requires an explicit licence acknowledgement.

The OpenLigaDB and LiveScoreFootball batches rotate every six-hour run so the
same first leagues are not permanently favored. Provider errors are recorded
in the run output and do not fail the primary Sportmonks collection step.

## Safety

The secondary step writes only immutable provider observation snapshots to
CockroachDB. It does not write canonical fixtures, prediction records or the
Neon prediction ledger. It does not activate any future-fixture route. The
existing fixture search and selected-fixture prediction flow remain unchanged.
