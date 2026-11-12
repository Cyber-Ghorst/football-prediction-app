# Future-fixture discovery and match-data provider separation

## Product workflow

The application must not ask users to guess or manually type teams to obtain a prediction.

1. Collect genuine scheduled fixtures from the dedicated future-fixture sources.
2. Present a searchable catalogue of upcoming fixtures.
3. The user selects one exact fixture.
4. Only then activate the existing weighted prediction model using the selected fixture and validated match context.
5. Store the prediction against the stable fixture identity.
6. After the match, collect a verified final result, evaluate the stored prediction and use the evaluation record for learning and calibration.

The prediction model, its weights, tactical recency policy, TVD and prediction ledger schema are protected by this separation.

## Provider domains

Future-fixture discovery is its own domain: `future_fixtures`. It must not be inferred from a provider having a generic `fixtures` method or supplying historical matches, scores, standings, lineups or statistics.

| Provider | Correct responsibility | Future-fixture discovery status |
|---|---|---|
| Sportmonks | Current-season football data and existing rolling-window scheduled-fixture collector | Implemented current primary, subject to account/competition validation |
| OpenLigaDB | Free public fixture discovery candidate, strongest German coverage | Read-only future-schedule adapter verified; disabled pending country-aware crosswalk review, licence review and promotion gates |
| OpenFootball | CC0 public JSON schedule dataset | Registered but disabled; freshness and timezone must be verified |
| Open Matchday | Non-commercial CSV schedule dataset | Registered but disabled; commercial use prohibited absent written permission; fixed CET-1 timestamp needs correction/validation |
| WorldCup26 label | Not a separate provider; the `worldcup26.ir` host is the public service used by the LiveScoreFootball adapter | Do not register or count this as a second provider |
| Bzzoiro Sports Data | Free-tier football fixture API | Registered but disabled; requires `BZZOIRO_API_TOKEN` and per-competition live validation |
| OpenScores | Read-only historical/result observations and entity-mapping audit | **Not a future-fixture source. Never route it into `future_fixtures`.** |
| Highlightly | Match enrichment plus documented scheduled-match discovery | Live account feed verified (179 observed leagues; 1,491 eligible records in the latest refresh); disabled pending exact canonical crosswalks, quota/freshness monitoring and prediction-data completeness validation |
| API Ninjas | Fixtures, results, standings and club/squad corroboration | Live current-season feed verified for all eight documented free competitions (1,415 eligible records in the latest refresh); disabled pending manual canonical crosswalk approval and explicit non-commercial-use acknowledgement |
| API-Football v3 | Historical fixtures/results and supported historical detail within account seasons | Historical only for the configured 2022–2024 account |
| LiveScoreFootball / worldcup26.ir | Scheduled fixtures plus competition-scoped results/standings corroboration through one public API | Live feed verified (42 eligible records across nine observed leagues); disabled pending exact canonical crosswalks and broader per-event identity/freshness validation |

The seven registered future-fixture candidates are OpenLigaDB, OpenFootball, Open Matchday, LiveScoreFootball (served at `worldcup26.ir`), Bzzoiro, Highlightly and API Ninjas. The WorldCup26 label is an alias/host reference for LiveScoreFootball here, not an additional independent provider. Latest live sample: Highlightly returned 1,518 observations across 179 leagues (1,491 eligible); API Ninjas returned 1,415 eligible observations across its eight free-tier leagues; OpenLigaDB returned 2,134 eligible observations across 32 leagues; LiveScoreFootball returned 42 eligible observations across nine leagues; OpenFootball returned 2,916 observations but zero eligible records because its timestamp schema does not establish a timezone. Bzzoiro could not be authenticated, and Open Matchday remains withheld pending licence review. These are archived provider observations, not unique fixtures in the next seven days or approved canonical fixtures. The candidates are not considered active sources merely because they are registered. A candidate remains disabled until its adapter has demonstrated future kickoff records, stable IDs, timezone-aware timestamps, scheduled status, competition/season/team identity, freshness, applicable reuse rights, canonical crosswalks, normalization tests and database round-trip behavior. Eligibility is per provider and competition.

