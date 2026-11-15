# Layer 11 — Romania, Slovakia, South America, Korea and Spain Priority B identity review

**Queue entries:** `observed_competition_071`, `observed_competition_074`, `observed_competition_075`, `observed_competition_076`, `observed_competition_077`, and `observed_competition_079`–`observed_competition_086`  
**Priority:** B — source-scoped provider records  
**Disposition:** Official competition scope supported; candidate provider pairs remain unlinked

## Provider observations

| Queue entry | Competition | Provider | Competition ID | Season ID | Raw observations |
|---|---|---|---:|---|---:|
| `observed_competition_071` | Romania Superliga | Bzzoiro | `23` | `23::1396` | 9 |
| `observed_competition_074` | Niké liga | Bzzoiro | `109` | `109::2243` | 4 |
| `observed_competition_075` | Copa Sudamericana | Bzzoiro | `33` | `33::114` | 1 |
| `observed_competition_076` | K League 1 | Bzzoiro | `50` | `50::1288` | 4 |
| `observed_competition_077` | Copa del Rey | Bzzoiro | `41` | `41::2052` | 20 |
| `observed_competition_079` | LaLiga EA Sports | OpenLigaDB | `4936` | `4936::2026` | 1,140 |
| `observed_competition_080` | Liga F | Bzzoiro | `36` | `36::1308` | 27 |
| `observed_competition_081` | Primera Division | football-data.org | `2014` | `2014::2518` | 1 |
| `observed_competition_082` | Segunda División | Bzzoiro | `38` | `38::1356` | 39 |
| `observed_competition_083` | Spanish Copa de la Reina | LiveScoreFootball | `20381` | `20381::2026` | 3 |
| `observed_competition_084` | Spanish Copa del Rey | LiveScoreFootball | `3951` | `3951::2026` | 5 |
| `observed_competition_085` | Spanish LALIGA | LiveScoreFootball | `740` | `740::2026` | 1 |
| `observed_competition_086` | Spanish LALIGA 2 | LiveScoreFootball | `3921` | `3921::2026` | 1 |

## Romania — Superliga

- LPF confirms the 16 clubs participating in 2026/27: https://lpf.ro/buletin/superliga-incepe-azi/1283
- The official schedule sets the 30-round regular phase: https://lpf.ro/noutati/superliga-programul-turului-editiei-2026-2027/6593
- The official table shows the top six entering the 10-round playoff and the remaining ten entering the nine-round playout: https://lpf.ro/liga-1

## Slovakia — Niké liga

- The official league governance page lists 12 member clubs for 2026/27: https://www.nikeliga.sk/text/8-ulk
- The official game model sets 22 regular rounds followed by ten rounds in two six-club groups: https://www.nikeliga.sk/text/56-herny-model
- The official 2026/27 schedule confirms the split phase: https://www.nikeliga.sk/clanok/4784-majster-zacne-u-novacika-pozname-program-nike-ligy-2026-2027

## South America — Copa Sudamericana

- The official 2026 club manual defines the qualification and group-stage structure: https://cdn.conmebol.com/wp-content/uploads/2025/12/Manual-de-Clubes-CONMEBOL-Sudamericana-2026-ESP.pdf
- The official group-stage draw confirms 32 clubs in eight groups of four, six matches per club: https://gol.conmebol.com/sudamericana/en/news/conmebol-sudamericana-2026-group-stage-draw-date-time-qualified-teams-pots-and-format

This is a **men's continental club competition**, not a domestic league.

## South Korea — K League 1

- The official K League 2026 regulations specify 12 clubs, 33 regular rounds and five final rounds, for 38 matches per club: https://www.kleague.com/about/competition.do
- Official final-round schedule confirms Final A/Final B for rounds 34–38: https://www.kleague.com/news_view.do?category=notice&orderBy=seq&page=1&seq=96653&viewOption=album

## Spain — men's and women's competitions

### Men's LaLiga EA SPORTS and LALIGA HYPERMOTION

- Official LaLiga EA SPORTS 2026/27 club directory lists 20 clubs: https://www.laliga.com/laliga-easports/clubes
- Official LALIGA HYPERMOTION 2026/27 club directory lists 22 clubs: https://www.laliga.com/laliga-hypermotion/clubes
- The official calendar lists all 42 rounds for HYPERMOTION: https://www.laliga.com/es-NG/noticias/conoce-el-calendario-completo-de-laliga-hypermotion-2026-27
- The official LaLiga news index lists the full EA SPORTS 2026/27 calendar release: https://www.laliga.com/noticias?page=3

The OpenLigaDB, football-data.org and LiveScoreFootball LaLiga records are plausible counterparts to the Bzzoiro/OpenFootball LaLiga records reviewed under Priority A. Similarly, the LiveScoreFootball LALIGA 2 record is a plausible counterpart to Bzzoiro's Segunda División. These are candidate relationships only; exact fixture and season-ID corroboration is still required.

### Women's Liga F and Copa de la Reina

- Liga F confirms 16 clubs for 2026/27: https://ligaf.es/noticia/los-clubes-de-liga-f-moeve-arrancan-la-temporada-20262027
- RFEF sets 30 Liga F matchdays in the 2026/27 women's calendar: https://rfef.es/es/noticias/repasa-las-fechas-clave-del-futbol-femenino-para-la-temporada-202627
- RFEF confirms the 2026/27 Copa de la Reina has 48 clubs, with 32 entering the first round and the rest joining later: https://rfef.es/es/noticias/configurada-la-primera-eliminatoria-de-la-copa-de-la-reina-2026-2027

Copa de la Reina is a **women's national knockout cup**, not a league.

### Men's Copa del Rey

- RFEF confirms 116 clubs participate in the 2026/27 edition; 112 enter the first round and four Supercopa teams join in the round of 16: https://rfef.es/es/noticias/112-equipos-56-cruces-para-la-primera-eliminatoria-de-la-copa-del-rey-mapfre-se-sortea-el-5-de

Bzzoiro and LiveScoreFootball Copa del Rey records are candidate counterparts, not approved links.

## Decision and safeguards

Keep all source records separate.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.
- Keep the Spanish men's and women's competitions distinct.
- Keep LaLiga, LaLiga 2, Copa del Rey and Copa de la Reina as separate competition entities.
- Keep domestic leagues distinct from continental competitions.

Next evidence needed: exact fixture-level corroboration and provider season metadata for candidate Spanish pairs, plus broader samples for low-count competitions.