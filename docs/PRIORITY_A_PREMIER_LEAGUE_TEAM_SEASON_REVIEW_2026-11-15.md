# Premier League 2026/27 — Sportmonks team and season review

Generated: 15 November 2026

## Scope and canonical reference

- Competition: English men's Premier League
- Season: 2026/27
- Sportmonks league: `8`
- Sportmonks season: `28083`
- Read-only Sportmonks roster: 20 teams, 20 unique team IDs, no duplicate or missing IDs
- No database access, provider-link writes, fixture writes or prediction-ledger writes were performed by this review.

## Team roster comparison

| Provider | Provider teams observed | Exact name matches | Alias/format matches | Unmatched | Sportmonks teams not observed |
|---|---:|---:|---:|---:|---|
| bzzoiro | 18 | 16 | 2 | 0 | Brentford, Everton |
| openfootball | 20 | 1 | 19 | 0 | None |
| openligadb | 20 | 10 | 10 | 0 | None |

All observed names resolve to the Sportmonks roster using conservative club-name normalization (FC/AFC suffixes and FC prefixes). The complete machine-readable crosswalk is in `premier_league_2026_27_provider_team_season_review.json`.

### Differences requiring attention

- **Bzzoiro:** 18 of 20 canonical clubs appeared in the bounded observation sample. Brentford and Everton were not observed. This is a sample-coverage gap, not evidence that either club is absent from the provider's competition catalogue.
- **OpenFootball:** all 20 clubs match; 19 names carry FC/AFC formatting variants. Its 7,600 observations have no timezone-qualified kickoff values in this snapshot, so they are not eligible for exact UTC fixture comparison.
- **OpenLigaDB:** all 20 clubs match after treating `Brentford F.C.` as a formatting alias for Brentford; the remaining aliases include `FC Arsenal`, `FC Liverpool`, and standard FC suffixes.

## Season identity review

| Provider | Competition ID | Season ID | Season label | Assessment |
|---|---|---|---|---|
| Bzzoiro | `1` | `1::1058` | Premier League 26/27 | Label supports 2026/27; two exact fixture overlaps with OpenLigaDB, both checked against the official schedule. |
| OpenFootball | `en.1` | `en.1::2026-27` | 2026-27 | Explicit 2026 start-year and 2026/27 label; kickoff timezone evidence is missing in the audit. |
| OpenLigaDB | `5996` | `5996::2026` | 2026 | Start-year aligns to 2026/27; two exact UTC overlaps with Bzzoiro, both checked against the official schedule. |
| Sportmonks | `8` | `28083` | 2026/2027 | Canonical target season; 20-team roster retrieved directly from Sportmonks. |

Official Premier League evidence confirms the English men's top-tier competition, its 2026/27 club list and the 2026/27 fixture schedule. The two exact cross-provider overlaps are:
- Aston Villa vs Sunderland — 21 November 2026, 15:00 UTC.
- Hull City vs Brighton & Hove Albion — 22 November 2026, 14:00 UTC.

The evidence supports the public competition identity and season interpretation. It does **not** prove that provider-specific IDs are interchangeable or that each provider's ID has been independently validated against its full raw catalogue response.

## Decision

**Team-name reconciliation: passed for all observed teams.**  
**Competition and season interpretation: strongly supported.**  
**Provider ID equivalence / canonical approval: not yet approved.**

No canonical mappings, provider links, season links, fixture ingestion routes or prediction eligibility were enabled. Keep provider IDs namespaced until raw catalogue metadata and explicit approval are available.

## Safety counts

- Canonical identity approvals: 0
- Provider-link writes: 0
- Season-link writes: 0
- Fixture writes: 0
- Prediction-ledger writes: 0
