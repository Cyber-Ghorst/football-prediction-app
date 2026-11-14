# Layer 11 — OpenLigaDB DFL and KNVB evidence review

**Review date:** 15 November 2026  
**Scope:** three OpenLigaDB country-unscoped source records  
**Status:** official country/competition context documented; exact provider IDs remain unlinked.

| OpenLigaDB ID | Source label | Official evidence | Country/scope disposition | Remaining gate |
|---|---|---|---|---|
| 5958 | 2. Bundesliga 2026/27 (Herren) | DFL/Bundesliga confirms the 2026/27 Bundesliga 2 competition and publishes matchday fixtures; DFB Datencenter independently lists the 2026/27 2. Bundesliga schedule. | Germany; men's second-tier league candidate | This ID differs from the other OpenLigaDB 2. Bundesliga record (4938). Do not merge the two IDs. Compare ID 5958's teams and fixtures against the official schedule and ID 4938 before proposing any alias or duplicate relationship. |
| 5966 | Franz-Beckenbauer-Supercup | DFL confirms the 2026 Franz Beckenbauer Supercup between Borussia Dortmund and Bayern Munich, scheduled for 22 August 2026. | Germany; men's national super cup, one-match competition | Verify the OpenLigaDB record's actual teams and date against the official match. Do not treat it as a league. |
| 6027 | Eredivisie | KNVB confirms the 2026/27 VriendenLoterij Eredivisie schedule and its opening fixture on 7 August 2026. | Netherlands; men's top-flight league candidate | Compare ID 6027's teams/dates/opponents with the KNVB fixture programme before linking. Do not merge based on name alone with any other provider record. |

## Official sources

- DFL/Bundesliga, [2026 Franz Beckenbauer Supercup details](https://www.bundesliga.com/en/bundesliga/news/dfl-confirm-details-2026-franz-beckenbauer-supercup-bayern-munich-borussia-dortmund-37584) — official match, participants and date.
- DFL/Bundesliga, [2026/27 Bundesliga and Bundesliga 2 fixture dates](https://www.bundesliga.com/en/bundesliga/news/confirmed-kick-off-times-dates-2026-27-fixtures-23955) — confirms the active second-tier competition and fixtures.
- DFB Datencenter, [2. Bundesliga 2026/27 schedule](https://datencenter.dfb.de/competitions/3/seasons/current) — official German competition fixture list.
- KNVB, [Definitive 2026/27 competition programme](https://www.knvb.nl/node/71918) — confirms the Eredivisie season, competition programme and opening match.
- KNVB, [VriendenLoterij Eredivisie 2026/27 fixture programme](https://www.knvb.nl/downloads/bestand/30062/definitiefcompetitieprogrammavriendenloterijeredivisie) — detailed official schedule.

## Safety outcome

- Country and real-world competition context are established for these three records.
- No exact OpenLigaDB-to-canonical mapping is approved.
- ID 5958 remains separate from ID 4938 until exact fixture/team comparison proves whether they are duplicate feeds, aliases, or distinct source scopes.
- ID 5966 is treated as a cup/supercup event, not a league.
- No canonical rows, provider links, season/team links, fixture writes, or prediction-ledger changes are made.
