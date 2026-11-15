# Layer 11 — France 2026/27 Priority B identity review

**Queue entries:** `observed_competition_038` and `observed_competition_039`  
**Priority:** B — single-provider source records  
**Disposition:** Official competition identity supported; provider mappings held

## Provider observations

| Queue entry | Competition | Provider | Competition ID | Season ID | Season label | Raw observations |
|---|---|---|---:|---|---|---:|
| `observed_competition_038` | Coupe de France | Bzzoiro | `44` | `44::2240` | Coupe de France 26/27 | 261 |
| `observed_competition_039` | French Ligue 1 | LiveScoreFootball | `710` | `710::2026` | 2026 | 1 |

## Official French football evidence

### Coupe de France

1. The FFF's official 2026/27 general competition calendar lists Coupe de France rounds across the 2026/27 season: https://media.fff.fr/uploads/files/db509044d79863d25e097a847f53638a.pdf
2. The official regional FFF calendar identifies the staged entry of clubs, including Ligue 2 at the seventh round and Ligue 1 at the 32nd-final stage: https://laurafoot.fff.fr/simple/les-affiches-des-7e-et-8e-tours-de-coupe-de-france-2026/
3. The FFF maintains the official Coupe de France competition/engagement page: https://www.fff.fr/competition/engagement/416884-coupe-de-france/phase/1.html

This is a **men's national knockout cup**, not a league. The staged entry structure includes amateur and professional clubs. The 261 Bzzoiro observations do not by themselves establish the complete entrant set or provider season-ID semantics.

### Ligue 1

1. The official LFP 2026/27 calendar sets the season start and final matchday: https://ligue1.com/en/articles/l1_article_5292-
2. LFP confirms the 18-club field for the 2026/27 Ligue 1 season: https://ligue1.com/en/articles/l1_article_5328-when-does-the-season-start-for-ligue-1-mc-donald-s-clubs
3. The official 2026/27 fixture list was published by LFP: https://www.lfp.fr/article/ligue-1-mc-donald-s-le-calendrier-de-la-saison-2026-2027

This is the **men's top-tier domestic league**, with 18 clubs and 34 matchdays. The LiveScoreFootball record has only one observation. It is a plausible counterpart to the Bzzoiro and OpenFootball Ligue 1 records reviewed under Priority A, but name similarity and season labels do not establish a provider crosswalk.

## Decision and safeguards

Keep both records source-scoped. Keep the cup and league separate.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.
- Do not link LiveScoreFootball Ligue 1 to Bzzoiro/OpenFootball without exact fixture and kickoff corroboration.

Next evidence needed: full-season Coupe de France entrant/fixture evidence, exact Ligue 1 cross-provider fixture comparisons, and explicit provider season metadata.