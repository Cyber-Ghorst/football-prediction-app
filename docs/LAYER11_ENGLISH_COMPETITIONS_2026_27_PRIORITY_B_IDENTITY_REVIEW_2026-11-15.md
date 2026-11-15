# Layer 11 — English men's and women's competitions 2026/27 Priority B identity review

**Queue entries:** `observed_competition_021` through `observed_competition_028`  
**Priority:** B — single-provider source records  
**Disposition:** Official competition types and broad scopes supported; provider mappings held

## Provider observations

| Queue entry | Competition | Provider | Competition ID | Season ID | Raw observations |
|---|---|---|---:|---|---:|
| `observed_competition_021` | English EFL Trophy | LiveScoreFootball | `18481` | `18481::2026` | 1 |
| `observed_competition_022` | English League Championship | LiveScoreFootball | `3914` | `3914::2026` | 11 |
| `observed_competition_023` | English League One | LiveScoreFootball | `3915` | `3915::2026` | 15 |
| `observed_competition_024` | English League Two | LiveScoreFootball | `3916` | `3916::2026` | 30 |
| `observed_competition_025` | English National League | LiveScoreFootball | `3917` | `3917::2026` | 33 |
| `observed_competition_026` | English Premier League | LiveScoreFootball | `700` | `700::2026` | 10 |
| `observed_competition_027` | English Women's FA Cup | LiveScoreFootball | `20226` | `20226::2026` | 3 |
| `observed_competition_028` | English Women's Super League | LiveScoreFootball | `8097` | `8097::2026` | 12 |

## Official evidence and competition classification

### Men's competitions

- **Premier League:** men's top tier, 20 clubs and 380 fixtures in 2026/27. Official guide: https://www.premierleague.com/en/news/4365156/new-to-the-premier-league-heres-all-you-need-to-know
- **EFL Championship:** men's second tier, 24 clubs. Official EFL table: https://www.efl.com/competitions/efl-championship
- **EFL League One:** men's third tier, 24 clubs. Official EFL table: https://www.efl.com/competitions/efl-league-one
- **EFL League Two:** men's fourth tier, 24 clubs; the EFL's 72-club structure assigns 24 clubs to each division. Official EFL regulations: https://images.gc.eflservices.co.uk/6a32d710-5b0b-11f0-ad0f-97502a343283.pdf
- **National League:** men's fifth tier, 24 clubs, evidenced by 12 fixtures in a standard round. Official National League coverage: https://www.thenationalleague.org.uk/news/2026/november/13/all-games-available-to-watch-on-dazn-this-weekend-/
- **EFL Trophy:** men's cup competition, not a league. The 2026/27 format combines 48 League One/Two clubs and 16 invited U21 teams. Official EFL announcement: https://www.efl.com/news/2026/june/23/under-21-teams-and-group-stage-draw-confirmed-for-2026-27-efl-trophy/

The EFL confirms the 2026/27 Championship, League One and League Two fixture release and opening weekend: https://www.efl.com/news/2026/june/25/the-2026-27-efl-fixtures-are-here/

### Women's competitions

- **Barclays Women's Super League:** women's top tier; expanded to 14 clubs from 2026/27 under the FA Board-approved format. Official FA announcement: https://www.thefa.com/news/2025/jun/20/statement-womens-super-league-proposals-approved-by-fa-board-20252006
- **Women's FA Cup:** national women's knockout cup; 535 clubs accepted for 2026/27. Official FA announcement: https://www.thefa.com/news/2026/jul/17/womens-fa-cup-clubs-accepted-2026-27-season

## Assessment

- All eight records are represented by LiveScoreFootball only in the approved intake snapshot.
- Samples range from **1 to 33 observations**; none is sufficient by itself to establish provider season-ID equivalence.
- League and cup competitions are now distinguished.
- Men's and women's competitions are explicitly classified; do not mix their team identities or season scopes.
- The EFL Trophy is a men's cup; the Women's FA Cup is a women's cup; neither is a league.
- The Women's Super League's 2026/27 expansion to 14 clubs means earlier 12-club assumptions must not be reused.

## Decision and safeguards

Keep all eight provider records source-scoped.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.

Next evidence needed: expanded provider fixture and roster samples, verified season metadata for each LiveScoreFootball ID, and independent provider corroboration where available.