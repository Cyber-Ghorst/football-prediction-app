# Layer 11 closeout — provider-independent catalogue and reconciliation

**Audit date:** 14 November 2026  
**Status:** Evidence intake and triage complete; unsafe canonical promotions remain blocked by design.

## Scope completed

The provider-independent intake contains **97 observed competition identities**. Every entry now has an explicit disposition in [identity_review_queue.json](../reports/provider_independent_catalogue/identity_review_queue.json):

| Queue band | Count | Final disposition |
|---|---:|---|
| Priority A — multi-provider with country context | 12 | Official-source and raw-observation evidence reviewed; not approved for canonical mapping |
| Priority B — single-provider with country context | 85 | Held as single-provider-only; no independent corroboration |
| Priority C — country missing/ambiguous | 0 | No competition entries in this band |
| Country-unscoped source records | 27 | Held outside identity groups until country evidence is available |

The 85 Priority B records are not silently treated as distinct canonical competitions or merged by name similarity. Their disposition is explicit: preserve each provider's namespaced source identity and wait for a second independent source or stronger official evidence.

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

The corrected read-only Priority A audit was generated at **2026-11-15 10:34:18 UTC** and examined **166,037 raw observations** across five independent providers. It found **20 exact cross-provider fixture overlaps** across the twelve Priority A entries after Austrian Bundesliga and Scottish Premiership were promoted from Priority B on the basis of independent provider corroboration and official-source review.

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

**The provider-independent catalogue intake, evidence audit, and review-queue triage are closed.** All 97 entries have a recorded disposition, the twelve Priority A entries have external and raw-provider evidence documented, and the remaining 85 single-provider entries are explicitly held rather than left in an ambiguous queue.

Canonical mapping promotion is a separate gated operation: it requires exact source-to-canonical approval and verified canonical targets. This closeout does not pretend that unverified provider IDs are mapped. It leaves those records safely available for later mapping when corroborating evidence or approved canonical targets exist.

The current Sportmonks canonical catalogue sync is separately partial: its last report imported 4 of 5 selected current-year seasons (82 teams, 90 Sportmonks source links) and held FA Cup season 28020 after a repeated-page response. That issue is recorded as a provider pagination limitation, not silently counted as a successful complete catalogue import.


## 15 November 2026 audit refresh

Following the local-date matching correction merged in commit `875bcca2f0f1be36216e0a96198426e338c6ae72`, both the Priority A audit workflow and the repository Python test/smoke-check workflow completed successfully on `main`.

The refreshed read-only audit was generated at **2026-11-15 10:34:18 UTC**. It examined **166,037 raw observations** across five independent providers and found:

| Evidence class | Count | Interpretation |
|---|---:|---|
| Exact team-pair + UTC-kickoff overlaps | 20 | Strong fixture-level corroboration; not automatic competition/season approval |
| Date-and-team candidate records | 162 | Manual-review leads only; local-time/date evidence is not exact UTC confirmation |
| Distinct date/team fixture leads | 155 | Seven records are repeated provider-pair evidence for the same date/team fixture |
| Priority A identity entries | 12 | All remain `not_approved` pending verified canonical targets and identity-level review |

The 20 exact overlaps are distributed across Premier League (2), 2. Bundesliga (5), Bundesliga (8), Saudi Pro League (1), and Scottish Premiership (4). The 155 distinct date/team leads are concentrated in Bundesliga (96), Premier League (56), and Eredivisie (3). The raw candidate-record count is higher because the same fixture can be corroborated by more than one provider pair.

The correction therefore repaired candidate discovery without weakening the exact-match rule. Date-only/local-time evidence remains explicitly non-confirmatory. The 20 exact overlaps remain evidence for human review, not permission to create canonical competition, season, team, provider, or fixture links.

The refreshed report confirms the following safeguards remained at zero: automatic identity approvals, canonical competition writes, canonical season writes, provider-link writes, fixture writes, future-fixture routes enabled, and prediction-ledger writes. The database transaction remained read-only.

Machine-readable refreshed report: [priority_a_provider_observation_audit/latest.json](../reports/provider_independent_catalogue/priority_a_provider_observation_audit/latest.json).



## Priority B re-triage — 15 November 2026

The refreshed free-provider crosswalk independently identified two former Priority B entries as multi-provider identities with shared 2026 season-year evidence:

- **Austrian Bundesliga — Austria:** Bzzoiro competition 96 / season `96::1999` and LiveScoreFootball competition 3907 / season `3907::2026`; 12 and 3 observations respectively. The official Austrian Bundesliga 2026/27 schedule was reviewed. No exact UTC fixture overlap was found in the selected audit window.
- **Scottish Premiership — Scotland:** Bzzoiro competition 13 / season `13::1355` and LiveScoreFootball competition 735 / season `735::2026`; 18 and 6 observations respectively. Four exact UTC fixture overlaps were found, and the official SPFL 2026/27 William Hill Premiership fixture list was reviewed.

