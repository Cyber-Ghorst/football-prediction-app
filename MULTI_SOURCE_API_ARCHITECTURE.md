# Multi-source football data architecture

## Decision record

Operating mode: **hybrid**. Accuracy is the priority. Existing Layer 1 calculations, Layer 2 workflows, model weights, recency weighting, and `tvd.py` are protected.

### Protected prediction model

The implementation must not change these values:

- Recent form: 20%
- Goals scored: 10%
- Goals conceded: 10%
- Home/away performance: 10%
- Strength of schedule: 15%
- Player availability: 5%
- Tactical analysis: 30%

Tactical sub-weights remain: playing style 6%, defensive structure 7%, attacking approach 7%, tactical compatibility 10%. Recent-history weighting remains 60% for the latest five matches and 40% for matches 6–10. Missing data remains unknown; it is not fabricated or silently imputed. The existing TVD rules and scoring remain unchanged.

## Provider responsibilities

Future-fixture discovery is a separate domain (`future_fixtures`) and is not
synonymous with generic fixture details or historical fixture retrieval.
Sportmonks is currently the only wired scheduled-fixture collector. OpenLigaDB,
OpenFootball, Open Matchday, LiveScoreFootball, Bzzoiro, Highlightly and API
Ninjas are registered as disabled future-fixture candidates pending live
account coverage, adapter, identity, timestamp, licence and persistence
validation. OpenScores is read-only result-observation and entity-audit data
only; it is not a future-fixture provider. Highlightly and API Ninjas also
retain their existing enrichment/corroboration roles; API-Football remains
historical-only for the configured account seasons.

Provider roles are domain-specific. A provider is not assumed to be authoritative for every field.

| Rank | Provider | Assigned role | Eligible data domains | Main limitation / activation gate |
|---:|---|---|---|---|
| 1 | **Sportmonks Football API v3** | Primary current-season source | Fixtures, results, standings, match statistics, injuries, lineups, players and squads, where returned | Account-enabled competitions/seasons only. Current-season Layer 2 path is active; selected competition still must pass history and data-quality checks. |
| 2 | **Highlightly** | Independent current-season corroboration and secondary source | Fixtures, results, standings, statistics, injuries, lineups, players and squads, where explicitly supplied | Plan-dependent coverage, fields, quotas and refresh interval. Adapter, smoke test and canonical normalizer exist; records are not yet active in Layer 2 reconciliation. |
| 3 | **API-Football v3** | Historical specialist source; secondary detail source where season access is confirmed | Fixtures, results, standings, statistics, injuries, lineups, players and squads | This account is limited to seasons 2022–2024. Current historical Layer 2 path is active; do not request unsupported newer seasons. |
| 4 | **API Ninjas** | Independent fixtures/results/standings and club/squad corroboration | Fixtures, results, standings, clubs and squads | Current adapter does not supply detailed fixture statistics, injuries or lineups. Adapter, smoke test and canonical normalizer exist; records are not yet active in Layer 2 reconciliation. |
| 5 | **LiveScoreFootball** | Conditional competition-specific corroboration | Fixtures, results and standings only | Database-backed snapshots can be delayed. Opt-in missing-score fallback is wired into Streamlit. Requires fresh global, per-competition and per-event sync timestamps, an exact competition/season crosswalk and exact completed fixture identity; it never overwrites valid Sportmonks scores. |

The rank is a practical role assignment, not a claim that one provider has universal coverage or is always freshest. Domain-specific priorities in `provider_core.py` remain authoritative. A source is eligible only when its account coverage, identity, timestamps and record validation pass.

The provider clients must be optional. The application must continue to operate when one provider is not configured or is temporarily unavailable, provided minimum validated match-history requirements are met.

## Hybrid request and reconciliation flow

1. Query the domain's designated primary provider.
2. Validate HTTP status, response shape, required IDs, timestamps, competition, teams, date and match status.
3. Normalize the response into a provider-neutral schema.
4. Query configured independent providers for corroboration or missing fields, respecting each provider's rate limits and plan coverage.
5. Match records using stable team identity, competition, kickoff date/time and source IDs. Keep every provider ID namespaced; never assume IDs from different providers are interchangeable.
6. Reconcile each field using its domain-specific source priority, freshness and validation status.
7. If sources agree, mark the field corroborated and retain its provenance.
8. If sources disagree, do not average scores, goals, dates or statistics. Prefer the configured authoritative source only when its record passes validation; otherwise mark the field conflicted/unknown and expose the conflict in diagnostics.
9. Preserve the last valid value when a provider fails. A failed request must never overwrite good data with null or an empty response.
10. Pass only validated canonical data to Layer 2. Layer 1 receives the same profile shape it already expects.

## Canonical data and provenance

Every normalized field should carry, internally, its value, provider, source record ID, fetched-at timestamp, source-updated-at timestamp (when supplied), validation status and confidence/coverage metadata.

Canonical match identity should include competition, season, kickoff time, home team and away team. Source-specific fixture IDs are stored separately, for example:

- `source_ids.api_ninjas`
- `source_ids.highlightly`
- `source_ids.api_football`
- `source_ids.livescore_football`

Do not join two fixtures solely because their numeric IDs match. Team aliases and competition IDs require an explicit cross-provider mapping table or a verified identity match.

## Domain-specific source priority

The default priority is encoded in `provider_core.py`:

| Data domain | Priority order |
|---|---|
| Future-fixture discovery | Sportmonks only until the seven registered candidates pass activation gates; OpenScores is excluded |
| Generic fixture details, results, standings | Sportmonks → Highlightly → API Ninjas → API-Football; LiveScoreFootball is prepended only for verified results/standings |
| Match statistics | Sportmonks → Highlightly → API-Football |
| Injuries | Sportmonks → Highlightly → API-Football |
| Lineups | Sportmonks → Highlightly → API-Football |
| Player profiles/statistics | Sportmonks → Highlightly → API-Football → API Ninjas |
| Squads | Sportmonks → Highlightly → API Ninjas → API-Football |

These priorities are selection order, not automatic permission to substitute. A provider must return the requested field for the exact fixture/competition/season, with valid identity and acceptable freshness. API Ninjas is not a statistics, injury or lineup source in the current adapter. LiveScoreFootball is never eligible for those domains. Opponent strength must use a validated standings table from the same competition and season; raw ranks from different competitions must not be compared without normalization.

### Activation status (2026-11-07)

