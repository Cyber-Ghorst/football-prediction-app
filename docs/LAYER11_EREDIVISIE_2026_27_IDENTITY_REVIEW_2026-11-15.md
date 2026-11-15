# Layer 11 — Eredivisie 2026/27 identity evidence review

**Review date:** 15 November 2026  
**Queue entry:** `observed_competition_060`  
**Disposition:** Broad competition identity supported; provider mapping not approved

## Provider observations

| Provider | Competition ID | Season ID | Season label | Observation quality |
|---|---|---|---|---|
| Bzzoiro | `10` | `10::1268` | Eredivisie 26/27 | 24 timezone-aware observations; 9 unique fixture IDs; 18 unique teams |
| OpenFootball | `nl.1` | `nl.1::2026-27` | 2026-27 | 6,120 raw observations; 306 unique fixtures; 18 teams; kickoff fields include date-only and local-time values without timezone |

The Priority A audit found **zero exact UTC cross-provider fixture overlaps**. OpenFootball's kickoff fields are not consistently timezone-aware and therefore cannot be used for exact UTC matching.

## Official Dutch football evidence

1. Eredivisie CV's official 2026/27 calendar sets the season start for 7–9 August 2026 and the final matchday for 23 May 2027: https://eredivisie.nl/nieuws/speeldagenkalender-betaald-voetbal-seizoen-2026-27-vastgesteld/
2. The KNVB competition model identifies the Eredivisie as the highest level of Dutch football and specifies 18 teams: https://www.knvb.nl/competities/competitiezaken/competitiemodel
3. Eredivisie CV's official 2026/27 branding page identifies the 18 participating clubs: https://eredivisie.nl/meer/merk/logos-18-clubs/
4. The KNVB's definitive 2026/27 competition programme lists the season's fixtures, dates and kick-off times: https://www.knvb.nl/downloads/bestand/30062/definitiefcompetitieprogrammavriendenloterijeredivisie

## Roster and schedule comparison

- The official competition has 18 teams.
- Bzzoiro's bounded sample contains 18 unique team names.
- OpenFootball's bounded sample also contains 18 unique team names and 306 unique fixtures, consistent with an 18-team double round-robin competition.
- Both provider season labels are descriptively consistent with 2026/27, but this does not prove that their provider-specific season IDs are equivalent.
- Bzzoiro's observed kickoffs are timezone-aware. OpenFootball has date-only and local-time values without timezone, preventing exact UTC fixture corroboration.

## Assessment

- Competition identity and country (Netherlands): **externally corroborated**.
- Competition type: **men's top-tier domestic league, externally corroborated**.
- Season context: **2026/27 externally corroborated; provider season IDs not independently verified**.
- Official team count: **18**.
- Bzzoiro roster sample: **18/18 teams observed**.
- OpenFootball roster sample: **18/18 teams observed**.
- OpenFootball fixture sample: **306 unique fixtures**, consistent with 18 clubs playing home and away.
- Exact UTC cross-provider fixture corroboration: **0**.

## Decision and safeguards

Keep both provider records source-scoped.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.

Next evidence needed: exact provider season metadata and a reliable timezone basis for OpenFootball kickoff values. Matching club names and fixture counts support broad scope but are not sufficient to approve provider-ID equivalence or create links.