Both entries are now Priority A for manual identity review. This updates the queue to **12 Priority A / 85 Priority B** while keeping all identity statuses unverified and all canonical/provider-link approvals at zero. Their provider IDs are retained as namespaced source identifiers; no canonical links, fixture writes, future-fixture routes or prediction eligibility were enabled.

The crosswalk's 12 corroborated competition candidates now align with the 12 Priority A queue entries. The separate 27 country-unscoped OpenLigaDB source records remain held outside identity groups.



## Final Layer 11 reconciliation — 15 November 2026, 18:06 UTC

This section supersedes earlier interim queue counts and consolidates the latest committed evidence reviews and parity audit.

### Reconciled evidence inventory

| Evidence group | Current count | Final safe disposition |
|---|---:|---|
| Country-scoped competition intake | 97 | Every record has an explicit queue disposition |
| Priority A | 12 | Official competition evidence reviewed; identity/provider-season mapping remains unapproved |
| Priority B | 85 | Official context reviewed in the Priority B evidence dossier; provider identity remains single-source and held |
| Country-unscoped OpenLigaDB records | 27 | Held outside canonical identity groups pending country evidence |
| Priority B alias shortlist | 17 groups | Candidate-only; no aliases or provider links approved |
| Exact UTC fixture overlaps in refreshed Priority A audit | 20 | Human-review evidence only; not automatic identity approval |

The earlier Priority B alias document stated 87 records. That count is superseded: two records (Austrian Bundesliga and Scottish Premiership) were re-triaged to Priority A, leaving 85 Priority B records. The alias shortlist has been reconciled accordingly.

### Priority A final dispositions

All twelve Priority A identities now have official competition evidence reviews. These establish competition scope and provide source provenance, but do not independently verify every provider competition ID, season ID, complete roster or canonical target. The MLS review explicitly preserves the US/Canada cross-border scope discrepancy rather than approving a US-only canonical country. Serie A and Ligue 1 remain separate provider records where timezone/roster evidence is insufficient. Championship and Eredivisie retain their documented kickoff/season evidence gaps.

The 20 exact UTC fixture overlaps are distributed across Premier League (2), 2. Bundesliga (5), Bundesliga (8), Saudi Pro League (1) and Scottish Premiership (4). They remain review evidence, not permission to promote provider links or ingest fixtures.

### Championship alias follow-through

The additional LiveScoreFootball Championship observation record is competition `3914`, season `3914::2026`, with 11 raw observations. Official EFL evidence confirms the 2026/27 Championship is the men's second tier with 24 clubs and 46 league matches per club. The 11-record provider sample does not establish a complete roster, provider season boundaries or timezone-aware fixture overlap with Bzzoiro/OpenFootball. The record therefore remains namespaced and unlinked. OpenFootball local kickoff values without timezone evidence remain excluded from exact UTC matching.

### Live provider-link parity

The latest committed parity audit (`approved_link_parity_latest.json`, generated 2026-11-15 16:26:21 UTC) was read-only and made no database writes.

- OpenScores: 216 link rows — 66 independently verified through its separate verification ledger and 150 fixture observations reconciled by exact observation status. These are not approved cross-provider identity links. OpenScores remains an observation/reconciliation source, not a future-fixture discovery route.
- Sportmonks: 2,010 source-native identity anchors (1,911 fixtures, 4 leagues, 7 seasons, 88 teams). These are legacy source identities, not independent-provider approvals.
- Cross-provider links approved through the separate approval audit: 0.
- Missing targets, ambiguous targets, rejected links and review-required links in this parity snapshot: 0. This is a structural integrity result, not evidence that provider-neutral identity mapping is complete.

### Final safeguards and exit criteria

The following remain unchanged and deliberately gated:

- Canonical competition, season and team promotions: none from this review.
- Cross-provider provider-link approvals: zero.
- Fixture ingestion or future-fixture routing enabled by these identity reviews: zero.
- Prediction eligibility changes: zero.
- Prediction-ledger writes: zero.
- Model weights, Layer 1, Layer 2 and TVD: unchanged.

**Layer 11 evidence intake, competition-scope review, queue reconciliation and read-only parity audit are complete.** The layer is closed in a safe-hold state. The remaining items are not unfinished documentation tasks; they are external evidence/approval gates that cannot be responsibly completed from the current source material: verified provider season metadata, reproducible timezone-aware fixture/team samples, country evidence for the 27 unscoped records, verified canonical targets and explicit approval for any promotion.

Any future promotion must be a separately reviewed change with exact source-to-canonical evidence, pre/post parity checks, rollback coverage and CI. Until then, all held source records remain available without being merged, ingested as canonical fixtures or made prediction-eligible.
