# Layer 11 — Greece, Italy and international friendly identity review

**Queue entries:** `observed_competition_048`, `observed_competition_049`, `observed_competition_051`, `observed_competition_052`, `observed_competition_053`  
**Priority:** B — source-scoped records  
**Disposition:** Competition scope supported where applicable; generic friendlies require taxonomy reclassification

## Provider observations

| Queue entry | Record | Provider | Competition ID | Season ID | Raw observations |
|---|---|---|---:|---|---:|
| `observed_competition_048` | Stoiximan Super League | Bzzoiro | `24` | `24::1569` | 1 |
| `observed_competition_049` | International Friendly Games | Bzzoiro | `31` | `31::133` | 91 |
| `observed_competition_051` | Serie B | Bzzoiro | `100` | `100::2084` | 10 |
| `observed_competition_052` | Serie C, Girone A | Bzzoiro | `101` | `101::2103` | 35 |
| `observed_competition_053` | Serie C, Girone B | Bzzoiro | `103` | `103::2130` | 33 |

## Greece — Stoiximan Super League

- The official Super League fixture schedule lists seven matches in each round: https://www.slgr.gr/
- The 2026/27 schedule shows the opening weekend of 22–23 August and seven fixtures per round: https://www.ertsports.gr/super-league/to-programma-tis-super-league-gia-ti-sezon-2026-2027/
- Reporting of the league's 15 July 2026 decision confirms 14 clubs and continuation of the same playoff/playout format: https://www.novasports.gr/sport/podosfairo/event/super-league-1/article/14994384/paramenoun-14-oi-omades-sti-super-league/

Assessment: men's top-tier domestic league, 14 clubs, 26 regular-season rounds followed by championship playoffs, European playoffs and relegation playouts. Bzzoiro contributes only one observation.

## International Friendly Games — classification correction

This is **not one competition**. It is a generic fixture category covering friendly matches between national teams across many countries and windows. It has no single participating-team roster, competition table or tournament season.

- FIFA's international match calendar sets national-team windows: https://inside.fifa.com/football-development/technical/football-calendar
- UEFA's international match calendar also defines windows rather than a single friendly tournament: https://www.uefa.com/european-qualifiers/news/02a1-1f3c6fcb2d72-9fdd6a9a6d3b-1000--international-match-calendar-2026-2027/

**Decision:** Reclassify `observed_competition_049` from a competition identity to a fixture-type taxonomy record after schema review. Do not create a canonical competition or season for it.

## Italy — Serie B

- Lega B confirms 20 clubs for Serie BKT 2026/27: https://www.legab.it/seriebkt/ultime-news/serie-bkt-2026-2027-curiosita-e-statistiche-delle-20-squadre
- The official calendar criteria specify 38 matchdays: https://www.legab.it/news/i-criteri-della-serie-bkt-2026-2027
- Official standings: https://www.legab.it/seriebkt/classifica

Assessment: men's second tier, 20 clubs, 38 rounds and 380 regular-season matches. Bzzoiro has 10 observations; provider season ID `100::2084` and full roster coverage remain unverified.

## Italy — Serie C, Girone A and Girone B

- The official Serie C club directory has separate Girone A, B and C lists for 2026/27: https://www.seriec.com/clubs
- Official Girone A schedule and club list: https://www.seriec.com/gironi/girone-a
- Official Girone B schedule and club list: https://www.seriec.com/gironi/girone-b

Each group has 20 clubs and plays a 38-round double round-robin season. They are regional groups within the national Serie C third tier.

**Decision:** Keep Girone A and Girone B as separate group-scoped competition records under a common Serie C parent. Do not merge their team/fixture memberships across groups or collapse their source IDs.

## Safeguards and remaining work

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.
- Generic international friendlies should be removed from the competition entity queue only after the fixture-type taxonomy is reviewed.
- Verify all provider season IDs and obtain larger samples before mapping.
