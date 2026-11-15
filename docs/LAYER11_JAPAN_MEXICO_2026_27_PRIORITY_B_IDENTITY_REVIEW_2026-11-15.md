# Layer 11 — Japan and Mexico Priority B identity review

**Queue entries:** `observed_competition_055`, `056`, `057`, `058`  
**Priority:** B — single-provider records  
**Disposition:** Official competition context supported; cross-provider season scope held

## Provider observations

| Queue entry | Competition label | Provider | Competition ID | Season ID | Season label | Observations |
|---|---|---|---:|---|---|---:|
| `observed_competition_055` | J1 League | Bzzoiro | `49` | `49::1518` | J1 League 26/27 | 16 |
| `observed_competition_056` | Japanese J.League | LiveScoreFootball | `750` | `750::2026` | 2026 | 3 |
| `observed_competition_057` | Liga MX Apertura | Bzzoiro | `19` | `19::1309` | Liga MX, Apertura 2026 | 8 |
| `observed_competition_058` | Mexican Liga BBVA MX | LiveScoreFootball | `760` | `760::2026` | 2026 | 3 |

## Japan — J.League season-transition issue

J.League's official 2026/27 competition page specifies 20 clubs each in J1, J2 and J3. J1 is a 20-club home-and-away competition with 38 matchdays and 380 matches.

- Official 2026/27 season structure: https://aboutj.jleague.jp/corporate/about_competitions/season/
- Official J1 English competition overview: https://www.jleague.jp/en/outline/j1/
- Official 2026/27 club composition: https://www.jleague.jp/news/article/32852/

**Important distinction:** J.League held a separate 2026 transition special season before moving to the 2026/27 autumn-to-spring calendar. The official special-season description is here: https://www.jleague.jp/news/article/29712/

The Bzzoiro row explicitly labels 2026/27. The LiveScoreFootball row only says 2026 and has three observations. It may refer to the transition special competition or the 2026/27 season, and its generic name does not identify J1 versus J2/J3. Do not crosswalk these records without exact fixtures and season metadata.

## Mexico — Liga MX Apertura and umbrella league

- N+ reports the official 2026 Apertura calendar: 18 clubs, opening on 16 July 2026, a 17-match regular phase, and a final Liguilla phase: https://www.nmas.com.mx/deportes/liga-mx-anuncia-calendario-oficial-del-apertura-2026-este-dia-arranca-el-torneo/
- The FMF's official Liga BBVA competition regulations identify the 18-club structure: https://fmf.mx/docs/reglamentos/497.pdf

The Bzzoiro label is explicitly **Liga MX Apertura 2026**. The LiveScoreFootball label **Mexican Liga BBVA MX** is generic and has only three observations. It does not establish whether the row represents Apertura 2026, Clausura 2026 or a broader league scope. Keep the tournament-specific and generic records separate until exact fixture-level evidence identifies the season and tournament.

## Assessment

- **J1 League:** Japan men's top tier, 20 clubs, 38 rounds and 380 matches in 2026/27.
- **Japanese J.League:** candidate J.League identity, but 2026 season scope is ambiguous due the separate transition special season and the 2026/27 full season.
- **Liga MX Apertura:** Mexico men's top-tier Apertura tournament, 18 clubs, 17 regular-season rounds followed by Liguilla.
- **Mexican Liga BBVA MX:** generic top-tier label; tournament/season scope not established by three observations.

## Decision and safeguards

Retain all four provider rows separately and source-scoped. Do not treat generic season labels as evidence of provider season equivalence.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.

Next evidence needed: broader roster/fixture samples, exact tournament/season metadata, and home/away plus kickoff comparisons before any cross-provider link is proposed.