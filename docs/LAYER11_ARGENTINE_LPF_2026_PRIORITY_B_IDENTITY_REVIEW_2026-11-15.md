# Layer 11 — Argentine Liga Profesional 2026 Priority B identity review

**Queue entries:** `observed_competition_002` and `observed_competition_003`  
**Priority:** B — each provider record is single-provider in the approved intake snapshot  
**Disposition:** Official competition identity and 2026 format supported; provider crosswalk not approved

## Provider observations

| Queue entry | Provider | Competition ID | Season ID | Season label | Raw observations |
|---|---|---:|---|---|---:|
| `observed_competition_002` | LiveScoreFootball | `745` | `745::2026` | 2026 | 1 |
| `observed_competition_003` | Bzzoiro | `85` | `85::1635` | Primera LPF 2026 | 3 |

The two queue entries have closely related competition names and both indicate the 2026 calendar year. They are plausible records of the same broad national first-division competition, but the approved intake contains only one provider for each exact name/country identity and only four raw observations in total. No exact fixture crosswalk has been established in this review.

## Official AFA evidence

1. The official 2026 Primera División tournament regulations specify **30 participating first-division clubs**: https://assets1.afa.com.ar/2026/BOLETINES/Boletin-Resoluciones-6818---Complementario-01---Reglamento-Torneos-LPF-Primera-2026.pdf
2. AFA's official draw announcement lists the groups for the 2026 Torneo Apertura and Torneo Clausura, with 15 clubs in each group: https://www.afa.com.ar/es/posts/sorteo-de-la-liga-profesional-2026-se-definen-los-grupos-del-torneo-apertura-y-torneo-clausura
3. AFA's official 2026 season agenda publishes the Apertura and Clausura fixture programmes: https://www.afa.com.ar/o/posts/agenda-para-la-temporada-2026-de-la-liga-profesional

## Assessment

- Country: **Argentina**.
- Competition type: **men's first-division professional league**, officially corroborated.
- Season: **2026 calendar year**, officially corroborated.
- Format: **30 clubs**, split into two groups of 15 for the Apertura and Clausura tournaments.
- LiveScoreFootball sample: **1 observation**.
- Bzzoiro sample: **3 observations**.
- Candidate relationship: **the names and season labels are consistent with the same broad LPF competition**, but this is not a provider crosswalk.
- Exact fixture corroboration: **not established in this review**.
- Provider season-ID equivalence: **not established**.

## Decision and safeguards

Retain both provider records separately and source-scoped. Do not merge the queue entries or create provider links based on name similarity.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.

Next evidence needed: larger provider roster and fixture samples, exact home/away and kickoff comparisons against the official AFA calendar, and explicit season metadata for `745::2026` and `85::1635`.