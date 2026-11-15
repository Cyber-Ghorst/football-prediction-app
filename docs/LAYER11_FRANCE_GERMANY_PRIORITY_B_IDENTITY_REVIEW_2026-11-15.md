# Layer 11 — French and German cup/division 2026/27 Priority B identity review

**Queue entries:** `observed_competition_038`, `039`, `041`, `042`, `044`, `046`  
**Priority:** B — source-scoped provider records  
**Disposition:** Official competition identities and formats supported; provider links remain unapproved

## Provider observations

| Queue entry | Competition | Provider | Competition ID | Season ID | Season label | Raw observations |
|---|---|---|---:|---|---|---:|
| `observed_competition_038` | Coupe de France | Bzzoiro | `44` | `44::2240` | Coupe de France 26/27 | 261 |
| `observed_competition_039` | French Ligue 1 | LiveScoreFootball | `710` | `710::2026` | 2026 | 1 |
| `observed_competition_041` | Ligue 2 | Bzzoiro | `89` | `89::1848` | Ligue 2 26/27 | 21 |
| `observed_competition_042` | Ligue 3 | Bzzoiro | `105` | `105::2163` | Ligue 3 26/27 | 10 |
| `observed_competition_044` | 3. Liga | OpenLigaDB | `4939` | `4939::2026` | 2026 | 1,140 |
| `observed_competition_046` | DFB Pokal | OpenLigaDB | `4945` | `4945::2026` | 2026 | 168 |

## France — official evidence

### Coupe de France

- The FFF's national competition regulations page lists the 2026/27 Coupe de France rules: https://www.fff.fr/11-les-reglements/390-les-reglements-des-competitions-nationales.html
- The FFF regional league's first-round announcement identifies the 110th edition and 520 clubs engaged at the first round: https://lfpl.fff.fr/simple/coupe-de-france-ca-2026-2027-les-matches-du-1er-tour/
- The official national-cup engagement circular sets out 2026/27 participation arrangements: https://lfpl.fff.fr/wp-content/uploads/sites/20/2026/05/Engagements-Coupes-Nationales-2026.2027.pdf

### Ligue 1 and Ligue 2

- The LFP calendar index lists the 2026/27 Ligue 1 McDonald's and Ligue 2 BKT calendars: https://www.lfp.fr/calendriers/2011
- The LFP published the complete 34-matchday Ligue 2 BKT calendar for 2026/27: https://www.lfp.fr/article/ligue-2-bkt-le-calendrier-de-la-saison-2026-2027
- LFP's 2026/27 club-return guide identifies the 18 Ligue 2 clubs: https://ligue1.com/fr/articles/l1_article_5343-les-dates-de-reprise-des-clubs-de-ligue-2-bkt-2627

The LiveScoreFootball label `French Ligue 1` is consistent with the existing Ligue 1 competition identity, but its one-observation sample is not enough to prove a provider crosswalk. Treat it as a candidate alias, not as a new approved canonical competition.

### Ligue 3 — important 2026/27 naming change

The FFF officially launched professional **Ligue 3** for 2026/27, replacing the former Championnat National. It has 18 clubs in one group and 34 home-and-away matchdays:

- FFF launch and competition-format announcement: https://www.fff.fr/article/16778-la-fff-officialise-la-ligue-3-professionnelle.html
- Official 2026/27 calendar and participant list: https://www.fff.fr/article/17022-le-calendrier-2026-2027-est-servi.html
- Official Ligue 3 regulations: https://media.fff.fr/uploads/documents/textes-votes-a-l-ag-fff-du-06.06.2026.pdf

The name `Ligue 3` is therefore valid for the 2026/27 season. Do not misclassify this as Ligue 2 or continue to use the former National label as the new season's official competition name.

## Germany — official evidence

### 3. Liga

- DFB's official 2026/27 participant-field announcement identifies 20 clubs and 380 league matches: https://www.dfb.de/news/teilnehmerfeld-der-3-liga-steht-fest-havelse-rueckt-fuer-1860-nach
- DFB Datencenter provides the official 3. Liga 2026/27 competition table: https://datencenter.dfb.de/en/competitions/4/seasons/current/current_matchweek

### DFB-Pokal

- DFB confirms 64 clubs are admitted to the 2026/27 first main round: https://www.dfb.de/news/faq-hier-wird-die-erste-dfb-pokalrunde-live-gezeigt
- DFB published the official 2026/27 first-round schedule: https://www.dfb.de/news/dates-and-kick-off-times-confirmed-for-dfb-pokal-first-round
- DFB's competition-mode page describes the 64-team qualification structure: https://www.dfb.de/maenner/wettbewerbe/dfb-pokal/modus

## Assessment

- **Coupe de France:** French national men's knockout cup; 110th edition in 2026/27. The first round involved 520 clubs; that is not the total number of clubs across every later round.
- **French Ligue 1:** LiveScoreFootball's one observation is a candidate alias of the already indexed Ligue 1 identity; exact fixture-level corroboration is absent.
- **Ligue 2:** French men's second-tier professional league; 18 clubs and 34 matchdays.
- **Ligue 3:** new FFF professional third tier from 2026/27; 18 clubs and 34 matchdays.
- **3. Liga:** German men's third-tier professional league; 20 clubs and 380 matches.
- **DFB-Pokal:** German national men's knockout cup; 64 opening-round participants and 63 ties.

## Decision and safeguards

Keep provider records source-scoped. Treat the single French Ligue 1 row as a candidate alias only; do not duplicate the existing canonical competition.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.

Remaining work: verify provider season-ID semantics, compare exact fixtures where provider overlaps exist, and expand samples where coverage is small. No provider crosswalk or canonical mapping is approved by this review.