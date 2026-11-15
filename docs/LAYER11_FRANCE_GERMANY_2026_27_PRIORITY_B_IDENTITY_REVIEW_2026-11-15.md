# Layer 11 — France and Germany 2026/27 Priority B identity review

**Queue entries:** `observed_competition_041`, `observed_competition_042`, `observed_competition_044`, `observed_competition_046`, `observed_competition_047`  
**Priority:** B — source-scoped provider identities  
**Disposition:** Official competition scopes supported; provider mappings held

## Provider observations

| Queue entry | Competition | Provider | Competition ID | Season ID | Raw observations |
|---|---|---|---:|---|---:|
| `observed_competition_041` | Ligue 2 | Bzzoiro | `89` | `89::1848` | 21 |
| `observed_competition_042` | Ligue 3 | Bzzoiro | `105` | `105::2163` | 10 |
| `observed_competition_044` | 3. Liga | OpenLigaDB | `4939` | `4939::2026` | 1,140 |
| `observed_competition_046` | DFB Pokal | OpenLigaDB | `4945` | `4945::2026` | 168 |
| `observed_competition_047` | German Bundesliga | LiveScoreFootball | `720` | `720::2026` | 1 |

## Official French football evidence

### Ligue 2

- LFP's official 2026/27 fixture calendar lists all 34 matchdays: https://ligue1.com/fr/articles/l1_article_5281-

### Ligue 3

- The FFF's official calendar confirms the new professional Ligue 3 starts in August 2026 and ends on 21 May 2027, with **18 clubs and 34 matchdays**: https://www.fff.fr/article/17022-le-calendrier-2026-2027-est-servi.html
- FFF confirms Ligue 3 is the new professional men's third tier from 2026/27: https://www.fff.fr/article/16778-la-fff-officialise-la-ligue-3-professionnelle.html
- The official LFP-hosted fixture calendar lists the 18 clubs and 34 rounds: https://ligue1.com/fr/articles/l1_article_5407-ligue-3-le-calendrier-de-la-saison-2026-2027

Ligue 3 replaces the former National competition. This is a new competition label/structure from 2026/27; do not infer historic identity from the old National name without a season-scoped transition review.

## Official German football evidence

### 3. Liga

- DFB's official 2026/27 announcement lists the 20 admitted clubs and confirms the season's 380 matches: https://www.dfb.de/news/teilnehmerfeld-der-3-liga-steht-fest-havelse-rueckt-fuer-1860-nach
- The DFB 3. Liga statute specifies a 20-participant competition: https://assets.dfb.de/uploads/000/322/300/original_Heft_02_Statut_3_Liga_20250701.pdf

### DFB-Pokal

- DFB identifies the DFB-Pokal as a men's knockout cup with 64 teams in the opening round: https://www.dfb.de/en/men/mens-dfb-pokal
- The official 2026/27 German football calendar includes the cup opening round and final: https://www.bundesliga.com/en/bundesliga/news/calendar-for-2026-27-season-world-cup-34676

### Bundesliga

- The official 2026/27 fixture release sets Matchday 1 for 28–30 August 2026 and Matchday 34 for 22 May 2027: https://www.bundesliga.com/en/bundesliga/news/2026-27-season-fixture-schedules-37671
- The official 2026/27 Bundesliga table lists 18 clubs: https://www.bundesliga.com/en/bundesliga/table

## Assessment

- **Ligue 2:** men's second tier, 18 clubs, 34 matchdays; 21 Bzzoiro observations.
- **Ligue 3:** men's professional third tier, 18 clubs, 34 matchdays; 10 Bzzoiro observations.
- **3. Liga:** men's German third tier, 20 clubs, 380 matches; 1,140 OpenLigaDB observations.
- **DFB-Pokal:** men's national knockout cup, 64 opening-round teams; 168 OpenLigaDB observations.
- **Bundesliga:** men's German top tier, 18 clubs, 34 matchdays; one LiveScoreFootball observation.
- LiveScoreFootball's German Bundesliga record is a plausible counterpart to the Bzzoiro Bundesliga 2026/27 record already reviewed in Priority A, but exact fixture corroboration is not established.
- The OpenLigaDB season label `2026` must not be assumed to equal the complete 2026/27 season without provider-specific metadata.

## Decision and safeguards

Keep all five records source-scoped. Keep leagues and cups separate.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.
- Do not treat Ligue 3 as a continuation of an older competition without season-specific transition evidence.

Next evidence needed: explicit provider season metadata, exact fixture comparisons for German Bundesliga records, and expanded samples for the low-count records.