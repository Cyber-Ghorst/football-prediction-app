# Layer 11 closeout — provider-independent catalogue and reconciliation

**Audit date:** 14 November 2026  
**Status:** Evidence intake and triage complete; unsafe canonical promotions remain blocked by design.

## Scope completed

The provider-independent intake contains **97 observed competition identities**. Every entry now has an explicit disposition in [identity_review_queue.json](../reports/provider_independent_catalogue/identity_review_queue.json):

| Queue band | Count | Final disposition |
|---|---:|---|
| Priority A — multi-provider with country context | 10 | Official-source and raw-observation evidence reviewed; not approved for canonical mapping |
| Priority B — single-provider with country context | 87 | Held as single-provider-only; no independent corroboration |
| Priority C — country missing/ambiguous | 0 | No competition entries in this band |
| Country-unscoped source records | 27 | Held outside identity groups until country evidence is available |

The 87 Priority B records are not silently treated as distinct canonical competitions or merged by name similarity. Their disposition is explicit: preserve each provider's namespaced source identity and wait for a second independent source or stronger official evidence.

## Provider crosswalk audit

The latest read-only crosswalk report was generated at **2026-11-14 15:58:56 UTC**. It examined five active independent provider snapshots:

| Provider | Observations | Leagues | Seasons | Teams |
|---|---:|---:|---:|---:|
| Bzzoiro | 1,530 | 67 | 67 | 1,056 |
| football-data.org | 38 | 4 | 4 | 26 |
| LiveScoreFootball | 159 | 22 | 22 | 148 |
| OpenFootball | 8,748 | 8 | 8 | 0 |
| OpenLigaDB | 14,733 | 38 | 38 | 456 |
| **Total source records/entities** | **25,208** | **139** | **139** | **1,686** |

These are provider-specific counts, not unique global entities. API Ninjas, Highlightly and Open Matchday were skipped by their separate account/terms gates and are not counted as active evidence sources.

The crosswalk audit surfaced **9 league-level manual-review candidates** and **103 team-level manual-review candidates**. All **139 season candidates** remain blocked because their parent competition links are not approved. The five independent provider reports contain no existing league, season or team links to the canonical catalogue.

Machine-readable report: [free_fixture_crosswalk_audit/latest.json](../reports/free_fixture_crosswalk_audit/latest.json).

## Priority A raw-observation validation

The latest read-only Priority A audit was generated at **2026-11-14 16:02:40 UTC** and examined **41,902 raw observations** across the selected provider snapshots. It found **11 exact cross-provider fixture overlaps** across the ten Priority A entries.

Exact overlap is strong fixture-level corroboration, but it does not independently approve a competition or season mapping. OpenFootball's local date/time values without timezone evidence remain ineligible for exact UTC matching. The audit also retains the football-data.org missing-country observations and MLS's US/Canada scope distinction as evidence gaps.

Machine-readable report: [priority_a_provider_observation_audit/latest.json](../reports/provider_independent_catalogue/priority_a_provider_observation_audit/latest.json).  
Official-source review: [Priority A identity evidence dossier](PRIORITY_A_COMPETITION_IDENTITY_EVIDENCE.md).

## Final safety and data-integrity result

- Automatic canonical identity approvals: **0**
- Independent-provider league/season/team links written by this review: **0**
- Fixture writes: **0**
- Future-fixture routes enabled by this review: **0**
- Prediction-ledger writes: **0**
- Raw provider observations remain separate from canonical records.
- Local kickoff times without timezone evidence are not guessed or converted.
- The OpenScores observations are not used for future-fixture discovery.

## Layer 11 disposition

**The provider-independent catalogue intake, evidence audit, and review-queue triage are closed.** All 97 entries have a recorded disposition, the ten Priority A entries have external and raw-provider evidence documented, and the remaining 87 single-provider entries are explicitly held rather than left in an ambiguous queue.

Canonical mapping promotion is a separate gated operation: it requires exact source-to-canonical approval and verified canonical targets. This closeout does not pretend that unverified provider IDs are mapped. It leaves those records safely available for later mapping when corroborating evidence or approved canonical targets exist.

The current Sportmonks canonical catalogue sync is separately partial: its last report imported 4 of 5 selected current-year seasons (82 teams, 90 Sportmonks source links) and held FA Cup season 28020 after a repeated-page response. That issue is recorded as a provider pagination limitation, not silently counted as a successful complete catalogue import.
