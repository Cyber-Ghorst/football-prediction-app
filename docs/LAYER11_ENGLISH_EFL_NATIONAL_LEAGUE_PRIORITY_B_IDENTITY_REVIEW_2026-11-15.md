# Layer 11 — English EFL and National League Priority B identity review

**Queue entries:** `observed_competition_021`–`observed_competition_025`  
**Priority:** B — single-provider source records  
**Disposition:** Official competition context supported; provider mappings held

## Provider observations

| Queue entry | Competition | Provider | Competition ID | Season ID | Season label | Raw observations |
|---|---|---|---:|---|---|---:|
| `observed_competition_021` | English EFL Trophy | LiveScoreFootball | `18481` | `18481::2026` | 2026 | 1 |
| `observed_competition_022` | English League Championship | LiveScoreFootball | `3914` | `3914::2026` | 2026 | 11 |
| `observed_competition_023` | English League One | LiveScoreFootball | `3915` | `3915::2026` | 2026 | 15 |
| `observed_competition_024` | English League Two | LiveScoreFootball | `3916` | `3916::2026` | 2026 | 30 |
| `observed_competition_025` | English National League | LiveScoreFootball | `3917` | `3917::2026` | 2026 | 33 |

Each is a single-provider record in the approved intake snapshot. The small samples do not prove complete rosters, full season boundaries, or provider-ID equivalence.

## Official English football evidence

### EFL Trophy — national cup

- The EFL confirms that 48 League One and League Two clubs are joined by 16 invited Premier League under-21 teams for the 2026/27 EFL Trophy, creating 16 regional groups of four: https://www.efl.com/news/2026/june/23/under-21-teams-and-group-stage-draw-confirmed-for-2026-27-efl-trophy/
- The official group-stage draw confirms the regional groups and competition progression: https://www.efl.com/news/2026/june/25/efl-trophy-group-stage-draw-confirmed/

### Championship, League One and League Two

- The EFL published the 2026/27 fixtures for all three divisions, with the season opening weekend on 14–16 August 2026: https://www.efl.com/news/2026/june/25/the-2026-27-efl-fixtures-are-here/
- EFL regulations state that the Championship and League One each consist of 24 clubs; the EFL comprises 72 clubs across the three divisions, leaving 24 in League Two: https://www.efl.com/documents/efl-handbook.pdf
- The Championship provider record here is a candidate counterpart to the separate Priority A Championship entry `observed_competition_020`; this is not an approved crosswalk.

### National League

- The official National League reported all 12 Enterprise National League fixtures for a complete 2026/27 matchday: https://www.thenationalleague.org.uk/news/2026/november/13/all-games-available-to-watch-on-dazn-this-weekend-/
- A separate official matchday report also lists 12 fixtures and confirms the 2026/27 season: https://www.thenationalleague.org.uk/news/2026/october/01/how-to-watch-and-follow-the-enterprise-national-league-this-weekend/
- This review does not independently enumerate the complete National League club roster; a current official 2026/27 club directory or standings snapshot is still required before treating the 24-club scope as fully audited.

## Assessment

- **EFL Trophy:** national cup involving 48 EFL League One/Two clubs plus 16 invited U21 sides; one provider observation.
- **Championship:** second-tier EFL league; 24 clubs; 11 LiveScoreFootball observations. Candidate counterpart to Priority A entry `observed_competition_020`, not linked.
- **League One:** third-tier EFL league; 24 clubs; 15 LiveScoreFootball observations.
- **League Two:** fourth-tier EFL league; 24 clubs; 30 LiveScoreFootball observations.
- **National League:** fifth-tier competition; official matchday sources show 12 fixtures, but a complete 2026/27 roster audit remains outstanding; 33 LiveScoreFootball observations.
- The EFL Trophy must remain distinct from the three EFL league divisions.
- All provider-specific season IDs remain source-scoped; the calendar-year label `2026` alone does not establish equivalence to a complete 2026/27 season.

## Decision and safeguards

Keep all five provider records source-scoped.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.

Next evidence needed: larger LiveScoreFootball roster and fixture samples, verified season boundaries, exact timezone-normalized fixture comparisons, and a full National League club directory.