- **Active prediction paths:** Sportmonks for current seasons after 2024; API-Football for historical seasons supported by the account (2022–2024).
- **Opt-in field-level fallback:** Highlightly can fill missing supported match-statistic fields and exact-fixture lineups, and can discover recent results that are imported only after an exact completed Sportmonks fixture and full-time score agree. Sportmonks remains authoritative; Highlightly is not promoted globally and does not supply injury/availability inferences.
- **Conditional result discovery:** API Ninjas can supply independent result candidates, but its score is never imported directly. An opt-in history fallback may append only the corresponding exact completed Sportmonks result after full-time score agreement. Its other fields remain diagnostic/canonicalization-only.
- **Opt-in missing-score fallback:** LiveScoreFootball can fill a missing full-time score only on an already-known completed Sportmonks fixture after fresh global, per-competition and per-event sync metadata, an exact competition-season crosswalk, exact home/away identity and kickoff checks. Existing Sportmonks scores remain authoritative; LiveScore does not supply statistics, lineups or injuries.
- **Reconciliation foundation:** canonical normalizers and field-level conflict/provenance logic exist. The next integration milestone is to fetch records from each provider, apply validated crosswalks and timestamps, reconcile them, and surface provenance/conflicts in Streamlit.
- **No model changes:** no provider issue authorizes changes to prediction weights, TVD rules, or 60/40 recency weighting. Missing data remains unknown; disagreements remain visible and are never averaged.

## Repository audit: blockers to fix before enabling the providers

The current repository has a provider contract mismatch:

1. `app.py` consumes API-Football v3 nested response objects (`league`, `team`, `fixture`), but the current `api_football.py` is an API Ninjas client returning API Ninjas-shaped records.
2. `app.py` expects league objects with `league.id` and `league.name`; the current API Ninjas league catalog exposes top-level `id` and `name`.
3. `app.py` expects team objects with `team.id` and `team.name`; API Ninjas club rows expose `team_id` and `name`.
4. `data_layer2.py` calls `last_fixtures(team_id, season, last=10)`, but the current API Ninjas method accepts a different signature and does not accept that `last` keyword.
5. `data_layer2.py` expects API-Football fixture nesting (`fixture`, `teams`, `goals`), which API Ninjas does not return.
6. `app.py` passes raw standings rows to `collect_team_profile`, while Layer 2 treats standings as a dictionary keyed by numeric team ID.
7. `data_layer2.py` treats `next_fixture` as a list, while the current API Ninjas client returns one dictionary or `None`.
8. API Ninjas explicitly returns no fixture statistics, injuries or lineups in the current client. These fields must be sourced from another configured provider or remain unknown.

These are integration-contract defects, not reasons to alter the prediction weights or TVD.

## Secrets and configuration

Use Streamlit Secrets or environment variables. Never commit keys:

- `API_NINJAS_API_KEY`
- `HIGHLIGHTLY_API_KEY` (support the existing `API_FOOTBALL_KEY` alias only as a backward-compatible Highlightly credential)
- `APISPORTS_API_KEY` (for API-Football v3; this avoids colliding with the legacy Highlightly key name)
- `LIVESCORE_FOOTBALL_BASE_URL` (optional override for the documented public API base)

Provider enablement must be explicit and independently configurable. Do not assume a key exists merely because a provider module is installed.

## Implementation sequence

1. Add provider interfaces, configuration, canonical normalization and field-level reconciliation with unit tests.
2. Implement isolated adapters for LiveScoreFootball, API Ninjas, Highlightly and API-Football v3.
3. Add team/league/fixture identity mapping and coverage-aware source selection.
4. Repair Layer 2 data collection to consume only the canonical schema; keep its existing output profile shape.
5. Integrate the provider registry into Streamlit with source-health and data-provenance diagnostics.
6. Run existing Layer 1/TVD tests plus provider normalization, conflict, fallback, missing-data and integration tests.
7. Backtest predictions against historical results before considering any change to model parameters.

No prediction weights, TVD rules or production branch files are changed by this architecture decision record.


## Current implementation status (2026-11-07)

- api_football.py now contains the dedicated API-Football v3 client and reads APISPORTS_API_KEY; it does not reuse the old ambiguous key name.
- The former API Ninjas implementation is preserved as api_ninjas.py with APINinjasClient / APINinjasError.
- highlightly.py contains a separate Highlightly adapter using the documented direct Football API host, key header, paginated-envelope handling and rate-limit metadata.
- data_layer2.py now consumes API-Football v3 response structures, converts standings to competition-season-relative opponent-strength scores, and handles a single upcoming fixture object.
- test_provider_adapters.py adds adapter contract and credential-redaction tests; .github/workflows/tests.yml runs the unit suite in CI.
- The Streamlit prediction flow currently uses API-Football v3 only. API Ninjas and Highlightly are isolated adapters, not yet active fallbacks in a live multi-source registry.
- LiveScoreFootball has a read-only adapter for the documented public database-backed API at https://worldcup26.ir. Its public read endpoints do not require an API key. The adapter remains outside the automatic prediction fallback until runtime competition mapping, sync freshness and per-match identity checks pass.
- Credentials are never displayed. Configure APISPORTS_API_KEY for API-Football, API_NINJAS_API_KEY for API Ninjas, and HIGHLIGHTLY_API_KEY for Highlightly. The Highlightly client retains API_FOOTBALL_KEY as a legacy fallback only.
- API-Football account status/quota and LiveScoreFootball health/sync diagnostics are now implemented in an opt-in Streamlit check. Actual deployment credentials and live endpoint responses still need to be checked from the running app.


## LiveScoreFootball provider identification and adapter

The user identified https://github.com/rezarahiminia/livescoreFootball. This is a public, database-backed REST API hosted at https://worldcup26.ir, not the separate upstream listener. The documented customer API does not require an API key. It reads stored MongoDB snapshots; a separately operated listener fetches upstream data and writes normalized records. Freshness therefore depends on listener synchronization and must be checked using /get/soccer/meta (lastSuccessfulSyncAt and generatedAt) and per-league lastSyncedAt.

The read-only adapter is livescore_football.py and defaults to https://worldcup26.ir. Supported documented endpoints include /health, /get/soccer/meta, /get/soccer/leagues, /get/soccer/{league}/fixtures, /get/soccer/{league}/scoreboard, /get/soccer/{league}/standings, /get/soccer/{league}/summary, and /get/soccer/{league}/events/{eventId}/plays. Override the base URL with LIVESCORE_FOOTBALL_BASE_URL. No credential should be configured for this public service unless its operator changes the documented access policy.

The repository README verifies initial competition coverage focused on England and Spain: Premier League, EFL competitions, FA Cup, LaLiga, LaLiga 2, Copa del Rey and women's competitions. UEFA Champions League and other countries are not to be assumed available. The service does not fetch upstream data on customer requests, and its API documentation warns that stored snapshots can be delayed or incomplete.

Current app status: the read-only adapter and mocked contract tests exist, and the provider is listed first for fixtures/results/standings in provider_core.py. It is not yet connected as an automatic Layer 2 fallback. Do not treat this source as a guaranteed live feed or infer missing statistics, injuries, lineups, or player availability from absent fields.


## Canonical normalization milestone (2026-11-07)

The first canonical match-normalization layer is now implemented in `canonical_data.py`:

