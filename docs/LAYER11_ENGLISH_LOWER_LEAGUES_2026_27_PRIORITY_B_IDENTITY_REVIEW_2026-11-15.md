# Layer 11 — English lower leagues 2026/27 Priority B identity review

**Queue entries:** `observed_competition_029`, `observed_competition_030`, `observed_competition_031`  
**Priority:** B — single-provider source records  
**Disposition:** Competition identity and broad season format supported; provider mappings held

## Provider observations

| Queue entry | Competition | Provider | Competition ID | Season ID | Season label | Raw observations |
|---|---|---|---:|---|---|---:|
| `observed_competition_029` | League One | Bzzoiro | `86` | `86::1655` | League One 26/27 | 50 |
| `observed_competition_030` | League Two | Bzzoiro | `87` | `87::1674` | League Two 26/27 | 48 |
| `observed_competition_031` | National League | Bzzoiro | `91` | `91::1903` | National League 26/27 | 50 |

All three records are single-provider observations in the approved intake snapshot. The provider season labels identify 2026/27, but the underlying season IDs have not been independently verified.

## Official and governing-body evidence

### EFL League One and League Two

1. The EFL published the official 2026/27 fixture lists for the Championship, League One and League Two on 25 June 2026: https://www.efl.com/news/2026/june/25/the-2026-27-efl-fixtures-are-here/
2. The EFL handbook defines the three-division structure, a maximum of 72 clubs, and 24 clubs each in the Championship and League One: https://www.efl.com/documents/efl-handbook.pdf
3. Official division pages provide current League One and League Two tables and participating clubs:
   - https://www.efl.com/competitions/efl-league-one
   - https://www.efl.com/competitions/efl-league-two

For the 2026/27 EFL structure, the 72-club, three-division allocation gives 24 clubs in each division. A full home-and-away round robin therefore produces 46 matches per club (552 matches per division).

### Enterprise National League

1. The FA published the 2026/27 National League System allocations for Steps 1–6: https://www.thefa.com/news/2026/may/14/nls-club-allocations-2026-27
2. Participating club Altrincham FC published the 2026/27 Enterprise National League roster, listing 24 clubs and the 8 August season opening: https://altrinchamfc.com/en-us/blogs/news/the-enterprise-national-league-2026-27
3. The National League's own 2026/27 coverage identifies the Enterprise National League and publishes the scheduled match programme: https://www.thenationalleague.org.uk/news/2026/november/13/all-games-available-to-watch-on-dazn-this-weekend-/

The 24-club home-and-away format yields 46 matches per club (552 matches across the division).

## Competition classification

- **League One:** men's third-tier EFL league; 24 clubs; 46 matches per club.
- **League Two:** men's fourth-tier EFL league; 24 clubs; 46 matches per club.
- **National League:** men's top non-League division, below EFL League Two; 24 clubs; 46 matches per club.
- These are three distinct competitions and must remain separate canonical competition candidates.

## Evidence limits

- Bzzoiro League One sample: **50 observations**.
- Bzzoiro League Two sample: **48 observations**.
- Bzzoiro National League sample: **50 observations**.
- These samples do not establish complete rosters, exact fixture coverage, or provider season-ID semantics.
- No independent provider observations for these exact queue identities are present in the approved intake snapshot.

## Decision and safeguards

Retain all three Bzzoiro records separately and source-scoped.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.

Next evidence needed: full provider roster and fixture samples, explicit provider season metadata, and independent provider/official fixture comparisons before proposing any crosswalk.