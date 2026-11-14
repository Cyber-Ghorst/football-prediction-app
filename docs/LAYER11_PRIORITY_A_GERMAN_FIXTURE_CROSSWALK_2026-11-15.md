# Layer 11 — Priority A exact fixture crosswalk review

**Review date:** 15 November 2026  
**Scope:** Priority A identities with exact cross-provider fixture overlaps in the 14 November provider-observation audit.  
**Status:** strong fixture-level corroboration recorded; no canonical or provider links approved.

## Executive finding

Four of the ten Priority A identities have exact fixture-level overlaps in the read-only provider-observation audit. Official federation/league schedules independently confirm the same matches:

- **Bundesliga:** 6 overlaps between Bzzoiro ID `5` and OpenLigaDB ID `4937`.
- **2. Bundesliga:** 3 overlaps between Bzzoiro ID `94` and OpenLigaDB ID `4938`.
- **Premier League:** 1 overlap between Bzzoiro ID `1` and OpenLigaDB ID `5996`.
- **Saudi Pro League:** 1 overlap between Bzzoiro ID `17` and LiveScoreFootball ID `21231`.

This moves four competition pairs from name/country similarity to strong fixture-level corroboration. It still does not by itself authorize canonical mappings or season links.

## Provider and season records

| Competition | Provider | Competition ID | Season ID | Snapshot evidence |
|---|---|---|---|---|
| Bundesliga | Bzzoiro | `5` | `5::1091` | 11 eligible observations; 14 unique teams in sampled observations |
| Bundesliga | OpenLigaDB | `4937` | `4937::2026` | 1,530 raw observations; 1,125 scheduled/eligible and 405 finished; 18 unique teams |
| 2. Bundesliga | Bzzoiro | `94` | `94::1967` | 14 eligible observations; 12 unique teams in sampled observations |
| 2. Bundesliga | OpenLigaDB | `4938` | `4938::2026` | 1,530 raw observations; 1,035 scheduled/eligible and 495 finished; 18 unique teams |
| Premier League | Bzzoiro | `1` | `1::1058` | 7 eligible observations; 14 unique teams in sampled observations |
| Premier League | OpenLigaDB | `5996` | `5996::2026` | 1,900 raw observations; 1,400 scheduled/eligible and 500 finished; 20 unique teams |
| Saudi Pro League | Bzzoiro | `17` | `17::1631` | 50 raw observations; 5 eligible and 45 postponed; 18 unique teams |
| Saudi Pro League | LiveScoreFootball | `21231` | `21231::2026` | 5 eligible observations; 2 unique teams |

The audit's selected snapshots are not complete season rosters. Unique-team counts must not be interpreted as full competition participant counts.

## Exact Bundesliga overlaps

All six matches appear in the official Bundesliga 2026/27 Matchday 10 schedule with the same UTC kickoffs as the Bzzoiro/OpenLigaDB overlap audit.

| UTC kickoff | Home | Away |
|---|---|---|
| 2026-11-20 19:30 | FC Bayern München | 1. FC Köln |
| 2026-11-21 14:30 | 1. FC Union Berlin | RB Leipzig |
| 2026-11-21 14:30 | Bayer 04 Leverkusen | SC Paderborn 07 |
| 2026-11-21 14:30 | Eintracht Frankfurt | TSG Hoffenheim |
| 2026-11-21 14:30 | SV Elversberg | Sport-Club Freiburg |
| 2026-11-21 17:30 | FC Schalke 04 | VfB Stuttgart |

Official references: [Bundesliga fixtures](https://products.bundesliga.com/fixtures) and [Matchday 10](https://www.bundesliga.com/en/bundesliga/matchday/2026-2027/10).

## Exact 2. Bundesliga overlaps

All three matches appear in the official DFB Datencenter 2. Bundesliga Matchday 12 schedule. The DFB lists local kickoff at 13:00 CET; the cross-provider audit records the equivalent 12:00 UTC.

| UTC kickoff | Home | Away |
|---|---|---|
| 2026-11-21 12:00 | VfL Wolfsburg | Holstein Kiel |
| 2026-11-21 12:00 | Hannover 96 | SpVgg Greuther Fürth |
| 2026-11-21 12:00 | 1. FC Nürnberg | Eintracht Braunschweig |

Official reference: [DFB Datencenter — 2. Bundesliga Matchday 12](https://datencenter.dfb.de/datencenter/2-bundesliga/2026-2027/12).

## Exact Premier League overlap

| UTC kickoff | Home | Away |
|---|---|---|
| 2026-11-21 15:00 | Aston Villa | Sunderland |

The Premier League's official 2026/27 fixture release lists Aston Villa v Sunderland on Saturday 21 November and states that all fixtures are GMT, with 15:00 kickoffs unless otherwise stated. This matches the one exact Bzzoiro/OpenLigaDB UTC overlap.

Official references: [Premier League 2026/27 fixtures](https://www.premierleague.com/en/news/4675097/all-380-fixtures-for-2026-27) and [November fixture amendments](https://www.premierleague.com/en/news/4725574).

## Exact Saudi Pro League overlap

| UTC kickoff | Home | Away |
|---|---|---|
| 2026-11-20 17:30 | Al Ahli | Al Nassr |

The Saudi Pro League's revised 2026/27 calendar confirms Al Ahli hosting Al Nassr on 20 November. Its official fixture PDF lists 20:30 local time in Jeddah, equivalent to 17:30 UTC, matching the Bzzoiro/LiveScoreFootball overlap.

Official references: [Saudi Pro League revised 2026/27 calendar](https://www.spl.com.sa/en/news/rsl-schedule-2026-27) and [official fixture PDF](https://images.spl.com.sa/image/private/fl_attachment/prd/m54jmnwpd2embhoz8bvb.pdf).

## Provider-specific limitations

- OpenFootball observations contain local date/time values without timezone-aware UTC kickoffs. They are useful for season/team context but were not eligible for exact UTC fixture matching in this audit.
- football-data.org supplied only very small samples for some identities; its raw observations did not carry country values in the audit snapshot. Do not use those observations as independent country confirmation.
- This review validates only the pairs listed above. It does not extend approval to similarly named sources, including OpenLigaDB ID `5958` (a separate country-unscoped 2. Bundesliga record).
- Saudi Pro League corroboration is based on one exact fixture and a small LiveScoreFootball sample; do not infer full team coverage from that overlap.

## Decision and remaining gates

1. Classify the four provider pairs above as **fixture-corroborated identity candidates**.
2. Keep provider-specific season IDs separate until season-boundary and source-season equivalence checks are complete.
3. Keep OpenFootball and football-data.org provider links separate until their timestamp/country evidence is corrected or independently established.
4. Keep OpenLigaDB ID `5958` quarantined until its actual fixture/team set is compared with IDs `4938` and official DFB data.
5. Keep MLS, Ligue 1, Championship, Serie A, Eredivisie and La Liga in the Priority A queue; the current audit did not produce exact fixture overlaps for those entries.
6. No canonical rows, provider links, season links, team links, fixture writes or prediction-ledger changes are made by this report.

## Source reports

- `reports/provider_independent_catalogue/priority_a_provider_observation_audit/latest.json`
- `reports/provider_independent_catalogue/priority_a_external_evidence.json`
- `reports/provider_independent_catalogue/identity_review_queue.json`

**Outcome:** four of ten Priority A identities have progressed to strong fixture-level corroboration. They remain unapproved for canonical mapping pending the remaining source-season and full team-set checks.