- LiveScoreFootball scoreboard/fixture events are normalized from their documented `competitions[].competitors[]` structure, including the nested `competitor.team` object and `homeAway` side marker.
- API-Football v3 fixture records are normalized from `fixture`, `teams`, `goals`, and `fixture.status.short`.
- Canonical identity requires an explicitly supplied shared competition key, matching season, same home/away team identities (with optional explicit aliases), and kickoff within a configurable five-minute default tolerance.
- Provider match and team IDs remain namespaced. Numeric ID equality is never used to join records.
- `reconcile_match_pair` applies the existing domain priority field by field, keeps conflicting-source diagnostics, and never averages score or status values. Records that do not pass identity matching are not merged.
- Unknown scores and absent fields remain `None`; a missing value from one source cannot overwrite a known value from another.

The normalizers currently cover LiveScoreFootball and API-Football v3. API Ninjas and Highlightly remain isolated adapters until their actual response shapes are captured in fixtures and independently tested. The new canonical layer is not yet switched into the Streamlit prediction flow: automatic fallback requires an explicit competition/season crosswalk, team alias validation, and freshness checks against the LiveScoreFootball metadata endpoint. This is intentional fail-closed behavior, not a missing-data workaround.

Tests are in `test_canonical_data.py`; the existing provider priority and Layer 1/TVD tests remain in place.


## Competition crosswalk and health validation milestone (2026-11-07)

### Competition crosswalk

`competition_crosswalk.py` creates runtime mappings from the API-Football league catalogue to the LiveScoreFootball public league catalogue. No API-Football numeric IDs or LiveScore slugs are guessed or hardcoded. A mapping is verified only when:

1. Competition names match exactly after conservative Unicode/punctuation normalization.
2. Country names match after a small explicit country-alias normalization.
3. Exactly one LiveScoreFootball catalogue candidate exists.
4. The LiveScoreFootball competition is active and `coverage.hasData` is true.
5. The LiveScoreFootball season year is present and equals the requested season.

No fuzzy matching is used. Ambiguous, inactive, empty, missing-season or mismatched-season records are rejected. `verified_livescore_slug` returns a slug only for a single verified mapping.

### Provider health and freshness

`provider_health.py` separates transport/account status from data freshness:

- LiveScoreFootball metadata is checked using the documented `service.dataSource`, `coverage`, and `lastSuccessfulSyncAt` fields. Its global latest sync is only a service-level indicator; competition-level `lastSyncedAt` remains the stronger signal when present.
- API-Football uses its documented `/status` endpoint to inspect active subscription and daily request usage/remaining quota. Account identity fields are deliberately discarded.
- Highlightly and API Ninjas remain credential/readiness-only until their provider-specific health contracts are verified; no undocumented endpoints are probed.
- Freshness thresholds are domain-specific (live scores, fixtures/results, standings, statistics, injuries/lineups, player/squad data). Missing or invalid source timestamps are `unknown`, future timestamps are invalid, and stale data is ineligible.
- The Streamlit sidebar has an opt-in provider health and coverage diagnostic. It does not run automatically on every app rerun and does not activate fallback.

### Current safety boundary

The crosswalk and health diagnostics are implemented and unit-tested. The app still uses API-Football as its active Layer 2 data provider. LiveScoreFootball is not yet used as a fallback because match-level source timestamps, team identity mapping, and canonical record validation must be applied to each candidate match before integration. API Ninjas and Highlightly remain isolated adapters. This is deliberate: no provider is promoted on catalogue presence alone.

The prediction engine, Layer 1 behavior, `tvd.py`, all existing component weights, and 60/40 recency weighting remain unchanged.


## Provider diagnostics and canonical adapter milestone (2026-11-07)

- The Streamlit provider health action now performs authenticated smoke tests for API Ninjas and Highlightly in addition to the existing API-Football and LiveScoreFootball checks. The checks report transport/HTTP metadata only; they do not expose credentials or imply that the providers are already used for prediction inputs.
- API Ninjas and Highlightly match records now have separate canonical normalizers. API Ninjas uses its documented UTC `start_time`, namespaced `game_id` and team IDs, status, and score fields. Highlightly uses its documented match `date`, `homeTeam`, `awayTeam`, `league.season`, state description, and displayed current score.
- Source update timestamps remain unknown when a provider does not supply them; scheduled kickoff is never mislabelled as a source-update timestamp.
- API Ninjas date handling was corrected for both Python `date` inputs and its connection test.
- Canonical reconciliation now requires an explicit `livescore_verified=True` signal before LiveScoreFootball can take priority. The default resolver excludes LiveScoreFootball, so catalogue presence alone cannot activate it.
- Unit tests were added for the two new match normalizers, unknown scores, strict identity matching, provider connection diagnostics, and the LiveScore verification gate.
- API Ninjas and Highlightly remain diagnostic/canonicalization sources. Runtime, identity-matched result corroboration is implemented and tested, but neither provider is wired to replace Layer 2 histories or supply prediction statistics, injuries, lineups or squads. Further field-level fallback requires endpoint-specific validation and provenance; no such fallback is enabled. Prediction weights, recency weighting and TVD remain unchanged.

## Current-season provider-role adjustment and Sportmonks integration (2026-11-07)

### API-Football season restriction

The user's API-Football Free subscription currently accepts seasons 2022–2024 only. Treat this as an account-plan coverage restriction, not as a parser or date-format defect. API-Football remains available for historical data within its permitted seasons; do not make it the required source for 2025/26 or 2026/27 data.

### Revised intended provider roles

| Provider | Intended role after validation |
|---|---|
| Sportmonks Football API v3 | Preferred current-season source for fixtures, results, standings, match statistics, lineups, player and availability data, limited to leagues enabled on the account |
| Highlightly | Independent current-season corroboration and secondary source where its account covers the exact league and fields |
| API Ninjas | Independent fixtures/results/standings corroboration where exact competition and season data are available |
| API-Football v3 | Historical source for seasons allowed by the user's subscription; secondary source only where a season is explicitly confirmed available |
| LiveScoreFootball | Competition-specific fixtures/results/standings only after the existing exact crosswalk and freshness checks |

provider_core.py now records Sportmonks first in the intended domain priority. This is a source-selection policy only: a provider observation must still exist, pass validation, and be fresh before it can be selected. It does not activate automatic fallback by itself.

### Sportmonks adapter

- Added sportmonks.py, a separate Football API v3 REST adapter using https://api.sportmonks.com/v3/football.
- Reads SPORTMONKS_API_TOKEN (or the backward-compatible SPORTMONKS_API_KEY) from environment variables or Streamlit Secrets.
- Uses the documented Authorization header; never logs or returns the token.
- Provides read-only methods for leagues, seasons, teams, standings, fixtures, date-range fixtures, individual fixtures and livescores.
- Connection diagnostics use the documented leagues endpoint and expose only HTTP/rate-limit metadata and record count.
- Added Sportmonks to the Streamlit provider-readiness panel and opt-in health diagnostic.
- Added adapter tests for response envelopes, connection metadata and credential redaction.

