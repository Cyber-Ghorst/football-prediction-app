# Free future-fixture provider candidates

## Decision

Register the five user-selected free sources as **fixture discovery and validation
candidates**. Do not route them into production fixture staging or prediction
inputs merely because they are listed here. Each provider/competition pair must
pass live future-fixture, identity, freshness, timezone, licensing and
round-trip checks first.

Sportmonks remains the only enabled current-fixture primary. This change does
not modify the canonical fixture repository, model weights, prediction
calculations, tactical recency policy, TVD or prediction ledger.

## Candidate register

| Provider | Access | Advertised scope | Known constraints | Initial role |
|---|---|---|---|---|
| OpenLigaDB | Free public API; no key | Broad community catalogue, strongest in German football | 60 requests/minute per IP; community-maintained; no SLA. Confirm applicable data licence before commercial redistribution. | Candidate / validation |
| OpenFootball (football.json) | Public JSON; no key | Major European leagues and additional competitions | CC0 dataset. Current-season JSON mirror refreshes daily, but upstream Football.TXT source updates are not automatically daily; kickoff timezone must be established before timestamp use. | Candidate / validation |
| Open Matchday | Public CSV on GitHub; no key | Advertises 75 competitions and daily refresh | Explicitly non-commercial only; not a live feed; kickoff time uses a fixed CET-1 convention and can be one hour off in summer. **Do not use in a commercial deployment without written permission or a different licence.** | Research-only candidate |
| LiveScoreFootball (public host: worldcup26.ir) | Public JSON REST API; no key | Competition catalogue currently documents verified coverage focused on England and Spain | Existing adapter exposes a paginated fixtures endpoint with scheduled status and date filters. Data is stored by an external listener, so freshness and per-event kickoff precision must be measured. This is one provider, not a separate WorldCup26 source. | Candidate / validation only |
| Bzzoiro Sports Data | Free football API; account token required | Advertises 60+ competitions and 7,500 requests/day on free access | Free tier is stated to be permanent and no-card. Terms allow display in apps and use of derived prediction outputs, but prohibit redistributing raw data as a standalone feed/database/API. | Candidate / validation |

## Live-fixture acceptance gates

A provider is not considered eligible globally. Eligibility is recorded per
provider and canonical competition:

1. The endpoint returns at least one fixture with a kickoff strictly after the
   audit timestamp and within the requested future window.
2. Fixture identity includes a stable provider fixture ID, competition and
   season identity, and both team identities. Where a static dataset lacks
   provider IDs, deterministic source keys may be retained as observations,
   but they are not canonical IDs.
3. Kickoff is timezone-aware and precise enough for scheduling. Date-only or
   timezone-ambiguous rows are discovery evidence only and cannot enter the
   prediction-ready fixture feed.
4. The fixture status is scheduled/not-started. Finished, live, cancelled,
   postponed-without-a-new-kickoff and stale rows are excluded.
5. The competition, season and teams have explicit verified crosswalks to
   canonical entities. Name similarity alone is not sufficient.
6. The fixture is deduplicated by canonical competition, season, home team,
   away team and kickoff. Conflicts remain visible; source values are not
   averaged or silently overwritten.
7. Raw payload, provider IDs, retrieval time, source URL and licence/attribution
   metadata are retained for audit.
8. The adapter passes fixture-normalization tests and a database round-trip
   test before a provider/competition route is enabled.

## Suggested source roles after validation

- OpenLigaDB: specialist corroboration for Bundesliga and other competitions
  where live coverage is demonstrated.
- OpenFootball: broad open-data cross-check and competition discovery.
- Open Matchday: broad daily fixture discovery for non-commercial research
  only, subject to its terms and upstream provider rights.
- LiveScoreFootball: England/Spain supplementary coverage through its
  existing scheduled-fixtures endpoint, subject to event freshness and exact
  team/season crosswalk validation. Do not count worldcup26.ir as a separate
  provider.
- Bzzoiro: broad current fixture source where the free account returns
  scheduled fixtures and its API terms permit the app's exact use.

No source should be used as a sole authority for kickoff changes or
postponements until its event-level freshness has been measured.

## Required secret

Only Bzzoiro requires an account token:

- `BZZOIRO_API_TOKEN`

Store it in the deployment secret manager (or Streamlit Secrets). Never commit
it, print it in diagnostics, or include it in reports. The other four sources
are documented as no-key public endpoints/datasets.

## References checked

- OpenLigaDB API: https://api.openligadb.de/index.html
- OpenFootball data and CC0 licence: https://github.com/openfootball/football.json
- Open Matchday README and terms: https://github.com/oladeeayo/open-matchday
- LiveScoreFootball API and source repository: https://worldcup26.ir/football-api and https://github.com/rezarahiminia/livescoreFootball
- Bzzoiro free plan: https://sports.bzzoiro.com/pricing/
- Bzzoiro data licence: https://sports.bzzoiro.com/docs/api-license/