## Evidence-based candidate audit

This is a capability audit, not production activation. Public documentation establishes that the sources can expose upcoming schedules, but the application must still pass its own live-response and canonical-identity gates.

### Latest authenticated account audit — 2026-11-11 12:25 UTC

These are catalogue-access results, not approved fixture routes:

- **Sportmonks:** five accessible catalogue leagues: Premier League (ID 8, England), FA Cup (24, England), Serie A (384, Italy), La Liga (564, Spain) and La Liga 2 (567, Spain). Each has three seasons in the catalogue. Country probes for Germany, France, World and International returned zero leagues; Bundesliga, Ligue 1 and World Cup name/ID probes returned no usable match. Do not invent mappings or treat an HTTP 200 response containing an API-level error as access.
- **LiveScoreFootball:** 35 competitions listed, all 35 marked available and fresh, spanning 17 countries. This is broader than the earlier nine-league sample, but it does not itself prove 35 competitions have future fixtures or canonical identity matches. Keep the provider disabled for prediction staging until per-competition competition, season, team and fixture mappings are verified.
- **Highlightly:** live catalogue probing was skipped because terms acknowledgement and non-betting-use confirmation are not configured. Do not enable its scheduled-fixture route until the required use conditions are explicitly confirmed.
- **Current coverage baseline:** the 2026-11-11 seven-day free-source audit found 104 unique future fixtures across the window, against a target of 630 (90 per day). No day met the target. The separate Sportmonks rolling collector imported 11 fixtures, all from La Liga 2. These figures are observations from the audit window, not guarantees of future coverage.

The immediate reconciliation priority is to map LiveScoreFootball's fresh competition catalogue only against the five actually accessible Sportmonks leagues, then verify season/team/fixture identities. Unmatched competitions remain visible as unmapped; do not widen canonical data or relax exact-context checks to inflate coverage.

| Unique candidate | Public evidence of upcoming fixtures | Remaining activation blocker |
|---|---|---|
| OpenLigaDB | The public API documents season-wide match data via `GET /getmatchdata/{leagueShortcut}/{leagueSeason}`; no key is required. | The documented League schema has no country field. The adapter adds country only for a curated set of verified stable league IDs; unknown IDs remain country-unmapped. OpenLigaDB league ID `4936` (`LaLiga EA Sports`) has a curated alias to the canonical `La Liga` name, but still produces only a manual-review candidate and requires exact Spain country context. Continue requiring live scheduled rows, stable IDs, timezone-aware kickoff timestamps and manual canonical review. |
| OpenFootball | The public-domain football.json repository contains current-season 2026/27 schedules and its generated latest-season mirror refreshes daily. | Some entries are date-only and time fields do not establish a timezone. Exclude those rows; use only events with reliable kickoff precision and a verified timezone. Upstream source data is not guaranteed to update daily. |
| Open Matchday | Its repository publishes separate `fixtures_<season>.csv` files and reports upcoming fixtures with a daily build. | Non-commercial-only use and the fixed CET-1 time convention must be resolved. Keep disabled for commercial use and reject ambiguous kickoff conversion. |
| LiveScoreFootball (`worldcup26.ir`) | Its documented fixtures endpoint accepts scheduled status and date filters; the existing adapter parses event IDs and paginated events. | The service is backed by an external database writer. Verify current per-competition sync freshness, exact season/team crosswalks and precise timezone-aware kickoff values before enabling. |
| Bzzoiro | Its football API documents upcoming match status, paginated match endpoints and ISO-8601 UTC timestamps. | Requires `BZZOIRO_API_TOKEN`. Confirm the token's free-tier access, per-competition coverage, stable IDs, licence conditions and database round-trip before enabling. |
| Highlightly | Its official `/matches` endpoint supports league, date and season queries; responses include stable match IDs, ISO-8601 dates, team IDs, league/season identity and a `Not started` state. The public documentation advertises 950+ leagues in 170+ countries. | Coverage is plan-dependent. Verify the connected account's accessible league catalogue, quota, future scheduled rows, update freshness and exact canonical team/competition/season crosswalks. Keep disabled until those live checks pass. |
| API Ninjas | Its `/v1/soccermatches` endpoint supports league/date/season/status queries and returns stable `game_id`, UTC `start_time`, scheduled status, team IDs and league identity. Its documentation lists 74 competitions overall. | The free plan is current-season only and the FAQ identifies eight free competitions (Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Champions League, Europa League and MLS); free-tier commercial use is prohibited. Verify the connected account's actual coverage, quota, stable IDs, freshness and exact canonical crosswalks before enabling. |

