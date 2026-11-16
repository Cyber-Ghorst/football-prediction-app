# Layer 12 — Highlightly / LiveScore / API Ninjas team identity review

**Review date:** 2026-11-16  
**Season:** 2026/27  
**Disposition:** provider-native details confirmed for 25 exact-name pairs; 21 additional Highlightly/API Ninjas aliases reviewed against official rosters and recorded as scope corroborations. None is approved as a canonical cross-provider identity.

## 1. Exact Highlightly–LiveScore candidates

The authenticated read-only detail audit used the 36 complete LiveScoreFootball standings observations staged for 2026/27 and the 96 Highlightly season-roster team records. It emitted 25 unique exact normalized-name pairs: 12 Bundesliga and 13 Ligue 1.

For every pair:
- Highlightly `GET /teams/{id}` returned the exact provider ID and matching name, with `type=club`.
- LiveScoreFootball `GET /get/soccer/{league}/clubs/{id}` returned the exact provider club ID and matching name.
- Both sides were scoped to the same 2026/27 competition, and LiveScore standings provenance was complete.
- The country field was absent from both providers' individual team/club detail responses. Country context is retained from the competition evidence; it is not copied into team records.
- No gender, age-group, senior/reserve or first-team status was inferred from the team-detail endpoints.

### Bundesliga — 12 confirmed provider-local details

| Highlightly ID | Highlightly name | LiveScore ID | LiveScore name | Detail result |
|---:|---|---:|---|---|
| 143752 | Bayer Leverkusen | 131 | Bayer Leverkusen | Both provider details confirmed |
| 134391 | Bayern Munich | 132 | Bayern Munich | Both provider details confirmed |
| 141199 | Borussia Dortmund | 124 | Borussia Dortmund | Both provider details confirmed |
| 139497 | Borussia Mönchengladbach | 268 | Borussia Mönchengladbach | Both provider details confirmed |
| 144603 | Eintracht Frankfurt | 125 | Eintracht Frankfurt | Both provider details confirmed |
| 145454 | FC Augsburg | 3841 | FC Augsburg | Both provider details confirmed |
| 148007 | RB Leipzig | 11420 | RB Leipzig | Both provider details confirmed |
| 136944 | SC Freiburg | 126 | SC Freiburg | Both provider details confirmed |
| 158219 | SC Paderborn 07 | 3307 | SC Paderborn 07 | Both provider details confirmed |
| 1413444 | SV Elversberg | 10388 | SV Elversberg | Both provider details confirmed |
| 147156 | VfB Stuttgart | 134 | VfB Stuttgart | Both provider details confirmed |
| 138646 | Werder Bremen | 137 | Werder Bremen | Both provider details confirmed |

### Ligue 1 — 13 confirmed provider-local details

| Highlightly ID | Highlightly name | LiveScore ID | LiveScore name | Detail result |
|---:|---|---:|---|---|
| 66311 | Angers | 7868 | Angers | Both provider details confirmed |
| 95245 | LE Havre AC | 3236 | Le Havre AC | Both provider details confirmed |
| 1105382 | Le Mans | 2697 | Le Mans | Both provider details confirmed |
| 99500 | Lens | 175 | Lens | Both provider details confirmed |
| 68013 | Lille | 166 | Lille | Both provider details confirmed |
| 83331 | Lorient | 273 | Lorient | Both provider details confirmed |
| 68864 | Lyon | 167 | Lyon | Both provider details confirmed |
| 69715 | Marseille | 176 | Marseille | Both provider details confirmed |
| 72268 | Nice | 2502 | Nice | Both provider details confirmed |
| 97798 | Paris FC | 6851 | Paris FC | Both provider details confirmed |
| 73119 | Paris Saint Germain | 160 | Paris Saint-Germain | Both provider details confirmed |
| 81629 | Strasbourg | 180 | Strasbourg | Both provider details confirmed |
| 82480 | Toulouse | 179 | Toulouse | Both provider details confirmed |

**Result:** 25/25 provider-local detail checks passed. This is strong candidate evidence, not an automatic cross-provider identity approval.

## 2. Highlightly–API Ninjas: 21 non-exact-name candidates

The read-only API Ninjas corroboration audit found 75 unique exact-name candidates and 21 non-exact-name Highlightly roster entries across the five domestic competitions. The API Ninjas seasonless catalogue rows joined to their 2026/27 standings rows for all 96 teams (96/96 exact provider-ID/competition joins, no missing or ambiguous standings rows). The API Ninjas records below carry 2026/27 season evidence, country, `team_type=club`, and `gender=men`.

Official competition rosters support the display-name variants below. These 21 manual aliases were recorded in the dedicated `provider_team_scope_corroborations` table with per-pair rationale and official references. They are scope corroborations only, not approved identity links.

