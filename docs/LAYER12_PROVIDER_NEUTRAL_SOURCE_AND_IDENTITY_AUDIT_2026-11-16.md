# Layer 12: Provider-neutral source and identity audit

**Audit date:** 16 November 2026  
**Status:** Source evidence staged; canonical identity approval remains on hold.

## Scope and safety

The provider-neutral source repository now stores provider-native competition, season and team records independently of the legacy Sportmonks-backed repository.

The following operations have been completed:

- LiveScoreFootball: staged competition and team participant observations for the 2026/27 Bundesliga and Ligue 1 date window.
- Sportmonks: copied the existing competition, season and team catalogue into provider-source evidence tables. Legacy rows were read-only.
- API-Football: staged its 2024 free-plan competition, season and team catalogue.
- Highlightly: staging was attempted but returned HTTP 429; no Highlightly rows were written.
- Provider-neutral identity candidate generation and source-evidence audits were read-only.

**No fixtures or fixture statistics were imported into the provider-source repository. No canonical IDs were assigned, no cross-provider links were created, and the prediction model and prediction ledger were untouched.**

## Staged source catalogue

| Provider | Competitions | Seasons | Teams | Evidence notes |
|---|---:|---:|---:|---|
| API-Football | 5 | 5 | 98 | 2024 catalogue season; country and competition type present for all 5 competitions; team country and national/club flag present for all 98 teams |
| Sportmonks | 4 | 7 | 88 | Existing legacy catalogue copied as source evidence; country missing for all 88 team rows |
| LiveScoreFootball | 2 | 0 | 36 | Bundesliga and Ligue 1; 2026/27 fixture-participant observations, not a complete authoritative season roster |
| Highlightly | 0 | 0 | 0 | HTTP 429 prevented staging; no cached or stale roster substituted |
| **Total** | **11** | **12** | **222** | Source evidence only |

API-Football's free plan rejected season 2026 and explicitly allowed seasons 2022–2024. The catalogue stage therefore uses 2024 for competition identity and historical team evidence. It does not treat those 2024 teams as the current 2026/27 roster.

LiveScore's provider catalogue did not supply a competition type in the observed records. Its two competition names are provider-native labels, “German Bundesliga” and “French Ligue 1”. Team-country values were not supplied for the 36 fixture-participant records and were left null.

## Cross-provider competition candidates

The deterministic identity audit found three exact name/country/type candidates shared by API-Football and Sportmonks:

| Competition | Country | API-Football ID | Sportmonks ID | Provider type evidence |
|---|---|---:|---:|---|
| Premier League | England | 39 | 8 | League / league |
| La Liga | Spain | 140 | 564 | League / league |
| Serie A | Italy | 135 | 384 | League / league |

Each pair has status **shared identity candidate — manual review required**. These are not approved mappings. The candidate key is a deterministic review aid, not an application-owned canonical ID.

The audit found nine competition identity-key candidates in total and three shared cross-provider candidate groups. There were no same-provider duplicate competition-key groups.

LiveScore's Bundesliga and Ligue 1 rows were held because competition type is unknown and their provider-native names do not exactly match the API-Football labels. No alias was inferred.

## Seasons and teams held

- **12 season source rows** are held. Their parent competition IDs are provider-scoped IDs, not approved canonical competition IDs. A season key cannot be finalized until its parent competition has been approved.
- **222 team source rows** are held. API-Football supplies country and club/national flags for 98 teams, but gender, age-group and squad scope are not established. LiveScore's 36 participant rows lack team-country and team-type evidence. Sportmonks' 88 legacy team rows lack country and team-scope dimensions.
- No team nationality is inferred from a league's country.
- No team identity is inferred from exact names alone.

## Required next steps

1. Implement an application-owned canonical identity registry with a separate reviewer-approved link table.
2. Require explicit reviewer, rationale and source evidence for every promotion. Do not auto-promote candidate keys.
3. Review the three competition pairs above before any canonical IDs or links are created.
4. Approve seasons only after their parent competition identity is approved.
5. Obtain provider-supplied team country, team type, gender, age-group and squad-scope evidence before creating canonical team identities.
6. Retry Highlightly only after its rate limit/quota permits; do not substitute guessed metadata.
7. Keep OpenScores restricted to historical observations/reconciliation, never future-fixture discovery.

## Audit guarantees

At the end of this audit:

- canonical_entities_created = 0
- cross_provider_links_created = 0
- fixtures_ingested = 0
- fixture_statistics_ingested = 0
- prediction_model_modified = false
- prediction_ledger_touched = false

The provider-neutral source repository is now multi-provider. The canonical identity layer is not yet promoted: that requires explicit review and verified evidence.
