# Layer 11 — League coverage audit

**Audit date:** 2026-11-10  
**Objective:** Establish the currently evidenced competition coverage before implementing automatic fixture discovery.  
**Scope:** Existing provider roles, repository integration, runtime diagnostics and the latest recorded LiveScoreFootball catalogue evidence.

## Executive finding

The application has five football data-source adapters, but it does **not** yet have one verified, aggregate count of competitions that are simultaneously discoverable, credential-accessible, fixture-covered, fresh and prediction-ready.

The strongest recent catalogue evidence available for LiveScoreFootball is from **2026-11-10**:

- 35 active competitions across 17 countries.
- 35 competitions reporting stored match data.
- 3,161 stored matches, 863 club records and 42 standings groups.
- 0 international competitions.
- Global service metadata sync was fresh at audit time.

This is a provider catalogue/snapshot count, **not** a claim that all 35 competitions are currently crosswalk-verified or prediction-ready in this app. The LiveScoreFootball service is database-backed and may lag its upstream listener. Its current league records expose coverage counts but no per-competition sync timestamp; therefore the strict per-competition freshness gate verifies 0 of 35 competitions for automatic fallback. Global metadata freshness alone is insufficient.

The repository README still describes a 33-competition catalogue. That figure is stale relative to the 2026-11-07 observation and must not be used as the current count.

## Provider-by-provider coverage and integration status

| Provider | Account/configuration evidence | Competition/season coverage evidence | Fixture-discovery suitability now |
|---|---|---|---|
| Sportmonks | Credential configured in the latest committed runtime diagnostic (2026-11-10 08:02 UTC); primary current-season provider | Account-enabled competitions/seasons only. Latest diagnostic proves one selected 2026/27 Premier League fixture and selected team histories; it does not enumerate the account's full competition catalogue. | Best primary source for current-season fixture discovery after querying its actual account catalogue and season coverage. |
| Highlightly | Credential configured in the latest committed runtime diagnostic; adapter implemented | Official documentation advertises 950+ leagues across 170+ countries. The account-specific catalogue audit returned HTTP 429 twice, so the actual account catalogue count and plan tier remain unverified. | Keep as an existing opt-in corroboration provider; do not promote it to broad fixture discovery until the authenticated catalogue and quota recover. |
| API-Football v3 | Credential configured in the latest committed runtime diagnostic; adapter implemented | Configured account is restricted to seasons 2022–2024. | Not a source for the upcoming 2026/27 fixture window under the recorded account restriction. |
| API Ninjas | Credential configured in the latest committed runtime diagnostic; adapter implemented | No current aggregate account competition catalogue recorded. Latest diagnostic describes it as not yet active in Layer 2 reconciliation. | Candidate secondary discovery/corroboration source after adapter integration and live coverage/quota checks. |
| LiveScoreFootball | Public read-only API; no key required | Fresh 2026-11-10 audit: 35 active competitions across 17 countries, 3,161 stored matches, 863 club records, 42 standings groups and 0 international competitions. | Broad enough to retain as a catalogue/corroboration source. Global and 35/35 per-competition sync checks pass; the existing exact competition/season crosswalk and per-event freshness gates still control each fallback. |

## What the code already supports

- Dynamic provider competition/season registration exists in `competition_registry.py`.
- `league_coverage.py` distinguishes discovered, supported, incomplete and explicitly prediction-ready competition-season records.
- `competition_crosswalk.py` requires exact competition/country matching, season agreement, active/data-backed catalogue status and fresh per-competition sync metadata for LiveScoreFootball mapping.
- Provider IDs remain namespaced; discovery does not automatically prove cross-provider identity.
- The Streamlit sidebar has a **Run provider health & coverage check** action for API-Football status/quota and LiveScoreFootball health, metadata and crosswalk diagnostics.
- A provider's adapter being implemented or its credential being configured does not establish that its entire competition catalogue is integrated or prediction-ready.

## Evidence limitations and unresolved measurements

1. The latest committed system diagnostic (2026-11-10 08:02 UTC) is a selected-fixture readiness report, not an aggregate league-coverage report.
2. It confirms Sportmonks, Highlightly, API-Football and API Ninjas credentials are configured, but does not expose a complete per-provider competition/season count.
3. The 2026-11-10 audit verified global and 35/35 per-competition freshness after correcting the app to read top-level `lastSyncedAt`.
4. Highlightly's authenticated catalogue could not be enumerated because its API returned HTTP 429; the public 950+ figure must not be treated as this account's accessible count.
5. A competition should count toward **usable app coverage** only after the app verifies its provider, competition, season, fixture availability, data freshness and prediction-readiness gates. Raw provider catalogue counts must be reported separately.

## Layer 11 design decision

For the automatic fixture collector:

1. Use Sportmonks as the primary current-season source, querying the account's actual available leagues/seasons at runtime.
2. Treat Highlightly and API Ninjas as secondary candidate sources only after their actual current fixture coverage and quotas are measured and their canonical integration is active.
3. Exclude API-Football from the 2026/27 upcoming-fixture source set unless a fresh account-status/coverage check proves the season restriction has changed.
4. Keep LiveScoreFootball conditional and fail-closed on missing/stale sync timestamps or unverified competition-season mappings.
5. Deduplicate by canonical competition, season, home/away identity and kickoff; never by a provider's numeric ID alone.
6. Report separate totals for discovered competitions, fixture-covered competitions, crosswalk-verified competitions and prediction-ready competitions.
7. If fewer than 90 unique valid fixtures are found inside the rolling seven-day window, report the shortfall. Never fabricate fixtures or extend the window beyond seven days to meet the target.

## Objective 1 outcome

**Completed as a repository/evidence audit.** The app has five adapters and the best recent recorded catalogue is 35 active club competitions on LiveScoreFootball, but no reliable app-wide usable-competition total has yet been established. A fresh credentialed provider-coverage run is a prerequisite to publishing an exact live count.

No prediction weights, TVD rules, provider priorities or production runtime behavior were changed by this audit.
