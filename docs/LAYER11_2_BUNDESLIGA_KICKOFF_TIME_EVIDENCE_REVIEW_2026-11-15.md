# Layer 11 — 2. Bundesliga fixture-time evidence review (2026-11-15)

## Purpose

Resolve the five exact Bzzoiro/OpenLigaDB fixture overlaps for the 2026/27 2. Bundesliga whose official kickoff timezone basis was previously unclear.

This is an evidence-only review. It does not approve a canonical competition or season identity, provider crosswalk, team mapping, fixture ingestion, or prediction eligibility.

## Provider audit observations

The Priority A observation audit reports five exact team-pair and UTC-kickoff overlaps between Bzzoiro and OpenLigaDB:

| Home | Away | Provider kickoff UTC |
|---|---|---:|
| 1. FC Nürnberg | Eintracht Braunschweig | 2026-11-21 12:00Z |
| Hannover 96 | SpVgg Greuther Fürth | 2026-11-21 12:00Z |
| VfL Wolfsburg | Holstein Kiel | 2026-11-21 12:00Z |
| FC Energie Cottbus | Hertha BSC | 2026-11-22 12:30Z |
| Karlsruher SC | VfL Osnabrück | 2026-11-22 12:30Z |

## Official DFB schedule and timezone conversion

The official DFB Datencenter's 2. Bundesliga 2026/27 Matchday 12 page independently lists all five pairings and their German local kickoff times:

- Saturday 21 November, 13:00: Nürnberg vs. Eintracht Braunschweig
- Saturday 21 November, 13:00: Hannover 96 vs. SpVgg Greuther Fürth
- Saturday 21 November, 13:00: VfL Wolfsburg vs. Holstein Kiel
- Sunday 22 November, 13:30: Energie Cottbus vs. Hertha BSC
- Sunday 22 November, 13:30: Karlsruher SC vs. VfL Osnabrück

Official source: https://datencenter.dfb.de/datencenter/2-bundesliga/2026-2027/12  
English official schedule: https://datencenter.dfb.de/en/competitions/3/seasons/current/current_matchweek

Germany is on Central European Time (CET, UTC+1) on 21–22 November 2026. Therefore:

- 13:00 CET converts to 12:00 UTC.
- 13:30 CET converts to 12:30 UTC.

All five DFB local kickoff times therefore agree exactly with the provider UTC timestamps. The earlier apparent one-hour discrepancy was caused by comparing German local schedule times with UTC provider values without converting the timezone. It is resolved; the provider timestamps are not shown to be wrong by this evidence.

## Decision

- Fixture pairings: **5 of 5 independently corroborated** by the official DFB schedule.
- Kickoff times: **5 of 5 confirmed after CET-to-UTC conversion**.
- Provider timestamp quality for these five pairs: **no discrepancy identified**.
- Competition identity: official context supports 2. Bundesliga as Germany's men's second tier; provider-specific competition IDs remain unverified.
- Season identity: 2026/27 is supported by official season context, but provider season IDs remain unverified.
- Canonical mappings/provider links: none approved by this document.
- Fixture writes, prediction eligibility, and prediction-ledger writes: none authorized.

## Required next checks

1. Verify the provider-specific season metadata and full 18-club roster for Bzzoiro season `94::1967` and OpenLigaDB season `4938::2026`.
2. Compare more fixtures across both providers against the official DFB schedule.
3. Keep competition and season identity unapproved until provider IDs, club roster and season semantics are independently verified.

## Safeguards

This review is documentation and evidence only. It makes no database changes and does not alter the prediction model or any provider ingestion route.
