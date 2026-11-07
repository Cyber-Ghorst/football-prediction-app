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

Provider roles are domain-specific. A provider is not assumed to be authoritative for every field.

| Provider | Intended role | Important limitation |
|---|---|---|
| LiveScoreFootball public API | Primary fixtures, results and standings where verified coverage exists | Public documentation currently identifies England and Spain as its initial verified coverage; do not use it as a global source without verifying league coverage |
| API Ninjas | Independent corroboration and fallback for fixtures, results, standings, clubs and squads | Does not provide the detailed fixture statistics, injuries or lineups required for all Layer 2 tactical/availability inputs |
| Highlightly | Supplementary match detail, statistics and player data | Plan-dependent coverage, quotas and returned fields must be checked |
| API-Football v3 | Supplementary fixture statistics, injuries and lineups; secondary fixtures/standings source | Competition/season coverage flags and plan limits must be checked before treating a missing field as a real absence |

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

## Domain-specific priority

- Fixtures/results/standings: LiveScoreFootball first only for leagues whose coverage has been verified; API Ninjas and Highlightly are independent corroboration/fallback sources. API-Football is an additional fallback.
- Detailed match statistics: API-Football and Highlightly, subject to per-competition coverage. Missing statistics remain unknown.
- Injuries/lineups: API-Football first where coverage is enabled; Highlightly may supplement only when the field is explicitly present and can be mapped to the correct fixture/team.
- Player profile/statistics: Highlightly first; API Ninjas squad data and API-Football player data may supplement where supported.
- Opponent strength: use a validated standings table from the same competition and season as the match. Never compare raw ranks across different competitions without normalization.

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
- No LiveScoreFootball adapter has been added: the provider name has not been matched to a verifiable official API documentation/base URL. Do not send credentials or assume coverage until the exact official product URL is confirmed.
- Credentials are never displayed. Configure APISPORTS_API_KEY for API-Football, API_NINJAS_API_KEY for API Ninjas, and HIGHLIGHTLY_API_KEY for Highlightly. The Highlightly client retains API_FOOTBALL_KEY as a legacy fallback only.
- Live provider health, quota, account coverage and deployed Streamlit configuration remain unverified until credentials and runtime access are available.


## LiveScoreFootball provider identification and adapter

The user identified https://github.com/rezarahiminia/livescoreFootball. This is a public, database-backed REST API hosted at https://worldcup26.ir, not the separate upstream listener. The documented customer API does not require an API key. It reads stored MongoDB snapshots; a separately operated listener fetches upstream data and writes normalized records. Freshness therefore depends on listener synchronization and must be checked using /get/soccer/meta (lastSuccessfulSyncAt and generatedAt) and per-league lastSyncedAt.

The read-only adapter is livescore_football.py and defaults to https://worldcup26.ir. Supported documented endpoints include /health, /get/soccer/meta, /get/soccer/leagues, /get/soccer/{league}/fixtures, /get/soccer/{league}/scoreboard, /get/soccer/{league}/standings, /get/soccer/{league}/summary, and /get/soccer/{league}/events/{eventId}/plays. Override the base URL with LIVESCORE_FOOTBALL_BASE_URL. No credential should be configured for this public service unless its operator changes the documented access policy.

The repository README verifies initial competition coverage focused on England and Spain: Premier League, EFL competitions, FA Cup, LaLiga, LaLiga 2, Copa del Rey and women's competitions. UEFA Champions League and other countries are not to be assumed available. The service does not fetch upstream data on customer requests, and its API documentation warns that stored snapshots can be delayed or incomplete.

Current app status: the read-only adapter and mocked contract tests exist, and the provider is listed first for fixtures/results/standings in provider_core.py. It is not yet connected as an automatic Layer 2 fallback. Do not treat this source as a guaranteed live feed or infer missing statistics, injuries, lineups, or player availability from absent fields.