### Coverage and cost guardrails

Sportmonks' free tier currently provides a limited competition set (the provider advertises Danish Superliga and Scottish Premiership). Paid self-serve tiers are league-count based: Starter from €29/month for 5 leagues, Growth from €99/month for 30 leagues, and Pro from €249/month for 120 leagues; verify current checkout terms before purchasing. The provider states that all selected leagues receive its professional data features, while historical data beyond three seasons is a separately priced add-on for self-serve tiers. See the official plans and pricing page at https://www.sportmonks.com/football-api/plans-pricing/ and Football API v3 docs at https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints.

### Activation boundary

Sportmonks is now wired into the Streamlit current-season prediction path through sportmonks_layer2.py. The app discovers leagues and seasons from the authenticated account, maps the selected league to its exact Sportmonks season ID, retrieves season teams/standings/fixtures, and builds the existing Layer 2 profile contract using provider-native team IDs. The current-season path still fails closed when the token, competition, season, teams, standings/fixtures, or five completed matches are unavailable. A successful token test alone is not treated as proof of competition coverage.

No model weights, 60/40 recency weighting, Layer 1 calculations, or TVD rules were changed.

### Sportmonks Layer 2 activation (2026-11-07)

- Added paginated season discovery, teams-by-season, standings-by-season, and fixtures-by-season methods. Pagination must terminate cleanly; partial collections are rejected.
- Added `sportmonks_layer2.py` to normalize Sportmonks fixture participants, completed match states, current scores, statistics, standings positions, and team history into the existing profile structure.
- Current-season app flow now uses Sportmonks for seasons after 2024 and no longer requires an API-Football key for those seasons. Historical seasons 2022–2024 continue using API-Football.
- The app uses Sportmonks league, season, and team IDs directly; it does not attempt to equate provider IDs across APIs.
- Only completed fixtures with both team scores are included. Five completed matches remain the minimum; ten are used when available. Latest five / previous five weighting remains in the existing model.
- Opponent strength is derived only from available standings positions. Missing positions and statistics remain unknown. Player availability and lineups remain unknown unless a verified source is added; no score is inferred from an empty injury list.
- Sportmonks statistics are mapped by returned statistic type names. Pass counts are not treated as pass accuracy.
- Added focused normalization tests in `test_sportmonks_layer2.py`. These tests have been committed but have not yet been confirmed by a CI run.
- API Ninjas and Highlightly remain connected for diagnostics/canonicalization; their match records are not yet included in multi-source field-level corroboration. LiveScoreFootball remains gated by the existing exact crosswalk.


## Independent result corroboration milestone (2026-11-07)

The repository now includes `provider_corroboration.py`, which connects the Highlightly and API Ninjas adapters to the existing canonical match identity and multi-provider reconciliation functions for a selected Sportmonks competition/season.

- Sportmonks completed fixtures are normalized as the anchor records.
- Highlightly is queried with its documented `leagueName`, `season`, `countryName`, `limit` and `offset` match filters, with bounded pagination.
- API Ninjas is queried for each selected team using its documented team, league and season match-history filters. The competition must have one exact name match in the adapter's league catalogue.
- Every candidate must match competition key, season, home/away team names and kickoff within the canonical five-minute tolerance. No provider IDs are equated across systems.
- Provider fetch timestamps, namespaced fixture/team IDs, selected values, corroborating sources and conflicting sources are retained.
- Missing country identity in Highlightly records is not accepted when a country filter was requested. Mismatched season, league, team or kickoff records do not join.
- API Ninjas does not contribute statistics, injuries or lineups. This integration is specifically for result/fixture corroboration.
- Streamlit exposes a checkbox to run the independent result cross-check during a current-season Sportmonks prediction. It is disabled by default because it is diagnostic-only and adds provider latency; users can enable it when they want an independent audit.
- The report is diagnostic only. It does not overwrite Sportmonks Layer 2 histories, team profiles, prediction inputs, TVD or model weights. Conflicting scores are displayed and never averaged.
- Historical API-Football seasons remain outside this current-season Sportmonks corroboration path.

Tests are in `test_provider_corroboration.py`, covering Sportmonks normalization, three-provider conflicts, country mismatch rejection, missing clients and team mismatch rejection.

### Remaining integration boundary

This milestone activates independent corroboration for recent match results. It does not yet merge Highlightly/API Ninjas statistics, player availability, lineups or squads into the Layer 2 team profiles. Those require separate endpoint-specific canonicalizers, field-level validation and identity mapping before use. Unknown values remain unknown.


## Sportmonks statistics and fixture-detail milestone (2026-11-07)

- Sportmonks match statistics are normalized into a conservative canonical set before tactical indicators consume them. Possession and pass-accuracy fractions (for example, 0.82) are converted to percentage points (82.0); percent strings (for example, "60%") are normalized consistently.
- Statistic names are mapped only where the meaning is supported. Shots accuracy is not treated as pass accuracy or shots-on-target count. Unknown statistic types remain outside the tactical feature set.
- Each normalized statistic retains its raw value, provider, fixture ID, season ID, source statistic type ID/name, and fixture update timestamp where supplied. Streamlit displays these observations in the match-statistics expander.
- The Streamlit flow now looks for an exact upcoming fixture with the selected home team, away team, orientation, and Sportmonks season. It does not substitute either team's unrelated next match.
- For that exact fixture only, the app requests Sportmonks lineups, formations and sidelined player records. Provider-reported sidelined records are shown separately; no player-availability rating is inferred from a list or its absence.
- Lineup confirmation remains "unknown" unless explicit confirmation metadata is parsed and verified. Predictive or unconfirmed lineups are not represented as confirmed.
- If the exact fixture is absent, the endpoint is unavailable, or subscription coverage blocks the includes, the app leaves those fields unknown and continues the prediction with existing inputs.
- API Ninjas is not used for statistics, injuries or lineups. Highlightly match-statistics and lineup endpoints remain a separate corroboration milestone.
- No model weights, latest-five/previous-five recency weighting, Layer 1 calculations, or TVD rules were changed.

Official endpoint references: Sportmonks fixture includes support lineups, formations, statistics and sidelined; Sportmonks documents sidelined.player / sidelined.sideline for player and absence details. Highlightly provides per-match statistics and lineups endpoints; its lineup feed is documented as available from approximately 40 minutes before kickoff until 120 minutes after, refreshing every 15 minutes, while match statistics refresh every five minutes.


## Highlightly match statistics and lineup corroboration (2026-11-07)

