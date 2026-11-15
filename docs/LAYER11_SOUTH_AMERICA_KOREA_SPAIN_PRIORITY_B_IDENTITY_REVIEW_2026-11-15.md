# Layer 11 — CONMEBOL, South Korea and Spain Priority B identity review

**Queue entries:** `observed_competition_075`, `076`, `077`, `079`, `080`, `081`, `082`, `083`  
**Priority:** B — source-scoped provider records  
**Disposition:** Official competition identity and format supported; provider crosswalks held

## Provider observations

| Queue entry | Competition | Provider | Competition ID | Season ID | Label | Raw observations |
|---|---|---|---:|---|---|---:|
| `075` | Copa Sudamericana | Bzzoiro | `33` | `33::114` | CONMEBOL Sudamericana 2026 | 1 |
| `076` | K League 1 | Bzzoiro | `50` | `50::1288` | K-League 1 2026 | 4 |
| `077` | Copa del Rey | Bzzoiro | `41` | `41::2052` | Copa del Rey 26/27 | 20 |
| `079` | LaLiga EA Sports | OpenLigaDB | `4936` | `4936::2026` | 2026 | 1,140 |
| `080` | Liga F | Bzzoiro | `36` | `36::1308` | Primera Division Women 26/27 | 27 |
| `081` | Primera Division | football-data.org | `2014` | `2014::2518` | 2026-08-16 | 1 |
| `082` | Segunda División | Bzzoiro | `38` | `38::1356` | LaLiga 2 26/27 | 39 |
| `083` | Spanish Copa de la Reina | LiveScoreFootball | `20381` | `20381::2026` | 2026 | 3 |

## CONMEBOL — Copa Sudamericana 2026

- The official CONMEBOL club manual identifies 44 qualified clubs from ten member associations and 157 matches: https://cdn.conmebol.com/wp-content/uploads/2025/12/CS-2026-Manual-de-Clubes-ESP-Feb26.pdf
- The official group-stage draw confirms the 32-team group stage and competition format: https://gol.conmebol.com/sudamericana/en/news/conmebol-sudamericana-2026-group-stage-draw-date-time-qualified-teams-pots-and-format

The Bzzoiro record has one observation only; full fixture coverage and season ID `33::114` remain unverified.

## South Korea — K League 1 2026

The official K League rules specify 12 clubs, 33 regular rounds, then a five-round split final stage (top six and bottom six), totalling 38 matches per club and 228 league matches.

- Official 2026 competition regulations: https://www.kleague.com/about/competition.do
- Official 2026 schedule announcement: https://www.kleague.com/news_view.do?orderBy=seq&page=1&seq=94117&viewOption=list

Bzzoiro's four observations do not establish full roster coverage or provider season-ID semantics.

## Spain — men's and women's competitions

### Copa del Rey

RFEF's official 2026/27 regulations specify **106 clubs** admitted to the men's Copa del Rey, including all 20 Primera División and 22 Segunda División clubs plus qualified lower-division and preliminary-round teams.

- Official 2026/27 regulation and entry criteria: https://rfef.es/sites/default/files/pdf/circulares/102_con_anexos_20250624.pdf
- Official RFEF circular register: https://rfef.es/es/federacion/normativas-y-circulares/circulares

### LaLiga EA Sports and Primera Division alias candidate

LALIGA's official standings identify the 2026/27 EA SPORTS top division. Its official competition structure is 20 clubs, 38 rounds and 380 matches:

- Official 2026/27 table: https://www.laliga.com/laliga-easports/clasificacion
- Official division structure: https://assets.laliga.com/assets/2025/03/24/originals/5408fc235e5b383d670bef19ab1fd196.pdf

The OpenLigaDB row's 1,140 raw observations exceed the 380 unique matches expected for one season; do not treat raw observation count as unique fixtures. The football-data.org `Primera Division` row has only one observation. Both are candidate aliases of existing La Liga identity records, not approved crosswalks.

### Liga F

- Liga F's official 2026/27 club announcement confirms 16 clubs: https://ligaf.es/noticia/los-clubes-de-liga-f-moeve-arrancan-la-temporada-20262027
- Official fixture calendar: https://ligaf.es/noticia/liga-f-moeve-ya-tiene-definido-el-calendario-de-emparejamientos-de-la-temporada-20262027
- RFEF's official women's football calendar: https://rfef.es/es/noticias/repasa-las-fechas-clave-del-futbol-femenino-para-la-temporada-202627

Sixteen clubs in a home-and-away format means 30 rounds and 240 matches. Bzzoiro's 27 observations are not a complete roster or season proof.

### Segunda División

LALIGA's official competition structure specifies 22 clubs, 42 rounds and 462 matches in the men's second tier.

- Official LALIGA competition structure: https://assets.laliga.com/assets/2025/03/24/originals/5408fc235e5b383d670bef19ab1fd196.pdf
- Official 2026/27 LALIGA Hypermotion standings: https://www.laliga.com/laliga-hypermotion/clasificacion

Bzzoiro's 39 observations do not establish full roster coverage or season-ID semantics.

### Copa de la Reina

RFEF's official 2026/27 regulations specify 48 clubs and 49 matches for the women's national knockout cup.

- Official 2026/27 regulation and entry criteria: https://rfef.es/sites/default/files/pdf/circulares/110_con_anexos_20250624.pdf
- Official first-round announcement confirms 32 clubs enter initially and later rounds build to 48: https://rfef.es/es/noticias/configurada-la-primera-eliminatoria-de-la-copa-de-la-reina-2026-2027
- Official women's football calendar: https://rfef.es/es/noticias/repasa-las-fechas-clave-del-futbol-femenino-para-la-temporada-202627

LiveScoreFootball's three observations do not establish complete cup coverage or the exact season-ID scope.

## Decision and safeguards

Keep all source records separate and source-scoped. Treat LaLiga EA Sports and Primera Division as possible aliases of existing La Liga records, pending exact fixture evidence. Do not treat raw provider observations as unique fixtures.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.

Remaining evidence: larger provider samples, explicit season metadata, and exact fixture-level comparisons before any provider crosswalk is proposed.