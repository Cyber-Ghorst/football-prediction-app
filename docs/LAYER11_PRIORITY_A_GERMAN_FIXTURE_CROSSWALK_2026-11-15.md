# Layer 11 — Priority A exact fixture crosswalk review: Germany

**Review date:** 15 November 2026  
**Scope:** Priority A identities `observed_competition_045` (Bundesliga) and `observed_competition_043` (2. Bundesliga).  
**Status:** strong fixture-level corroboration recorded; no canonical or provider links approved.

## Executive finding

Two of the ten Priority A identities now have independently verified fixture-level corroboration between Bzzoiro and OpenLigaDB, aligned to the official DFL/DFB 2026/27 schedules:

- **Bundesliga:** 6 exact home-team / away-team / UTC-kickoff overlaps between Bzzoiro competition ID `5` and OpenLigaDB competition ID `4937`.
- **2. Bundesliga:** 3 exact home-team / away-team / UTC-kickoff overlaps between Bzzoiro competition ID `94` and OpenLigaDB competition ID `4938`.

The official schedule checks confirm the same fixtures and kickoff times. This moves these two competition pairs from name-and-country similarity to strong, independent fixture-level identity corroboration. It still does not by itself authorize a canonical mapping or season link.

## Provider and season records

| Competition | Provider | Competition ID | Season ID | Snapshot evidence |
|---|---|---|---|---|
| Bundesliga | Bzzoiro | `5` | `5::1091` | 11 eligible observations; 14 unique teams in sampled observations |
| Bundesliga | OpenLigaDB | `4937` | `4937::2026` | 1,530 raw observations; 1,125 scheduled/eligible and 405 finished; 18 unique teams |
| 2. Bundesliga | Bzzoiro | `94` | `94::1967` | 14 eligible observations; 12 unique teams in sampled observations |
| 2. Bundesliga | OpenLigaDB | `4938` | `4938::2026` | 1,530 raw observations; 1,035 scheduled/eligible and 495 finished; 18 unique teams |

The provider-observation audit recorded six exact overlaps for Bundesliga and three for 2. Bundesliga. Its method requires matching normalized home team, away team, competition/country context and UTC kickoff. The audit's selected snapshots are not complete season rosters, so unique-team counts must not be interpreted as full competition participant counts.

## Exact Bundesliga overlaps

All six matches below appear in the official Bundesliga 2026/27 Matchday 10 schedule, with the same UTC kickoffs as the Bzzoiro/OpenLigaDB cross-provider overlap audit.

| UTC kickoff | Home | Away |
|---|---|---|
| 2026-11-20 19:30 | FC Bayern München | 1. FC Köln |
| 2026-11-21 14:30 | 1. FC Union Berlin | RB Leipzig |
| 2026-11-21 14:30 | Bayer 04 Leverkusen | SC Paderborn 07 |
| 2026-11-21 14:30 | Eintracht Frankfurt | TSG Hoffenheim |
| 2026-11-21 14:30 | SV Elversberg | Sport-Club Freiburg |
| 2026-11-21 17:30 | FC Schalke 04 | VfB Stuttgart |

Official reference: [Bundesliga 2026/27 Matchday 10 fixtures](https://products.bundesliga.com/fixtures) and [Bundesliga Matchday 10](https://www.bundesliga.com/en/bundesliga/matchday/2026-2027/10).

## Exact 2. Bundesliga overlaps

All three matches below appear in the official DFB Datencenter 2. Bundesliga Matchday 12 schedule. The DFB lists local kickoff at 13:00 CET; the cross-provider audit records the equivalent 12:00 UTC.

| UTC kickoff | Home | Away |
|---|---|---|
| 2026-11-21 12:00 | VfL Wolfsburg | Holstein Kiel |
| 2026-11-21 12:00 | Hannover 96 | SpVgg Greuther Fürth |
| 2026-11-21 12:00 | 1. FC Nürnberg | Eintracht Braunschweig |

Official reference: [DFB Datencenter — 2. Bundesliga Matchday 12](https://datencenter.dfb.de/datencenter/2-bundesliga/2026-2027/12).

## Provider-specific limitations

- The OpenFootball snapshots contain local date/time values without timezone-aware UTC kickoffs. They are useful for season and team context but were not eligible for exact UTC fixture matching in this audit.
- football-data.org supplied only a very small sample for the Bundesliga identity and its raw observations did not carry country values in the audit snapshot. Do not use those observations as independent country confirmation.
- This review validates the Bzzoiro/OpenLigaDB pairs only. It does not extend approval to similarly named sources, including OpenLigaDB ID `5958` (a separate country-unscoped 2. Bundesliga record).

## Decision and remaining gates

1. Classify the Bzzoiro/OpenLigaDB Bundesliga pair (IDs `5` and `4937`) as **fixture-corroborated identity candidate**.
2. Classify the Bzzoiro/OpenLigaDB 2. Bundesliga pair (IDs `94` and `4938`) as **fixture-corroborated identity candidate**.
3. Keep provider-specific season IDs separate until season-boundary and source-season equivalence checks are complete.
4. Keep OpenFootball and football-data.org provider links separate until their timestamp/country evidence is corrected or independently established.
5. Keep OpenLigaDB ID `5958` quarantined until its actual fixture/team set is compared with IDs `4938` and official DFB data.
6. No canonical rows, provider links, season links, team links, fixture writes or prediction-ledger changes are made by this report.

## Source reports

- `reports/provider_independent_catalogue/priority_a_provider_observation_audit/latest.json`
- `reports/provider_independent_catalogue/priority_a_external_evidence.json`
- `reports/provider_independent_catalogue/identity_review_queue.json`

**Outcome:** two of ten Priority A identities have progressed to strong fixture-level corroboration. They remain unapproved for canonical mapping pending the remaining source-season and full team-set checks.
