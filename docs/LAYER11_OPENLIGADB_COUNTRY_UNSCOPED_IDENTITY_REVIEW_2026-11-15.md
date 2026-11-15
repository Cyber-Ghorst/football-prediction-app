# Layer 11 — OpenLigaDB country-unscoped source identity review

**Review date:** 15 November 2026  
**Source report:** `reports/provider_independent_catalogue/openligadb_country_scope_probe_latest.json`  
**Source inventory:** 27 OpenLigaDB records previously held outside country-scoped canonical identity review  
**Disposition:** API scope evidence recovered; candidate records remain source-scoped and unapproved

## Probe outcome

The read-only OpenLigaDB public API probe successfully resolved all **27 of 27** source records to exact league metadata and match lists for season 2026. There were no missing or ambiguous metadata records, empty match lists, or request errors.

- Match rows returned: **2,627**
- Rows with UTC kickoff: **2,627**
- Local-only kickoff rows: **0**
- Duplicate fixture identities within a source: **2**
- Database connections or writes: **0**
- Canonical identity writes, provider-link writes, fixture writes and prediction writes: **0**

UTC availability establishes timestamp evidence in the OpenLigaDB response; it does not by itself prove that a source record is an official competition or that it matches another provider's season.

## Source record inventory

| OpenLigaDB ID | Source name | Initial scope class | Candidate country/scope | Match rows | Teams | UTC kickoffs | Duplicate fixture rows |
|---:|---|---|---|---:|---:|---:|---:|
| 5972 | 1. Frauen Fußballbundesliga | domestic_league_candidate | Germany | 182 | 14 | 182 | 0 |
| 5958 | 2. Bundesliga 2026/27 (Herren) | domestic_league_candidate | Germany | 306 | 18 | 306 | 0 |
| 5960 | BLClaude | custom_or_user_created | Unassigned | 58 | 18 | 58 | 2 |
| 5957 | Bundesliga | test_or_duplicate_candidate | Germany | 1 | 2 | 1 | 0 |
| 5985 | DFB Frauen Supercup | domestic_cup_or_supercup_candidate | Germany | 1 | 2 | 1 | 0 |
| 5981 | DFB Nationalspiele | national_team_collection | Germany | 6 | 4 | 6 | 0 |
| 5984 | DFB U21 | national_team_collection | Germany | 3 | 4 | 3 | 0 |
| 6020 | DFB-Pokal Frauen | domestic_cup_candidate | Germany | 40 | 48 | 40 | 0 |
| 5959 | Empty Stands Spendenliga 2026/2027 | charity_or_custom_competition | Unassigned | 144 | 10 | 144 | 0 |
| 6027 | Eredivisie | domestic_league_candidate | Netherlands | 306 | 18 | 306 | 0 |
| 4949 | FIFA World Cup | international_tournament | International | 48 | 48 | 48 | 0 |
| 5966 | Franz-Beckenbauer-Supercup | domestic_cup_or_supercup_candidate | Germany | 1 | 2 | 1 | 0 |
| 5983 | Frauen-Nationalmannschaft | national_team_collection | Germany | 2 | 3 | 2 | 0 |
| 4941 | Freundschafts-und-Testspiele | friendly_or_test_collection | International | 1 | 2 | 1 | 0 |
| 5998 | Fußball-Regionalliga Nord | domestic_regional_league_candidate | Germany | 306 | 18 | 306 | 0 |
| 4900 | Hallenstadtmeisterschaft 2026 Bottrop | local_tournament | Germany | 14 | 13 | 14 | 0 |
| 5991 | NOFV Regionalliga NordOst | domestic_regional_league_candidate | Germany | 306 | 18 | 306 | 0 |
| 6010 | NOFV-Oberliga Süd | domestic_regional_league_candidate | Germany | 240 | 16 | 240 | 0 |
| 6016 | Oberliga Niederrhein | domestic_regional_league_candidate | Germany | 153 | 18 | 153 | 0 |
| 5994 | Regionalliga West Frauen | domestic_regional_league_candidate | Germany | 240 | 16 | 240 | 0 |
| 5992 | Spiele mit Arminia Bielefeld Beteiligung | team_filtered_match_collection | Germany | 34 | 18 | 34 | 0 |
| 4922 | tem26 | opaque_custom_label | Unassigned | 15 | 8 | 15 | 0 |
| 4943 | Testliga Outi77 | explicit_test_competition | Unassigned | 27 | 18 | 27 | 0 |
| 4927 | Testspiele Eintracht Frankfurt 26/27 | team_filtered_friendly_collection | Germany | 3 | 4 | 3 | 0 |
| 4944 | Testspiele2026 | generic_test_match_collection | International | 14 | 25 | 14 | 0 |
| 4897 | WM | international_tournament | International | 104 | 48 | 104 | 0 |
| 4923 | WM 2026 USA | international_tournament_alias_candidate | International | 72 | 48 | 72 | 0 |

