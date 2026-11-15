# Layer 11 — Austrian Bundesliga 2026/27 identity evidence review

**Review date:** 15 November 2026  
**Queue entry:** `observed_competition_005`  
**Disposition:** Broad competition identity supported; provider mapping not approved

## Provider observations

| Provider | Competition ID | Season ID | Season label | Observation quality |
|---|---|---|---|---|
| Bzzoiro | `96` | `96::1999` | Bundesliga 26/27 | 15 timezone-aware observations; 6 unique fixture IDs; 12 unique teams |
| LiveScoreFootball | `3907` | `3907::2026` | 2026 | 3 timezone-aware observations; 3 unique fixture IDs; 6 unique teams |

The Priority A audit found **zero exact cross-provider fixture overlaps**. Both feeds provide timezone-aware kickoffs in the bounded sample, but their sampled fixture sets do not overlap.

## Official Austrian football evidence

1. The Austrian Football Bundesliga published the 2026/27 ADMIRAL Bundesliga basic-round schedule, beginning with LASK vs Grazer AK on 31 July 2026: https://www.bundesliga.at/de/news/artikel/admiral-bundesliga-spielplan-fuer-den-grunddurchgang-2026-27
2. The official Bundesliga match schedule identifies the current season as 2026/2027: https://www.bundesliga.at/de/spielplan
3. The official season overview confirms 12 clubs, a 22-round home-and-away basic phase, and a subsequent split into championship and qualification groups: https://www.oefbl.at/de/medienbereich/mediainfos/2026/alles-wissenswerte-zur-saison-2026-27

## Roster and season comparison

- Official competition: **12 clubs**.
- Bzzoiro bounded sample: **12/12 team names observed**.
- LiveScoreFootball bounded sample: **6/12 team names observed**.
- Bzzoiro season label explicitly indicates 2026/27.
- LiveScoreFootball's calendar-year label `2026` may refer to the same season start year, but does not independently establish season boundaries or equivalent provider ID semantics.
- Both provider samples have timezone-aware kickoff values, but no exact cross-provider fixture pair was found.

## Assessment

- Competition identity and country (Austria): **externally corroborated**.
- Competition type: **men's top-tier domestic league, externally corroborated**.
- Season context: **2026/27 externally corroborated; LiveScoreFootball season ID scope not verified**.
- Official club count: **12**.
- Bzzoiro roster sample: **12/12 teams observed**.
- LiveScoreFootball roster sample: **6/12 teams observed**.
- Exact timezone-aware cross-provider fixture corroboration: **0**.

## Decision and safeguards

Keep both provider records source-scoped.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.

Next evidence needed: broader LiveScoreFootball roster/fixture coverage and provider-specific season metadata confirming that `3907::2026` represents the complete 2026/27 season. The matching competition name and calendar-year start are not enough to approve cross-provider links.