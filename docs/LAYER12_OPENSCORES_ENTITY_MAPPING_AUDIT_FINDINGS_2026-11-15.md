# Layer 12 — OpenScores entity mapping audit findings

**Audit date:** 2026-11-15  
**Controller run:** [43753474901](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43753474901)  
**Status:** Read-only audit passed; candidate review completed; no identity mappings approved.

## Scope and live result

The controller executed `openscores_entity_mapping_audit` against the 300 already-staged OpenScores observations and the current Sportmonks-backed canonical catalogue.

| Measure | Result |
|---|---:|
| OpenScores fixture observations | 300 |
| OpenScores competitions / seasons | 6 / 6 |
| Distinct observed teams | 144 |
| Canonical leagues / seasons / teams | 4 / 7 / 88 |
| Unique competition-name candidates | 3 |
| Unique season candidates | 3 |
| Unique exact team-name candidates | 42 |
| Ambiguous competition / team candidates | 0 / 0 |
| New provider links written | 0 |
| Canonical tables modified | No |
| Prediction ledger touched | No |
| Future fixtures / fixtures in next 7 days | 0 / 0 |

The audit completed with `status=pass`, `read_only=true`, and all write-safety indicators clear.

## Competition and season candidates

Three competition candidates are available for human review:

| OpenScores competition | Country | Candidate canonical competition |
|---|---|---|
| La Liga | Spain | Sportmonks 564 — La Liga |
| Premier League | England | Sportmonks 8 — Premier League |
| Serie A | Italy | Sportmonks 384 — Serie A |

The corresponding three season candidates are 2025/2026, matched by exact season-year pair to Sportmonks seasons 25659 (La Liga), 25583 (Premier League), and 25533 (Serie A).

These are candidate relationships only. The source season labels contain competition names plus year pairs, while canonical season labels contain year pairs; the matching logic correctly records the basis as `exact_season_year_pair`. It does not create links.

Three competitions remain without a canonical candidate in the current catalogue:
- Bundesliga (Germany)
- Ligue 1 (France)
- World Cup (country is not supplied)

The current canonical catalogue contains only four leagues (La Liga, La Liga 2, Premier League and Serie A). Lack of a candidate is not evidence that the OpenScores competition is invalid; the corresponding canonical catalogue coverage is incomplete.

## Team candidate findings

Of 144 observed teams, 42 have one exact normalized-name candidate in the current 88-team canonical catalogue. The remaining 102 have no exact-name candidate. No ambiguous exact-name matches were reported.

Even a unique exact name is not sufficient identity evidence. The audit output does not establish a shared stable team identifier between OpenScores and Sportmonks for these candidates, and team candidate rows do not carry competition context that independently proves the club's league/season. Common or shortened labels (for example, "Inter", "Liverpool", "Bournemouth" or "Tottenham") must not be promoted solely from text equality.

Therefore all 42 remain review-only candidates. The 102 unmatched teams remain unresolved; do not fuzzy-match, alias, or impute them.

## Source freshness and future-fixture boundary

All 300 sampled observations are historical relative to the CockroachDB server clock at the audit time. The per-competition samples cover:
- Premier League, La Liga, Bundesliga, Ligue 1 and Serie A: August–October 2025
- World Cup: June 2026

The audit found zero future fixtures and zero fixtures in the next seven days. This independently confirms that this staged sample is historical evidence, not a current future-fixture feed.

OpenScores remains excluded from upcoming-fixture discovery. The former scheduled-fixture observation sync remains disabled. Do not route these observations into the future fixture catalogue or production prediction workflow.

## Required evidence before any mapping approval

A separate, explicit review is required before creating any `provider_entity_links` rows. At minimum:
1. Verify provider league and season identity using stable source identifiers and country/competition metadata.
2. Verify team identity using shared external IDs where available, plus country and competition context; exact names alone are insufficient.
3. Confirm season boundaries and fixture provenance, including timezone-aware kickoff evidence.
4. Run pre- and post-change provider-link parity checks and regression tests.
5. Keep the change isolated from fixture ingestion, prediction eligibility, the prediction ledger, model weights, Layer 1, Layer 2 and TVD unless separately approved.

## Closeout decision

The Layer 12 read-only audit objective is complete: all 300 observations were assessed, candidate classes and missing catalogue coverage were quantified, the future-fixture exclusion was reconfirmed, and zero-write safeguards passed.

**Entity mapping is not complete and is not approved.** The 3 competition, 3 season and 42 team candidates remain pending evidence review. The 3 unmatched competitions and 102 unmatched teams remain unresolved. This is a safe-hold closeout of the audit, not a claim that OpenScores has been integrated into canonical identities or production predictions.