## Scope-class distribution

| Initial scope class | Records |
|---|---:|
| domestic league candidate | 3 |
| custom or user created | 1 |
| test or duplicate candidate | 1 |
| domestic cup or supercup candidate | 2 |
| national team collection | 3 |
| domestic cup candidate | 1 |
| charity or custom competition | 1 |
| international tournament | 2 |
| friendly or test collection | 1 |
| domestic regional league candidate | 5 |
| local tournament | 1 |
| team filtered match collection | 1 |
| opaque custom label | 1 |
| explicit test competition | 1 |
| team filtered friendly collection | 1 |
| generic test match collection | 1 |
| international tournament alias candidate | 1 |

The original classifications are retained as review categories, not approvals. In particular, national-team collections, international tournaments, custom/user-created competitions, local tournaments, friendlies, team-filtered collections and test competitions must not be treated as ordinary domestic leagues.

## Exact fixture-overlap findings

Fixture identity comparison uses exact normalized home team, away team and UTC kickoff. Team names are normalized with Unicode NFKC, case-folding and whitespace normalization. Provider match IDs are deliberately excluded because IDs are source-specific.

| Left source | Right source | Exact shared fixtures | Left-only fixtures | Right-only fixtures |
|---|---|---:|---:|---:|
| 5958 — 2. Bundesliga 2026/27 (Herren) | 5992 — Spiele mit Arminia Bielefeld Beteiligung | 19 | 287 | 15 |
| 4949 — FIFA World Cup | 4897 — WM | 46 | 2 | 58 |
| 4949 — FIFA World Cup | 4923 — WM 2026 USA | 46 | 2 | 26 |
| 4897 — WM | 4923 — WM 2026 USA | 66 | 38 | 6 |

### Interpretation

1. **2. Bundesliga ID 5958 vs Arminia Bielefeld filtered collection ID 5992:** 19 exact fixture overlaps. This supports that the team-filtered collection contains fixtures also present in the 2. Bundesliga source. The remaining rows differ, so ID 5992 is not interchangeable with the competition source.
2. **World Cup IDs 4949, 4897 and 4923:** the three sources share 46, 46 and 66 exact fixtures across their pairwise comparisons. Their fixture totals are 48, 104 and 72 respectively. This is strong evidence that the records overlap in tournament scope, but they are not identical datasets. Do not collapse them into one provider record or infer which is authoritative from names alone.
3. **BLClaude ID 5960:** 58 match rows produce 56 unique exact fixture identities, indicating two duplicate fixture rows inside that source response. This custom/user-created source remains excluded from canonical competition promotion.
4. **All other pairs:** no exact full-fixture identity overlap was detected by this strict fingerprint method. A zero overlap is not proof that two sources are unrelated; names, aliases, time basis and coverage can prevent exact matching.

## Decisions and safeguards

- Keep all 27 OpenLigaDB IDs source-scoped.
- Preserve the existing candidate classifications; do not convert custom, local, friendly, test, team-filtered or national-team collections into domestic league identities.
- Keep World Cup IDs 4949, 4897 and 4923 separate pending official schedule reconciliation and season/coverage semantics.
- Keep the 2. Bundesliga competition source distinct from the Arminia Bielefeld team-filtered collection.
- Investigate the two duplicate fixture identities in BLClaude before any use; do not promote that source.
- No canonical competition, season or team identity approvals.
- No provider links, fixture ingestion or prediction eligibility changes.

**Next evidence required:** official competition/organizer corroboration for domestic candidates, fixture-level comparison against official schedules where useful, and explicit provider-specific season semantics. Exact fixture overlap is a review signal only and never an automatic approval.
