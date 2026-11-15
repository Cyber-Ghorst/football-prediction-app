# Layer 11 — 2. Bundesliga fixture-time evidence review (2026-11-15)

## Purpose

Record a focused evidence check of the five exact Bzzoiro/OpenLigaDB fixture overlaps currently listed for the 2026/27 2. Bundesliga in `reports/provider_independent_catalogue/priority_a_provider_observation_audit/latest.json`.

This is an evidence-only review. It does not approve a canonical competition or season identity, provider crosswalk, team mapping, fixture ingestion, or prediction eligibility.

## Provider audit observations

The latest Priority A observation audit reports five exact team-pair and UTC-kickoff overlaps between Bzzoiro and OpenLigaDB:

| Home | Away | Audit kickoff UTC |
|---|---|---:|
| 1. FC Nürnberg | Eintracht Braunschweig | 2026-11-21 12:00Z |
| Hannover 96 | SpVgg Greuther Fürth | 2026-11-21 12:00Z |
| VfL Wolfsburg | Holstein Kiel | 2026-11-21 12:00Z |
| FC Energie Cottbus | Hertha BSC | 2026-11-22 12:30Z |
| Karlsruher SC | VfL Osnabrück | 2026-11-22 12:30Z |

These are exact overlaps between the two provider snapshots, not yet official UTC corroboration.

## Official schedule check and discrepancy

The official Bundesliga team schedule pages independently show the following pairings on Saturday 21 November 2026, each listed at **12:00**:

- 1. FC Nürnberg vs. Eintracht Braunschweig — https://www.bundesliga.com/en/2bundesliga/matchday/2026-2027/1-fc-nuernberg
- Hannover 96 vs. SpVgg Greuther Fürth — https://www.bundesliga.com/en/2bundesliga/matchday/2026-2027/hannover-96
- VfL Wolfsburg vs. Holstein Kiel — https://www.bundesliga.com/en/2bundesliga/clubs/vfl-wolfsburg

The official Bundesliga pages are Germany-local schedule displays. On the 21 November date, Germany is on CET (UTC+1). If the displayed 12:00 is local CET, it corresponds to 11:00Z, whereas the provider audit stores 12:00Z. This is a one-hour time-basis discrepancy. The official source pages do not expose a timezone label alongside these team schedule times in the retrieved page text, so this review does **not** assert that the provider timestamps are definitively wrong; it flags the discrepancy for source-level timezone validation.

The remaining two provider-overlap pairs on 22 November have not been independently corroborated against an official team schedule in this review.

An official Bundesliga fixture-time announcement also confirms that exact kick-off dates and times are published for the 2026/27 Bundesliga 2 matchdays: https://www.bundesliga.com/en/bundesliga/news/confirmed-kick-off-times-dates-2026-27-fixtures-23955/

## Decision

- Competition identity: official context supports 2. Bundesliga as a German second-tier league; provider-specific competition IDs remain unverified.
- Season identity: 2026/27 is supported by official season context, but provider season IDs remain unverified.
- Fixture corroboration: five provider-to-provider exact overlaps remain useful candidates; three match pairings are independently visible in official schedules, but their timezone conversion requires resolution.
- Provider timestamps: **hold for timezone-basis review**; do not treat the five overlaps as five officially UTC-confirmed fixtures.
- Canonical mappings/provider links: none approved by this document.
- Fixture writes, prediction eligibility, and prediction-ledger writes: none authorized.

## Required next checks

1. Inspect raw Bzzoiro and OpenLigaDB payloads for timezone/offset fields and the exact timestamp conversion path.
2. Compare each provider's raw local time and UTC representation with the official matchday schedule, including the two 22 November pairings.
3. Add regression tests for timezone normalization before counting these as official exact-UTC corroboration.
4. Keep the competition and season identity unapproved until provider IDs, club roster and schedule semantics are independently verified.

## Safeguards

This review is documentation only. It makes no database changes and does not alter the prediction model or any provider ingestion route.
