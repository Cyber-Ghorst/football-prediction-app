# Premier League provider team-name crosswalk review

**Review status:** evidence-only; no identity approvals or database writes  
**Reviewed:** 2026-11-15  
**Canonical comparison roster:** Sportmonks Premier League, season ID `28083`  
**Provider observation report:** [latest Priority A audit](../priority_a_provider_observation_audit/latest.json)  
**Sportmonks roster audit:** [Premier League roster report](../premier_league_sportmonks_roster.json)

## Scope and safeguards

This document compares provider-observed team names with the 20 names in the current Sportmonks Premier League roster. It is a human-review aid only. It does not approve competition or season identity, create provider team links, create fixture links, alter CockroachDB, change future-fixture routing, or write prediction records.

A name match is not sufficient evidence of season identity or fixture identity. Provider snapshot coverage is limited, and an absent team name means only that the team was not present in the selected observations.

## Provider-level findings

| Provider | Observed teams | Kickoff / season evidence | Review interpretation |
|---|---:|---|---|
| Bzzoiro (`1`, season `1::1058`) | 18 | 30 raw and 30 eligible observations; 9 distinct fixture IDs; season label `Premier League 26/27` parses as 2026/27 | 18 names align to the canonical roster. Brentford and Everton are not observed in this small snapshot; do not infer unsupported teams. |
| OpenFootball (`en.1`, season `en.1::2026-27`) | 20 | 7,600 raw observations; 0 eligible because kickoff values have local date/time but no timezone; season label parses as 2026/27 | All 20 names have plausible canonical matches, but timezone-naive kickoff data cannot establish exact fixture overlap. |
| OpenLigaDB (`5996`, season `5996::2026`) | 20 | 7,600 raw; 5,600 eligible scheduled observations; 2,000 finished observations; timezone-aware kickoff values; season label is calendar year 2026 | All 20 names have plausible canonical matches and scheduled observations exist. Calendar-year 2026 is not proof of equivalence to Sportmonks 2026/27. |

The Priority A audit records two exact cross-provider Premier League fixture overlaps, but competition and season identity remain `not_approved`.

## Candidate name crosswalk

The following are name-equivalence candidates only. Canonical labels are the Sportmonks roster names.

| Canonical Sportmonks team | Bzzoiro observed name | OpenFootball observed name | OpenLigaDB observed name |
|---|---|---|---|
| AFC Bournemouth | Bournemouth | AFC Bournemouth | AFC Bournemouth |
| Arsenal | Arsenal | Arsenal FC | FC Arsenal |
| Aston Villa | Aston Villa | Aston Villa FC | Aston Villa |
| Brentford | Not observed | Brentford FC | Brentford F.C. |
| Brighton & Hove Albion | Brighton & Hove Albion | Brighton & Hove Albion FC | Brighton & Hove Albion |
| Chelsea | Chelsea | Chelsea FC | Chelsea FC |
| Coventry City | Coventry City | Coventry City FC | Coventry City |
| Crystal Palace | Crystal Palace | Crystal Palace FC | Crystal Palace FC |
| Everton | Not observed | Everton FC | Everton FC |
| Fulham | Fulham | Fulham FC | Fulham FC |
| Hull City | Hull City | Hull City AFC | Hull City |
| Ipswich Town | Ipswich Town | Ipswich Town FC | Ipswich Town |
| Leeds United | Leeds United | Leeds United FC | Leeds United |
| Liverpool | Liverpool FC | Liverpool FC | FC Liverpool |
| Manchester City | Manchester City | Manchester City FC | Manchester City |
| Manchester United | Manchester United | Manchester United FC | Manchester United FC |
| Newcastle United | Newcastle United | Newcastle United FC | Newcastle United FC |
| Nottingham Forest | Nottingham Forest | Nottingham Forest FC | Nottingham Forest |
| Sunderland | Sunderland | Sunderland AFC | Sunderland |
| Tottenham Hotspur | Tottenham Hotspur | Tottenham Hotspur FC | Tottenham Hotspur FC |

## Review conclusions

1. **Name coverage:** OpenFootball and OpenLigaDB each expose all 20 canonical roster teams in the selected snapshot. Bzzoiro exposes 18; the two unobserved names are Brentford and Everton.
2. **Fixture evidence:** OpenLigaDB's timezone-aware scheduled observations are suitable for continued exact-fixture corroboration, subject to independent season and competition checks. OpenFootball's timezone-naive kickoff values must not be promoted to exact fixture evidence.
3. **Season evidence:** Bzzoiro and OpenFootball carry 2026/27 season labels. OpenLigaDB carries calendar year 2026 and requires additional evidence before season equivalence can be considered.
4. **Decision remains blocked:** no provider competition or season identity is approved by this document. No team crosswalk is persisted as a canonical provider link.

## Required next evidence

- Validate OpenLigaDB 2026 scheduled fixtures against the official Premier League 2026/27 schedule using exact home team, away team, and UTC kickoff.
- Keep OpenFootball as name/competition corroboration only until timezone semantics are independently established.
- Expand Bzzoiro's observation window before drawing conclusions about its two unobserved roster teams.
- Reassess competition and season identity separately; do not infer either from team-name coverage alone.
