# Layer 11 — Italy, Japan, Mexico and Netherlands Priority B identity review

**Queue entries:** `observed_competition_054`, `observed_competition_055`, `observed_competition_056`, `observed_competition_057`, `observed_competition_058`, `observed_competition_059`  
**Priority:** B — source-scoped provider records  
**Disposition:** Official competition scopes supported; important season-boundary ambiguities retained

## Provider observations

| Queue entry | Competition | Provider | Competition ID | Season ID | Raw observations |
|---|---|---|---:|---|---:|
| `observed_competition_054` | Serie C, Girone C | Bzzoiro | `102` | `102::2116` | 38 |
| `observed_competition_055` | J1 League | Bzzoiro | `49` | `49::1518` | 16 |
| `observed_competition_056` | Japanese J.League | LiveScoreFootball | `750` | `750::2026` | 3 |
| `observed_competition_057` | Liga MX Apertura | Bzzoiro | `19` | `19::1309` | 8 |
| `observed_competition_058` | Mexican Liga BBVA MX | LiveScoreFootball | `760` | `760::2026` | 3 |
| `observed_competition_059` | Eerste Divisie | Bzzoiro | `108` | `108::2220` | 52 |

## Italy — Serie C, Girone C

- The official Serie C club directory lists separate Girone A, B and C groups for 2026/27: https://www.seriec.com/clubs
- Official Girone C schedule and club list: https://www.seriec.com/gironi/girone-c

Girone C is one of three regional groups within the men's third-tier Serie C competition. Keep it separate from Girone A and B under the shared parent; do not merge its club or fixture memberships with the other groups.

## Japan — J1 League season-transition issue

J.League explicitly distinguishes two competitions/seasons:

1. **2026 special season:** the J1 100 Year Vision League, which has its own 2026 standings: https://www.jleague.jp/en/j1/standings/2026/
2. **2026/27 J1 League season:** a separate 20-club, 38-matchday season beginning 7 August 2026 and ending 6 June 2027: https://aboutj.jleague.jp/corporate/about_competitions/season/

The official club-composition announcement also distinguishes the 2026 special season and 2026/27 season: https://www.jleague.jp/news/article/32852/

**Decision:** Bzzoiro's label `J1 League 26/27` is consistent with the 2026/27 season. LiveScoreFootball's `2026` label is ambiguous and may refer to the special transition competition. Do not map competition ID `750` to Bzzoiro ID `49` until raw fixture dates and provider metadata prove the season.

## Mexico — Liga MX Apertura and broad Liga BBVA MX

- The official Liga BBVA MX portal: https://ligamx.net/
- Official league materials identify Apertura 2026 as a distinct tournament within the Liga BBVA MX season: https://tienda.ligamx.net/products/balon-de-futbol-aereus40-apertura-no-5-basic-juego-amateur

Bzzoiro's record is explicitly **Liga MX Apertura 2026**. LiveScoreFootball's record is named broadly **Mexican Liga BBVA MX** and has only three observations with a generic `2026` season label. It is not established whether that provider record covers Apertura only, Clausura only, or both tournaments.

**Decision:** Keep the two records separate. Require exact fixtures and provider tournament-scope metadata before any crosswalk.

## Netherlands — Eerste Divisie

- The KNVB competition model identifies the Eerste Divisie as a 20-team competition: https://www.knvb.nl/competities/competitiezaken/competitiemodel
- The KNVB's period-title rules show the 38-round schedule, with four periods covering rounds 1–38: https://www.knvb.nl/competities/competitiezaken/competitiemodel/periodetitels-in-de-eerste-divisie

The Eerste Divisie is the men's second tier, with 20 clubs and 38 matchdays. Bzzoiro's 52 observations provide a broader sample, but do not alone prove the full provider roster or season-ID equivalence.

## Decision and safeguards

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.
- Keep Serie C group A/B/C separate under their parent.
- Keep J.League's 2026 special season distinct from 2026/27.
- Keep the broad Mexican Liga BBVA MX record separate from the specific Apertura 2026 record.

Next evidence needed: raw fixture-date comparisons for Japan, tournament-scope metadata and exact fixtures for Mexico, and expanded provider roster evidence where samples remain small.