# Bundesliga 2026/27 — provider roster and season review

Generated: 15 November 2026

## Result

The public competition identity and 2026/27 season are supported by official Bundesliga/DFL evidence. Bzzoiro, OpenFootball and OpenLigaDB each expose all 18 clubs in the official 2026/27 Bundesliga roster. football-data.org exposes a smaller 14-club sample and omits country metadata on all 11 observations in this audit.

Eight exact UTC fixture overlaps between Bzzoiro and OpenLigaDB were checked against the official Bundesliga fixture schedule; all eight agree.

**This is evidence corroboration, not approval of provider IDs or a canonical database mapping.**

## Official scope

The official Bundesliga club directory lists 18 clubs for 2026/27. The DFL/Bundesliga calendar states Matchday 1 is 28–30 August 2026 and Matchday 34 is 22 May 2027.

- [Official Bundesliga 2026/27 club directory](https://www.bundesliga.com/en/bundesliga/clubs)
- [Official 2026/27 fixture list announcement](https://www.bundesliga.com/en/bundesliga/news/2026-27-fixture-lists-now-available-38068)
- [Official 2026/27 season calendar](https://www.bundesliga.com/en/bundesliga/news/calendar-for-2026-27-season-world-cup-34676)

## Provider review

| Provider | Competition ID | Season ID | Label | Unique clubs | Evidence assessment |
|---|---|---|---|---:|---|
| Bzzoiro | `5` | `5::1091` | Bundesliga 26/27 | 18 | 37 timezone-aware observations; 9 unique fixtures |
| football-data.org | `2002` | `2002::2522` | 2026-08-28 | 14 | 11 observations, 7 unique fixtures; country absent on all 11 |
| OpenFootball | `de.1` | `de.1::2026-27` | 2026-27 | 18 | 2,160 local date/time rows lack timezone; not eligible for exact UTC matching |
| OpenLigaDB | `4937` | `4937::2026` | 2026 | 18 | 6,120 timezone-aware rows; 4,500 eligible |

All 18 official clubs appear in Bzzoiro, OpenFootball and OpenLigaDB. football-data.org's bounded sample does not include FC Augsburg, 1. FSV Mainz 05, Hamburger SV or SV Werder Bremen. This is a sample-coverage gap, not proof those clubs are absent from its full catalogue.

Name variants reconciled against the official club directory:
- Borussia M'gladbach → Borussia Mönchengladbach
- SC Freiburg → Sport-Club Freiburg
- SV 07 Elversberg → SV Elversberg
- TSG 1899 Hoffenheim → TSG Hoffenheim

## Eight exact fixture overlaps

Bzzoiro and OpenLigaDB independently report these exact UTC fixtures; the [official Bundesliga fixture schedule](https://products.bundesliga.com/fixtures) confirms all eight:

| Fixture | Kickoff UTC |
|---|---|
| FC Bayern München – 1. FC Köln | 20 Nov 2026, 19:30 |
| 1. FC Union Berlin – RB Leipzig | 21 Nov 2026, 14:30 |
| Bayer 04 Leverkusen – SC Paderborn 07 | 21 Nov 2026, 14:30 |
| Eintracht Frankfurt – TSG Hoffenheim | 21 Nov 2026, 14:30 |
| SV Elversberg – Sport-Club Freiburg | 21 Nov 2026, 14:30 |
| FC Schalke 04 – VfB Stuttgart | 21 Nov 2026, 17:30 |
| FC Augsburg – 1. FSV Mainz 05 | 22 Nov 2026, 14:30 |
| SV Werder Bremen – Hamburger SV | 22 Nov 2026, 16:30 |

## Sportmonks canonical-target gap

Sportmonks publicly identifies Bundesliga league ID `82`. However, the repository's latest authenticated catalogue sync does not contain a German Bundesliga 2026/27 season or its team roster. No season ID is established from the committed evidence.

Therefore league ID 82 is only a candidate locator. Do not infer a season ID, create canonical records, or create provider links from this review. The next required evidence is an authenticated Sportmonks response for league 82, its 2026/27 season record, and the complete 18-team season roster.

Reference: [Sportmonks league coverage example listing Bundesliga ID 82](https://www.sportmonks.com/blogs/how-many-football-leagues-app-needs/).

## Decision

- Official competition and 2026/27 season interpretation: **supported**.
- Three provider rosters: **18/18 clubs observed**.
- football-data.org: **14-club partial sample; country evidence missing**.
- Exact fixture corroboration: **8 official-schedule matches**.
- Provider-specific competition and season IDs: **not approved**.
- Sportmonks canonical season/roster: **not available in current committed catalogue evidence**.
- Provider links, season links, fixture ingestion and prediction eligibility: **remain disabled**.

## Integrity safeguards

No canonical identity, provider-link, season-link, fixture or prediction-ledger writes were made.