- Added `highlightly_match_enrichment.py` as a diagnostic-only integration.
- The app exposes a separate opt-in checkbox because the enrichment may make up to 20 match-statistics requests (latest 10 completed matches per selected team), plus one lineup request for the exact upcoming selected fixture.
- Highlightly matches are filtered by competition, country and season; a match is joined to Sportmonks only when competition key, season, home team, away team, orientation and kickoff (within five minutes) all match.
- Statistics use Highlightly's documented response shape: team object plus a list of `displayName` / `value` observations. Known metrics are normalized conservatively; percentage fractions are converted to percentage points.
- Cross-provider statistic comparisons are only shown for metrics supported by both providers under the same canonical name and compatible units. The report preserves both values, the difference and the tolerance. It never averages or overwrites either value.
- Unknown Highlightly statistic labels remain visible as raw observations but are not compared or used by the model.
- Upcoming lineups are requested only after an exact scheduled Sportmonks fixture is matched to a Highlightly match. Initial lineup rows are flattened according to the documented nested grid; substitutes remain separate.
- Highlightly lineup status is labeled `provider_reported`, not independently verified by the app. If the endpoint is not yet available, returns no lineup, or cannot be matched, lineup data remains unknown.
- API Ninjas remains outside this statistics/lineups integration. No injury or suspension claims are inferred from Highlightly's lineup endpoint.
- The existing result corroboration checkbox and new statistics/lineups checkbox are independent. The new checkbox defaults off to protect API quota; enabling it can make up to 20 stats calls plus one lineup call.
- No prediction weights, latest-five/previous-five 60/40 recency weighting, Layer 1 calculations, tactical scoring rules or TVD logic were changed.

Official Highlightly documentation: match statistics return per-team `statistics` items with `displayName` and numeric `value`, refreshing every five minutes; lineups return home/away formations, nested initial lineups and substitutes, available from 40 minutes before kickoff to 120 minutes after kickoff, refreshing every 15 minutes.


## Highlightly player and team-season performance diagnostics (2026-11-07)

An opt-in diagnostic path now uses the exact selected-fixture Highlightly lineup to query player season statistics and team-season aggregates.

- Player IDs come only from the exact provider-reported starting lineups. The integration does not perform name-only joins.
- Each player response is filtered to exact normalized club name, competition name and selected season. Only documented per-competition fields are surfaced: appearances, minutes, goals, assists, penalties, own goals, cards, clean sheets, goals conceded and substitutions.
- Team statistics are requested with the documented `fromDate` parameter and `Africa/Nairobi` timezone, then filtered to exact competition and season. Total, home and away aggregates are preserved as returned.
- The UI is separately opt-in. It makes at most 22 player-stat requests plus two team-stat requests, and only when the exact selected-fixture lineup is available. Missing IDs, unavailable lineups and unmatched competition/season/club rows remain unknown.
- Player/team statistics are diagnostic only. They do not change the 5% player-availability weight, tactical ratings, Layer 2 profiles or predictions. Statistics do not establish injury status or guaranteed availability.
- The Highlightly statistics endpoints refresh on a daily basis for player statistics and after matches for team statistics; exact account plan coverage remains provider-dependent.


## Cross-competition player-stat validation and Opta benchmarking (2026-11-07)

### Prediction ledger and evaluation
- `prediction_evaluation.py` creates an auditable pre-match prediction record with competition/country/season, home/away teams, fixture/provider IDs where available, prediction timestamp, kickoff, 1X2 probabilities, model version and the protected 60/40 recency policy.
- The Streamlit app keeps a session ledger and supports CSV export/import so records can be carried across app restarts. Streamlit session memory is not treated as permanent storage.
- Final home/away goals can be entered in the ledger after the match. Evaluation excludes forecasts not demonstrably timestamped before kickoff. The evaluator recomputes eligibility from prediction/kickoff timestamps rather than trusting imported boolean flags, requires identifiable fixture identity for scoring, and uses only the latest valid pre-kickoff forecast per fixture to avoid duplicate-match inflation. Repeated and unidentifiable rows are reported separately.
- Reports accuracy, multiclass Brier score and log loss, plus model metrics by competition.
- Opta comparison uses only completed fixtures for which both model and Opta probabilities are recorded. It reports both on the same fixture subset, never compares unrelated samples.
- No automatic model fitting, weight changes or probability calibration is performed by the evaluation report.

### Player-stat validation and look-ahead protection
- Player and team season aggregates are diagnostic observations, not injury or availability status.
- Player-stat snapshots are eligible for historical evaluation only when the enrichment request has completed before the exact fixture kickoff. The completion timestamp is recorded after all provider calls.
- Post-kickoff snapshots are excluded from the pre-match snapshot count to prevent future-data leakage.
- Cross-competition coverage is summarized by competition as predictions are collected and exported/imported.
- A future candidate player-impact feature must be evaluated as a separate experimental signal. It must not be relabelled as the existing 5% player-availability input, which requires verified availability evidence.
- Any proposed model change requires a sufficiently large, chronological, out-of-sample evaluation and must beat the unchanged baseline on proper scoring rules before it is considered. No threshold or sample-size claim is treated as a guarantee.

### Opta's role
- Public Opta Analyst Supercomputer match probabilities can be recorded manually as an external benchmark with the article URL and capture timestamp.
- Official Opta material describes the match outcome model as using betting-market odds and Opta Power Rankings. It is therefore a useful strong comparator, but not a pure odds-free independent model and not ground truth.
- The app does not scrape Opta, reverse engineer its proprietary model, or copy its probabilities into our model inputs.
- Licensed Opta data feeds/APIs remain a later commercial integration option, subject to coverage, demo access, pricing, redistribution rights and written licensing terms.
- Benchmark scores are reported only on the same fixture set as our own forecasts.


## Operational hardening and runtime validation (2026-11-10)

### Data quality and provenance
- Layer 2 history diagnostics now consume the same shared eight-metric definitions as the system-wide statistics coverage report. Shots on Target and Shots on Goal are treated as aliases for one canonical input; the app does not double-count them.
- Repository fixture rows carry separate `history_repository_collected_at` and `history_provider_updated_at` timestamps. Direct live-fetch time remains `history_collection_fetched_at`; repository ingestion time is never mislabeled as a direct API fetch. Provider update time remains unknown when the source does not supply it.
- Sportmonks and Highlightly statistic parsers reject non-finite and negative observations and percentage values above 100; supported fractional percentages are normalized, and explicit percent units are preserved.
- Sportmonks provider IDs and fixture season IDs must be positive integers or digit strings; booleans and fractional values are rejected rather than truncated or attributed to the wrong team.
- The latest verified Chelsea–Leeds run reported 10 completed matches per team, 8/8 core match-statistic metrics with 100% coverage for both teams, zero duplicate fixture IDs, and healthy readiness diagnostics.

### Prediction result automation
- `sync_prediction_results.py` runs from the six-hour scheduled controller and is also available as the manual `result_sync` operation.
- It reads the Neon ledger, groups duplicate forecasts by exact Sportmonks fixture ID, and updates only blank result fields after verifying exact fixture ID, home/away identity, competition, season, completed state and final 90-minute score.
- Existing manual scores and model probabilities are preserved. AET/penalty totals are not substituted for the 90-minute score.
- The first live manual sync read 72 ledger rows and found no eligible unfinished results; it correctly made no changes. The evaluation report showed 21 unique pre-match fixtures and one completed verified fixture.

