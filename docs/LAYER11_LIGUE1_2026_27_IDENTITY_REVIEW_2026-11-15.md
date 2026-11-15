# Layer 11 — Ligue 1 2026/27 identity evidence review

**Review date:** 15 November 2026  
**Queue entry:** `observed_competition_040`  
**Disposition:** Broad competition identity supported; provider mappings not approved

## Provider observations

| Provider | Competition ID | Season ID | Season label | Observation quality |
|---|---|---|---|---|
| Bzzoiro | `6` | `6::1311` | Ligue 1 26/27 | 34 timezone-aware observations; 9 unique fixture IDs; 18 unique teams |
| football-data.org | `2015` | `2015::2497` | 2026-08-22 | 10 timezone-aware observations; 6 unique fixtures; 12 teams; country missing on all 10 observations |
| OpenFootball | `fr.1` | `fr.1::2026-27` | 2026-27 | 6,120 raw observations; 306 unique fixtures; 18 teams; sampled kickoff values include local/date-only values without timezone and missing kickoff values |

The Priority A audit found **zero exact UTC cross-provider fixture overlaps**. The absence of exact overlap is a data-quality limitation, not evidence that the feeds describe different competitions.

## Official LFP / Ligue 1 evidence

1. The official 2026/27 calendar announcement gives the season start (21 August 2026), final matchday (29 May 2027), and the 34-matchday schedule: https://ligue1.com/en/articles/l1_article_5292-
2. The official Ligue 1 announcement explicitly refers to the **18 clubs** in the 2026/27 season: https://ligue1.com/en/articles/l1_article_5328-when-does-the-season-start-for-ligue-1-mc-donald-s-clubs
3. The LFP's French-language official calendar announcement, published 10 June 2026, independently confirms the 2026/27 calendar: https://www.lfp.fr/article/ligue-1-mc-donald-s-le-calendrier-de-la-saison-2026-2027

## Roster and schedule comparison

- The official competition has 18 clubs and 34 matchdays.
- Bzzoiro's bounded sample contains 18 unique team names, matching the 18-club official scope by count and roster names.
- OpenFootball's bounded sample also contains 18 unique team names.
- football-data.org's sample contains only 12 teams and omits country on all 10 observations; this is a bounded-sample metadata gap, not proof of an incorrect competition identity.
- Provider season labels are descriptively consistent with 2026/27, but the provider-specific competition and season IDs have not been proven equivalent.
- OpenFootball's timezone-less/local/date-only kickoff fields prevent exact UTC fixture matching. Bzzoiro and football-data.org samples also produced no exact overlap in the current audit.

## Assessment

- Competition identity and country (France): **externally corroborated**.
- Competition type: **men's top-tier domestic league, externally corroborated**.
- Season context: **2026/27 externally corroborated; provider season IDs not independently verified**.
- Official team count: **18**.
- Bzzoiro roster sample: **18/18 team names observed**.
- OpenFootball roster sample: **18/18 team names observed**.
- football-data.org sample: **12 teams; country absent from all 10 observations**.
- Exact UTC cross-provider fixture corroboration: **0**.

## Decision and safeguards

Keep all provider records source-scoped.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.

Next evidence needed: exact provider season metadata, country-complete football-data.org observations, and a reliable timezone basis for OpenFootball's kickoff fields. Do not infer timezone from the country alone.