| Competition | Highlightly ID and name | API Ninjas ID and name | Official 2026/27 roster display name |
|---|---|---|---|
| Serie A | 430539 — Inter | `soccer-internazionale` — Internazionale | Inter |
| LaLiga | 458622 — Celta de Vigo | `soccer-celta-vigo` — Celta Vigo | Celta |
| LaLiga | 463728 — Deportivo La Coruña | `soccer-deportivo` — Deportivo | RC Deportivo |
| LaLiga | 456920 — Sevilla FC | `soccer-sevilla` — Sevilla | Sevilla FC |
| Premier League | 30569 — Bournemouth | `soccer-afc-bournemouth` — AFC Bournemouth | AFC Bournemouth |
| Premier League | 44185 — Brighton | `soccer-brighton-hove-albion` — Brighton & Hove Albion | Brighton & Hove Albion |
| Premier League | 1146230 — Coventry | `soccer-coventry-city` — Coventry City | Coventry City |
| Premier League | 49291 — Ipswich | `soccer-ipswich-town` — Ipswich Town | Ipswich Town |
| Premier League | 54397 — Leeds | `soccer-leeds-united` — Leeds United | Leeds United |
| Premier League | 40781 — Tottenham | `soccer-tottenham-hotspur` — Tottenham Hotspur | Tottenham Hotspur |
| Ligue 1 | 92692 — Auxerre | `soccer-aj-auxerre` — AJ Auxerre | AJ Auxerre |
| Ligue 1 | 94394 — Estac Troyes | `soccer-troyes` — Troyes | ESTAC Troyes |
| Ligue 1 | 78225 — Monaco | `soccer-as-monaco` — AS Monaco | AS Monaco |
| Ligue 1 | 80778 — Rennes FC | `soccer-stade-rennais` — Stade Rennais | Stade Rennais FC |
| Ligue 1 | 90990 — Stade Brestois 29 | `soccer-brest` — Brest | Stade Brestois 29 |
| Bundesliga | 142901 — 1899 Hoffenheim | `soccer-tsg-hoffenheim` — TSG Hoffenheim | TSG Hoffenheim |
| Bundesliga | 164176 — FC Koln | `soccer-fc-cologne` — FC Cologne | 1. FC Köln |
| Bundesliga | 148858 — FC Schalke 04 | `soccer-schalke-04` — Schalke 04 | FC Schalke 04 |
| Bundesliga | 140348 — FSV Mainz 05 | `soccer-mainz` — Mainz | 1. FSV Mainz 05 |
| Bundesliga | 149709 — Hamburger SV | `soccer-hamburg-sv` — Hamburg SV | Hamburger SV |
| Bundesliga | 155666 — Union Berlin | `soccer-1-fc-union-berlin` — 1. FC Union Berlin | 1. FC Union Berlin |

### False near-name candidate rejected

The similarity-only audit suggested API Ninjas **Stade Rennais** as a near-name candidate for Highlightly **Stade Brestois 29**. This is not a valid alias: the official 2026/27 Ligue 1 calendar lists Stade Brestois 29 and Stade Rennais FC as two distinct clubs. The reviewed candidate for Stade Brestois 29 is API Ninjas **Brest** (`soccer-brest`), not Stade Rennais. No similarity score is used as proof of identity.

## 3. Official season-roster references

- [Lega Serie A — official 2026/27 club statistics](https://en.legaseriea.it/serie-a/statistiche/clubs)
- [LALIGA — official 2026/27 clubs](https://www.laliga.com/en-US/laliga-easports/clubs)
- [Premier League — official 2026/27 club list](https://www.premierleague.com/en/news/4365156)
- [Ligue 1 — official 2026/27 calendar and club list](https://ligue1.com/en/articles/l1_article_5292-)
- [Bundesliga — official 2026/27 clubs](https://www.bundesliga.com/en/bundesliga/clubs)

## 4. Live audit evidence

- [Highlightly / LiveScore exact-detail audit — controller run #436](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43910264808)
- [API Ninjas corroboration audit — controller run #433](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43909144446)
- [LiveScore club-catalogue metadata audit — controller run #432](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43908950082)
- [Provider-neutral identity candidate audit — controller run #430](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43908598483)
- [Scope corroboration write — controller run #438](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43911085721)
- [Post-write scope corroboration audit — controller run #439](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43911467932)

## 5. Disposition and safety

- 25 Highlightly–LiveScore exact-name pairs: provider-local details confirmed; remain unapproved cross-provider candidates.
- 21 Highlightly–API Ninjas non-exact-name pairs: official roster variants reviewed and recorded as manual scope corroborations.
- 132 scope corroboration records were written to the dedicated review table: 111 exact-name corroborations and 21 manual official-name aliases (96 Highlightly and 36 LiveScoreFootball).
- No canonical identity or cross-provider provider link was approved or created. Provider source rows and their country/type/gender fields were not updated.
- No fixture, prediction, model-weight, TVD or prediction-ledger changes.
- No source rows were overwritten or deleted.

A future canonical identity mapping approval must be explicit and recorded per pair with reviewer, rationale, provider-native detail evidence, competition/season context and official reference. The 132 scope corroborations do not authorize canonical identity promotion; all IDs remain namespaced and `promotion_allowed=false`.
