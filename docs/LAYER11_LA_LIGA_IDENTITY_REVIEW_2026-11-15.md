# Layer 11 — La Liga 2026/27 identity evidence review

**Review date:** 15 November 2026  
**Queue entry:** `observed_competition_078`  
**Disposition:** Evidence reviewed; canonical mapping not approved

## Provider observations

| Provider | Competition ID | Season ID | Season label | Observation quality |
|---|---|---|---|---|
| Bzzoiro | `3` | `3::1307` | LaLiga 26/27 | 31 timezone-aware observations; 18 unique team names |
| OpenFootball | `es.1` | `es.1::2026-27` | 2026-27 | 7,600 observations; 380 unique fixtures; 20 home and 20 away team names; all kickoff times are local-time values without timezone |

The Priority A audit found **zero exact UTC cross-provider fixture overlaps**. This is a data-quality limitation, not evidence that the two feeds describe different competitions.

## Official LALIGA evidence

1. The [official 2026/27 calendar announcement](https://www.laliga.com/noticias/ya-se-conoce-el-calendario-al-completo-de-laliga-ea-sports-2026-27), published 30 June 2026, establishes the full 2026/27 competition calendar.
2. The [official LALIGA EA SPORTS clubs page](https://www.laliga.com/en-US/laliga-easports/clubs) lists 20 clubs.
3. The [official 2026/27 calendar](https://www.laliga.com/calendar-2026-2027/laliga-easports) shows 38 matchdays, with 20 clubs in each round.

## Roster comparison

The official 20-club roster is fully represented in the OpenFootball observation sample. Bzzoiro's bounded sample contains 18 unique team names and does not include Elche CF or Levante UD. This is a sample-coverage gap; it does not establish that those clubs are absent from Bzzoiro's full season catalogue.

## Assessment

- Competition name and country: **corroborated** by official LALIGA sources and both providers.
- Season label: **corroborated at the descriptive level** (2026/27).
- Official team count: **20**.
- OpenFootball roster: **20/20 observed**, but its sampled kickoff timestamps lack timezone information.
- Bzzoiro roster sample: **18/20 official teams observed**.
- Exact UTC fixture corroboration: **0**.
- Provider-specific season ID equivalence: **not established**.

OpenFootball's local-time timestamps cannot be used for exact fixture matching until a reliable timezone basis is established. Do not infer a timezone from country or venue alone. The Bzzoiro sample is too small to prove complete roster parity.

## Decision and safeguards

The broad competition identity is well supported, but the provider-specific season records and complete source coverage are not yet reconciled. Keep both records source-scoped.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.

Next evidence needed: a larger Bzzoiro roster/fixture sample and an authoritative timezone basis for OpenFootball's kickoff fields. Only then can exact cross-provider fixture corroboration be assessed.