Source documentation:
- OpenLigaDB API: https://api.openligadb.de/index.html
- OpenFootball football.json: https://github.com/openfootball/football.json
- Open Matchday README and data dictionary: https://github.com/oladeeayo/open-matchday
- LiveScoreFootball API: https://github.com/rezarahiminia/livescoreFootball
- Bzzoiro API documentation and data licence: https://sports.bzzoiro.com/docs/ and https://sports.bzzoiro.com/docs/api-license/
- Highlightly matches endpoint: https://highlightly.net/football-api/documentation/matches/
- API Ninjas football API and free-tier coverage: https://api-ninjas.com/api/football

## Routing invariants

- `future_fixtures` is the only category used to populate the upcoming-fixture search catalogue.
- OpenScores has no `fixtures` or `future_fixtures` assignment. Its disabled result-validation assignment is audit-only. The legacy scheduled-fixture observation sync is disabled in both the controller workflow and Python entry point; existing observations are retained without deletion.
- Highlightly and API Ninjas have read-only scheduled-match observation collectors and are registered as disabled future-fixture candidates. Their enrichment/corroboration roles remain separate; neither is active for fixture discovery until account-level live coverage and identity gates pass.
- API-Football remains historical-only for the configured 2022–2024 account and is not assigned to `future_fixtures`.
- LiveScoreFootball is explicitly registered as one of the seven future-fixture candidates because its adapter exposes a scheduled-fixtures endpoint. It remains disabled until live records pass per-competition identity, timestamp and freshness checks.
- The existing collector currently calls Sportmonks only. All seven registered candidates remain disabled until their adapters and live audits are complete. LiveScoreFootball has an existing fixtures adapter, but it remains disabled for future-fixture collection until the same live validation gates pass.
- No provider may silently overwrite a canonical fixture, kickoff, team identity or score. Conflicts remain visible with provenance.
- Temporary fixture staging is separate from the prediction ledger.

## Activation and prediction safeguards

A selected fixture must have a provider-scoped stable ID, future timezone-aware kickoff, scheduled status, competition and season IDs, and both team identities. Cross-provider records must be reconciled to canonical competition, season and team IDs before the fixture is prediction-ready.

Fixture selection is the trigger for prediction. Background fixture collection must never create predictions for every fixture automatically. Prediction storage and post-match evaluation remain tied to the selected fixture identity.

No change in this provider-routing work authorizes changes to the model weights, TVD, tactical recency, canonical fixture repository or prediction-ledger behavior.

## Independent data providers (not discovery sources)

- `football_data_org` is assigned to the separate `independent_data` provider category.
- Its own authenticated observation refresh may collect provider match and competition/team metadata for independent corroboration and crosswalk review.
- It is not a member of `FREE_FIXTURE_CANDIDATES`, is not routed to `future_fixtures`, and its observations do not count toward future-fixture coverage totals.
- Sportmonks remains independently active in its existing data-provider role; neither provider may overwrite the other's observations or canonical data.
