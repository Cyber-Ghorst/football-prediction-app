# Layer 11 — Belgian professional leagues 2026/27 Priority B identity review

**Queue entries:** `observed_competition_006`, `observed_competition_007`, `observed_competition_008`  
**Priority:** B — single-provider source records  
**Disposition:** Official tier and season scope supported; provider mappings held

## Provider observations

| Queue entry | Competition | Provider | Competition ID | Season ID | Season label | Raw observations |
|---|---|---|---:|---|---|---:|
| `observed_competition_006` | Belgian Pro League | LiveScoreFootball | `3901` | `3901::2026` | 2026 | 1 |
| `observed_competition_008` | Pro League | Bzzoiro | `14` | `14::1327` | Pro League 26/27 | 7 |
| `observed_competition_007` | Challenger Pro League | Bzzoiro | `97` | `97::2018` | Challenger Pro League 26/27 | 9 |

The two top-tier records have names and season labels consistent with the same broad Jupiler Pro League competition. They remain separate source records because the samples are too small to establish an exact fixture crosswalk or provider season-ID equivalence.

## Official Pro League evidence

1. The official 2026/27 Jupiler Pro League calendar confirms 18 clubs, 34 matchdays and the opening fixtures: https://www.proleague.be/nieuws/kalender-2026-2027-club-brugge-opent-tegen-kv-kortrijk-eerste-super-sunday-al-op-speeldag-4
2. The Pro League's official format decision confirms that the Jupiler Pro League returns to 18 clubs from 2026/27: https://www.proleague.be/nieuws/vanaf-seizoen-26-27-met-18-clubs-in-de-jupiler-pro-league
3. The official 2026/27 Challenger Pro League calendar confirms 15 clubs and a 30-matchday regular season: https://www.proleague.be/nieuws/kalender-2026-2027-nieuwkomers-treffen-elkaar-meteen-in-challenger-pro-league
4. The official Challenger Pro League format decision confirms 15 clubs for 2026/27 and the promotion/relegation rules: https://www.proleague.be/nieuws/challenger-pro-league-heeft-nieuw-format-zonder-quota-voor-u23

## Competition classification

- **Jupiler Pro League:** men's top-tier domestic league, 18 clubs, 34 regular-season matchdays.
- **Challenger Pro League:** men's second-tier professional league, 15 clubs, 30 regular-season matchdays.
- The similar labels `Belgian Pro League` and `Pro League` are consistent with the top-tier Jupiler Pro League, but exact provider-ID equivalence is not proven.
- `Challenger Pro League` is a distinct second-tier competition and must not be merged with the Jupiler Pro League.

## Evidence limits

- LiveScoreFootball top-tier sample: **1 observation**.
- Bzzoiro top-tier sample: **7 observations**.
- Bzzoiro Challenger Pro League sample: **9 observations**.
- These bounded samples do not establish complete rosters or exact fixture overlaps.
- The LiveScoreFootball season label `2026` and Bzzoiro labels `26/27` are descriptively compatible but do not prove provider season-ID equivalence.

## Decision and safeguards

Keep all three source records separate and source-scoped.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.

Next evidence needed: larger provider-specific fixture/roster samples, exact home/away and kickoff comparisons for the two top-tier records, and explicit season metadata for all three provider season IDs.