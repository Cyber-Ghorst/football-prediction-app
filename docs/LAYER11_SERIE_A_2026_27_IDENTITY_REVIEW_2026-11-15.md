# Layer 11 — Serie A 2026/27 identity evidence review

**Review date:** 15 November 2026  
**Queue entry:** `observed_competition_050`  
**Disposition:** Broad competition identity supported; provider mapping not approved

## Provider observations

| Provider | Competition ID | Season ID | Season label | Observation quality |
|---|---|---|---|---|
| Bzzoiro | `4` | `4::1375` | Serie A 26/27 | 21 raw observations; 9 unique fixture IDs; 18 unique teams; all 21 kickoffs timezone-aware |
| OpenFootball | `it.1` | `it.1::2026-27` | 2026-27 | 7,600 raw observations; 380 unique fixtures; 20 home and 20 away team names; sampled kickoff values are local date/time without timezone |

The Priority A provider-observation audit found **zero exact UTC cross-provider fixture overlaps**. This is not proof that the feeds describe different competitions: OpenFootball's timezone-less local kickoff values are not eligible for exact UTC matching.

## Official Lega Serie A evidence

1. The official English-language 2026/27 season announcement identifies 20 clubs, 38 matchdays and 380 matches, with the season running from August 2026 to May 2027: https://en.legaseriea.it/serie-a/news/looking-forward-to-the-2026-27-serie-a-fixture-list
2. Lega Serie A published the 2026/27 fixture list on 5 June 2026: https://www.legaseriea.it/serie-a/news/calendario-della-serie-a-enilive-2026-27
3. The official calendar currently lists Matchday 12 fixtures for 21–23 November 2026: https://www.legaseriea.it/serie-a/calendario-risultati

## Roster and schedule comparison

- The official competition comprises 20 clubs.
- OpenFootball's observed 20-team roster covers the official 20-club scope in the bounded observation sample.
- Bzzoiro's sample contains 18 unique teams. It does not include AC Monza or ACF Fiorentina in this sample; that is a sample-coverage gap, not proof those clubs are absent from the provider's complete season catalogue.
- The providers' descriptive season labels both indicate 2026/27, but this does not establish provider-specific season-ID equivalence.
- No exact UTC fixture overlap can be asserted because OpenFootball's kickoff values lack timezone information.

## Assessment

- Competition identity and country (Italy): **externally corroborated**.
- Competition type: **men's top-tier domestic league, externally corroborated**.
- Season context: **2026/27 externally corroborated; provider season IDs not independently verified**.
- Official team count: **20**.
- OpenFootball roster sample: **20/20 teams observed**.
- Bzzoiro roster sample: **18/20 teams observed**.
- Exact UTC cross-provider fixture corroboration: **0**.
- Provider competition/season ID equivalence: **not established**.

## Decision and safeguards

Keep both provider records source-scoped.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.

Next evidence needed: an expanded Bzzoiro season roster/fixture sample and an authoritative timezone basis for OpenFootball kickoff values. A later cross-provider match can be assessed only after kickoff timestamps are on a comparable timezone basis.