### Runtime optimization
- Independent Highlightly/API Ninjas result corroboration remains available, but is now opt-in by default because it is diagnostic-only and does not change prediction inputs.
- Same-fixture benchmark: Chelsea vs Leeds United, 2026-11-10. Before the change, elapsed time was 60.99 seconds and optional corroboration consumed 11.157 seconds. Two post-change runs took 46.19 and 49.61 seconds, with corroboration at 0 seconds in both. The 1X2 probabilities remained identical at 45.9% / 26.9% / 27.2%. The latest run completed with zero app errors.
- Timings vary with cache and provider response latency; the measured reduction is a real run comparison, not a guaranteed runtime.

### Evaluation boundary and remaining work
- The current performance report evaluates prospective saved forecasts as their results are verified. It is not a retrospective historical walk-forward backtest.
- Only one unique completed fixture has a verified result against the current minimum descriptive sample of 30. Accuracy, Brier score and log loss remain provisional; no model calibration or weight changes are justified.
- As of 2026-11-10, Highlightly match statistics and exact-fixture lineups have opt-in, field-level Layer 2 fallbacks for missing values only; recent result candidates can enter history only after exact Sportmonks verification and score agreement. Sportmonks values remain authoritative. Player statistics and team-season aggregates remain diagnostic-only. Highlightly is not used to infer injuries or player availability. A future player-impact feature must be a separate experimental signal and pass chronological, out-of-sample evaluation before any production use.
- Further provider integration must remain field-level and fail-closed: exact competition, season, fixture, team orientation, freshness, canonical metric, provenance and conflict handling are required. Missing or conflicting values must not be averaged or silently imputed.

Validation at this milestone: 28/28 application smoke checks, 5/5 live provider checks and 344 unit tests passed. The deployment probe reached Streamlit and received its authentication redirect; this confirms protected reachability, not an authenticated health response. The CI probe reports `protected_reachable`; application code smoke and live provider checks run separately.

## Layer completion status (2026-11-10)

| Layer | Scope | Status and evidence |
|---|---|---|
| 1 | Provider/API setup | Complete: authenticated provider adapters, request diagnostics, credential isolation and provider readiness checks. |
| 2 | Data collection, normalization and storage | Complete: Sportmonks current-season collection, API-Football historical path, canonical fixture/state normalization, shared eight-metric definitions, strict provider-ID/season/score/stat parsing, timestamp provenance and Neon prediction ledger. |
| 3 | Prediction validation | Complete for the current evidence threshold: exact provider-ID, fixture/team/competition/season/state checks; 10 completed history matches per team; 8/8 core statistics at 100% coverage; 4/5 tactical pairings available (72% coverage, above the 70% integration threshold). Missing counter-attack evidence remains unknown, never imputed. |
| 4 | Probability validation | Complete: 1X2 probabilities must be finite, within 0–100 and sum to 100; model weights remain unchanged and sum to 100%. Proper scoring and calibration diagnostics are calculated by the evaluation layer, but empirical calibration is not established yet. |
| 5 | Prediction evaluation | Operational: timestamped prediction ledger, verified-result synchronizer, accuracy/Brier/log-loss and calibration reporting. The latest ledger has 74 saved predictions and one unique completed fixture with a verified result, below the 30-fixture minimum; the six-hour sync will continue accumulating evidence. |
| 6 | Authenticated deployment and reliability | Operational: authentication-protected Streamlit deployment, 28/28 code smoke checks, 5/5 live integrations, 341 unit tests and scheduled controller checks. CI confirms protected reachability; it cannot verify an authenticated user session without a deployment login. |

The application is operational across all six layers. The remaining non-blocking work is longitudinal rather than a missing core feature: allow verified outcomes to accumulate to at least 30 unique fixtures before making model-accuracy or calibration claims. Keep the agreed model weights and recency weighting fixed until that evidence exists.

### Snapshot validation coverage correction (2026-11-07)
- Player-level and team-season statistics are now counted separately in the prediction ledger.
- A team-only statistics response cannot be mislabeled as a player-stat snapshot.
- Both snapshot types must have completed before the selected fixture kickoff to count toward pre-match coverage.
- API request counters increment when a request is attempted, including failed calls, so quota diagnostics do not undercount exceptions.
- The app reports player-stat and team-season snapshot counts independently.


## Opt-in Highlightly missing-stat fallback (2026-11-10)

The current Layer 2 flow now supports a controlled field-level fallback from Highlightly into the selected teams' recent match profiles.

- The sidebar option is disabled by default to protect Highlightly quota and keep the existing Sportmonks-only path unchanged unless explicitly enabled.
- The fallback uses the same exact-match collection gate: competition, country, season, home/away orientation, team identities and kickoff within five minutes must match the Sportmonks anchor fixture.
- It considers the latest ten completed Sportmonks matches per selected team. It can populate both a team's own match statistics and the opponent-statistics view for that exact fixture.
- Only supported canonical metrics with valid finite, non-negative values and valid percentage ranges are eligible.
- A Highlightly value is inserted only when the corresponding Layer 2 field is missing. Existing Sportmonks values remain authoritative, whether they agree or conflict; no values are averaged.
- Duplicate Highlightly rows that disagree for the same canonical metric are skipped as ambiguous.
- Added values carry provider, Sportmonks fixture ID, Highlightly match ID, raw and normalized values, collection start and completion timestamps, and a fallback marker in match-level provenance and diagnostics.
- The team's tactical summary is recomputed from the enriched match rows so supported missing statistics can contribute to the existing tactical analysis. Prediction weights and 60/40 history weighting are unchanged.
- The separate tactical_evidence object consumed by automatic TVD is deliberately not rebuilt from Highlightly. TVD continues to use its existing primary-source evidence path until its own provider-quality and league-reference integration is separately validated.
- This fallback does not infer injuries, player availability, confirmed lineups or squad membership. Those fields remain on their existing verified-source rules.
- The opt-in fallback is not a blanket promotion of Highlightly to primary provider status. It fills only missing fields after exact identity checks and preserves Sportmonks precedence.

The fallback is covered by unit tests for missing-field fill, primary-value preservation, opponent-stat attribution, invalid timestamps, team-identity mismatch and conflicting duplicate observations. Live account coverage and authenticated runtime behavior still require deployment-level verification.


## Opt-in Highlightly lineup fallback (2026-11-10)

- A separate sidebar option can use Highlightly lineups only when the exact selected Sportmonks fixture is scheduled and inside the provider's documented lineup request window (40 minutes before kickoff through 120 minutes after kickoff).
- The existing Highlightly match normalizer requires exact home/away team names against the selected Sportmonks fixture. The fallback additionally requires the returned Sportmonks fixture ID to equal the selected fixture ID and each profile's team identity to match its home/away side.
- Provider-reported starters/substitutes are used only when the corresponding Sportmonks lineup is unavailable. Existing Sportmonks lineups are never overwritten.
- The source, Highlightly match ID, Sportmonks fixture ID, collection start/completion timestamps and provider-reported confirmation status are retained.
- This fallback updates only the profile's lineup display/readiness evidence. It does not populate injury status, availability scores, squad membership, or any player-availability assessment. Missing availability remains unknown.
- The option is disabled by default. A lineup report outside the provider time window, with a mismatched fixture/team, without starters, or without a valid collection completion timestamp is not used.

