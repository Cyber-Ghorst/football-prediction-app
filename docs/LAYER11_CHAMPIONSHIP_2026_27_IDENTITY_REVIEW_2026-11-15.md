# Layer 11 — EFL Championship 2026/27 identity evidence review

**Review date:** 15 November 2026  
**Queue entry:** `observed_competition_020`  
**Disposition:** Broad competition identity supported; provider mapping not approved

## Provider observations

| Provider | Competition ID | Season ID | Season label | Observation quality |
|---|---|---|---|---|
| Bzzoiro | `12` | `12::1111` | Championship 26/27 | 45 timezone-aware observations; 12 unique fixture IDs; 24 unique teams |
| OpenFootball | `en.2` | `en.2::2026-27` | 2026-27 | 11,040 raw observations; 552 unique fixtures; 24 home and 24 away team names; kickoff values are local date/time without timezone |

The Priority A audit found **zero exact UTC cross-provider fixture overlaps**. OpenFootball's timezone-less local kickoffs cannot be used for exact UTC fixture matching.

## Official English Football League evidence

1. The EFL's official 2026/27 fixture release states that the Championship opening weekend is 14–16 August 2026 and the Championship season concludes on 1 May 2027: https://www.efl.com/news/2026/june/25/the-2026-27-efl-fixtures-are-here/
2. The official EFL Championship competition page provides the current 2026/27 competition table, showing 24 clubs: https://www.efl.com/competitions/efl-championship/
3. EFL regulations state that the Championship and League One each consist of 24 clubs: https://images.gc.eflservices.co.uk/6a32d710-5b0b-11f0-ad0f-97502a343283.pdf

## Roster and schedule comparison

- The official Championship structure comprises 24 clubs.
- Bzzoiro's bounded sample contains 24 unique team names.
- OpenFootball's bounded sample also contains 24 unique team names and 552 unique fixtures, consistent with a complete double round-robin season for 24 clubs.
- Both provider season labels are descriptively consistent with 2026/27, but this does not establish that the provider-specific season IDs are equivalent.
- Bzzoiro's observed kickoffs are timezone-aware; OpenFootball's sampled kickoff values are local date/time without timezone. Therefore, the current audit cannot use them for exact UTC fixture corroboration.

## Assessment

- Competition identity and country (England): **externally corroborated**.
- Competition type: **men's second-tier domestic league, externally corroborated**.
- Season context: **2026/27 externally corroborated; provider season IDs not independently verified**.
- Official club count: **24**.
- Bzzoiro roster sample: **24/24 teams observed**.
- OpenFootball roster sample: **24/24 teams observed**.
- OpenFootball fixture sample: **552 unique fixtures**, consistent with 24 clubs playing home and away.
- Exact UTC cross-provider fixture corroboration: **0**.

## Decision and safeguards

Keep both provider records source-scoped.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.

Next evidence needed: an authoritative timezone basis for OpenFootball kickoff values and exact provider season metadata. The matching team roster and fixture count support broad scope, but are not sufficient to approve provider-ID equivalence or create links.