Unit tests cover exact-fixture matching, preservation of existing Sportmonks lineups, missing/invalid timestamps, and the rule that player availability is not changed.


## Opt-in verified result-history fallback (2026-11-10)

The app now has a separate opt-in control to fill missing recent result history using Highlightly or API Ninjas as discovery/corroboration sources and Sportmonks as the authoritative result source.

- A candidate from either secondary provider is eligible only when one Sportmonks fixture matches the exact season, competition, home/away team IDs and kickoff, is explicitly completed, has valid non-negative full-time scores, and its score exactly agrees with that candidate provider.
- Ambiguous duplicate exact fixtures, missing verification timestamps, score conflicts, incomplete matches, unresolved team IDs and non-exact kickoff matches are rejected. Targeted Sportmonks date responses are cached per UTC date and capped at ten unique-date requests per run.
- The appended history row uses the verified Sportmonks score and namespaced provider identity. The candidate provider (Highlightly or API Ninjas) is retained only as the independent corroboration reference.
- The fallback is disabled by default and runs only when explicitly enabled. It is bounded to the existing ten-match history window and does not invent statistics or opponent strength.
- Recent form, goals for/against, venue ratings and the tactical summary are recomputed from the updated ten-match window. Match statistics remain empty for the inserted result unless separately sourced and validated. Existing TVD tactical_evidence is deliberately not rebuilt by this result-only fallback.
- API Ninjas remains a separate optional corroboration path; it is not required for this fallback and does not supply missing match statistics.


## Opt-in LiveScoreFootball missing-result fallback (2026-11-10)

- The fallback is disabled by default and is independent of the Highlightly/API Ninjas result-history option.
- It first filters the already-collected Sportmonks season fixtures for explicitly completed matches involving the selected teams that have no explicit CURRENT score rows. Fixtures with any CURRENT score row are left untouched, including malformed or partial current rows; period-only scores are not treated as full-time results.
- Before requesting LiveScore data, it requires fresh global LiveScore metadata and a unique exact Sportmonks-to-LiveScore competition crosswalk for the requested season, including active status, hasData and fresh per-competition fixture sync time.
- It requests only the UTC dates needed for eligible missing-score fixtures, caches repeated dates and caps requests at ten unique dates per run.
- A LiveScore event is accepted only when exactly one completed, score-valid event matches the Sportmonks anchor fixture's exact competition key, home/away team names and kickoff within five minutes.
- The inserted history row retains the Sportmonks fixture ID as its identity anchor and LiveScore event ID/slug, per-competition sync timestamp, global sync timestamp, raw source update time and collection completion timestamp as score provenance.
- Existing Sportmonks scores are never overwritten. LiveScore does not supply statistics, standings, lineups, injuries or player availability through this fallback. The TVD tactical_evidence object and all model weights remain unchanged.
- The fallback is covered by mocked-client tests for global/per-competition freshness, exact crosswalk, exact identity, invalid scores, ambiguity, request caching, existing-score preservation and profile provenance.


## Cross-provider provenance audit (2026-11-10)

- Sportmonks fixture states used by corroboration now require exact documented finished/live/scheduled labels or state IDs. Substring matches such as "unfinished" and "not finished" remain unknown.
- Malformed participant and score envelopes are ignored safely by the corroboration normalizer.
- Conflicting duplicate Sportmonks CURRENT score rows no longer use last-row-wins behavior. The affected participant score remains unknown in canonical history, corroboration and secondary-result verification.
- Provider IDs remain namespaced. Cross-provider joins still require competition, season, home/away orientation and kickoff agreement; candidate result imports still require exact Sportmonks fixture and score agreement.
- Highlightly statistics, lineups and player/team-season enrichment remain opt-in and retain provider provenance. Missing statistics, injury evidence and player availability are not inferred.
- No prediction weights, tactical evidence rules or 60/40 recent-match weighting were changed by this audit.


## Layer 3 — data verification, reconciliation and quality control (started 2026-11-10)

Layer 3 adds evidence-based checks around the canonical records delivered by Layer 2. It does not change Layer 1 model calculations or Layer 2 provider priority.

### First implementation milestone: source reliability diagnostics

- `source_reliability.py` calculates secondary-provider agreement against the current-season Sportmonks primary using exact-identity, freshness-eligible records produced by the existing corroboration collector.
- Score reliability is measured as an exact home-away full-time score pair per fixture, not as two independent score-field votes.
- Status and kickoff agreement are reported separately. Kickoff agreement uses a five-minute tolerance, matching the canonical fixture-identity window.
- Each provider report includes compared/agreed/disagreed counts, agreement percentage, a 95% Wilson interval, and the configured minimum sample size.
- A minimum of 30 paired score fixtures is required before a descriptive score is marked sample-sufficient. Smaller samples are explicitly labelled insufficient; no reliability ranking is inferred.
- Duplicate observations from one provider/field are excluded as ambiguous.
- Reliability is diagnostic only. It cannot change provider priority, substitute data, prediction inputs, weights, TVD or tactical recency weighting.
- The Streamlit data-collection report archives the reliability evidence and exposes it in the provider corroboration panel.
- Historical API-Football seasons are not compared against Sportmonks by this report because the current corroboration collector is anchored to Sportmonks.

### Second implementation milestone: field-level data quality controls

- Sportmonks match statistics now detect duplicate canonical observations per fixture/team. Conflicting values are excluded rather than using last-row-wins or averaging; valid-plus-invalid duplicates are excluded regardless of row order. Invalid supported values are reported separately and do not count as usable coverage.
- Statistics conflicts and invalid observations are carried into team profiles, prediction-input quality warnings and the archived Streamlit collection evidence. Optional statistic gaps remain unknown; the gate does not block a prediction solely because an optional statistic is absent.
- Highlightly lineup normalization requires exact home/away team names and provider team IDs, valid stable IDs for every starter and substitute, and no duplicate player ID within either team's combined starting/substitute list. Existing exact-fixture, kickoff and collection-timestamp checks remain in force. Existing primary lineups are not overwritten.
- Sportmonks player/season enrichment now rejects boolean and fractional team, season and player IDs rather than coercing them. Each current-squad player must have exactly one matching team-season statistics row with matching player identity and valid minutes evidence.
- Fixture-specific sidelined/injury records are checked against the current squad and, when supplied, exact fixture, team and season identity. Invalid dates, malformed status values, unknown players and mismatched scope keep availability unknown.
- Missing, conflicting or malformed evidence is not repaired or imputed. These controls are quality diagnostics and do not change provider priority or prediction weights.
- Regression tests cover conflicting/invalid statistic duplicates, resulting coverage, lineup player identity/duplicates and malformed player/injury/team/season identifiers.
- GitHub Actions validation passed: compile step and all 409 Python unit tests.

### Third implementation milestone: prediction-input quality gates

- The existing fail-closed history gate now also checks the age and validity of the collection timestamp for each team's match-history evidence. Evidence older than 24 hours or timestamped in the future blocks prediction; a missing/invalid timestamp downgrades readiness because freshness cannot be established.
- When an exact upcoming fixture is verified, stale fixture retrieval evidence blocks fixture-specific prediction. Unknown fixture freshness is surfaced as an attention warning; an unverified upcoming fixture does not prevent non-fixture-specific matchup analysis.
- Missing core fields (fixture ID, score pair, kickoff, selected team identity and minimum history depth), duplicate fixtures and invalid chronology continue to block prediction. Optional statistics, lineups and injury/availability gaps remain unknown and do not become fabricated zeros.
- Conflicting or invalid optional statistic observations remain excluded from the usable data and downgrade readiness with explicit warnings; they are never averaged or silently selected. Core match-history conflicts remain blocking.
- The report now exposes the fixture-quality checks and freshness threshold, and the Streamlit prediction flow passes the exact fixture readiness evidence into the input gate.
- The gate does not modify collected inputs, provider priority, model weights, TVD rules or the 60/40 tactical recency weighting.

### Fourth implementation milestone: persistent provider reliability history

- Every current-season collection with exact cross-provider fixture comparisons appends its matched field-level observations to the CockroachDB provider_reliability_history table. Each row records competition, season, primary provider, capture time and matched fixture evidence.
- History is append-only and scoped by competition and season. The app loads the latest 500 collection runs from the preceding 90 days and recomputes the reliability report from the combined evidence.
- Repeated fixtures across collection runs are deduplicated by canonical competition key, season, UTC kickoff and home/away team identity before sample counts and agreement percentages are calculated. Records without complete canonical identity are excluded.
- Score-pair agreement, separate status/kickoff agreement and Wilson confidence intervals retain the original definitions. A minimum of 30 unique paired score fixtures remains required for a sample-sufficient descriptive score.
- If CockroachDB history is unavailable, the current-run diagnostic remains available and the UI explicitly labels the report as non-persistent; a storage failure never blocks prediction or changes its inputs.

### Third implementation milestone: conflict triage and immutable audit records (completed 2026-11-10)

- `conflict_audit.py` creates one event per conflicted field from exact reconciled fixtures. Each event retains canonical fixture identity, every provider observation and source ID, the selected value/provider, corroborating/conflicting providers, the decision reason and timestamp.
- `provider_data_storage.py` appends events to CockroachDB's `provider_conflict_resolution_audit` table and loads the latest 90-day audit history by competition and season.
- The Streamlit report exposes persistent audit history and distinguishes a configured-priority policy selection from a human override. No manual override is performed.
- If there is no unique eligible selected observation, the field remains explicitly unresolved. No averaging, guessing or fabricated replacement is allowed.
- Audit persistence failures are diagnostic only and do not block prediction. Current-run source observations remain visible.
- This milestone does not change provider priorities, model inputs, prediction weights, TVD or tactical recency weighting.

### Fourth implementation milestone: dynamic competition discovery and registration (completed 2026-11-10)

- `competition_registry.py` pairs Sportmonks league and season records only through exact provider-native `league_id` relationships, rejects orphan and ambiguous IDs, and creates stable provider-namespaced identities.
- `provider_data_storage.py` persists discovered competition-season records in CockroachDB's `provider_competition_registry` table. Repeated discovery refreshes descriptive provider metadata without changing registered identity.
- The Streamlit collection flow displays the discovered catalogue and registration outcome. Discovery and registration are separate from cross-provider identity verification and prediction readiness.
- Cross-provider matching produces candidates only when competition name, country and season label agree. Even then it remains explicitly unverified; matching numeric IDs or names never auto-links providers.
- Every discovered row starts as `prediction_ready = false`. Existing selected-competition, season, team and fixture validation gates remain in place.
- No provider priority, model input, prediction weight, TVD or tactical recency weighting changed.

### Fifth implementation milestone: league coverage dashboard (completed 2026-11-10)

- A read-only dashboard classifies every registered provider competition-season as discovered, supported, incomplete or explicitly prediction-ready.
- "Supported" requires both an implemented provider adapter and configured credentials. A discovered row without confirmed credentials remains visible but is not counted as supported.
- "Incomplete" means supported but not explicitly prediction-ready. Discovery, provider IDs, adapter presence and credentials never promote readiness.
- The dashboard reports counts and per-competition/season reasons, with the selected-season view separated from the all-registry totals.
- Duplicate provider identity keys are counted once. Unknown readiness remains unknown; no missing data is treated as zero or fabricated.
- Tests cover all classifications, unconfigured credentials, duplicate identities and the no-auto-promotion rule.
- No provider priority, prediction input, model weight, TVD rule or tactical recency weighting changed.

### Sixth implementation milestone: historical coverage validation (2026-11-10)

- `historical_coverage.py` loads timestamped prediction-performance archive snapshots and the latest report, retaining parse errors instead of silently dropping unreadable files.
- Archive snapshots are not independent observations. Fixture rows are deduplicated by competition, UTC kickoff, home team and away team; where multiple valid pre-kickoff forecasts exist, the latest forecast before kickoff is selected.
- Rows are excluded when prediction time is missing/invalid or at/after kickoff, score is malformed, actual outcome disagrees with the score, predicted outcome is invalid, or the recorded correctness flag is inconsistent.
- Conflicting archived final scores for the same fixture are excluded as ambiguous. Reported completed counts are compared with the fixture-level history to expose archive inconsistencies.
- The validation reports unique verified fixtures, repeated snapshot rows, invalid rows, ambiguous fixtures, a Wilson interval and progress toward the existing 30-fixture descriptive minimum.
- The Streamlit performance panel reads the repository's archived JSON reports and shows the historical coverage audit. A sample meeting 30 remains descriptive only; this report never authorizes provider-priority or model-weight changes.
- Current archive evidence remains insufficient: the latest report contains one unique completed pre-match fixture, with 20 other unique pre-match fixtures awaiting verified scores. Repeated archive snapshots do not increase that count.
- Regression tests cover snapshot deduplication, latest pre-kickoff forecast selection, leakage and score validation, ambiguous outcomes, minimum sample labeling, report inconsistencies and archive parse failures.

### Layer 3 completion boundary

All eight implementation objectives are complete when this milestone is merged. Historical evidence is still longitudinal: the system must continue collecting independently verified outcomes until at least 30 unique fixtures are available before making descriptive performance claims. No provider priority, prediction input, model weight, TVD rule or tactical recency weighting is changed by this milestone.
