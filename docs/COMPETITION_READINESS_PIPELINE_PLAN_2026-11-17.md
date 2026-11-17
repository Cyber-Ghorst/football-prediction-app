# Competition readiness expansion plan

**Prepared:** 2026-11-17  
**Source audit:** `reports/free_fixture_crosswalk_audit/latest.json` generated 2026-11-16T22:34:12.249059+00:00  
**Tracking issue:** #594

## Current baseline

The latest crosswalk audit reports 91 provider-independent competition name/country groups, of which 12 are corroborated across multiple providers and eligible for manual canonical seed review. These are review candidates, not 12 approved competitions and not 12 prediction-ready competitions.

The audit reports zero automatic mapping approvals, zero canonical rows created, zero canonical fixture writes and zero prediction-ledger writes. This is intentional: identity evidence is not yet sufficient to approve mappings automatically.

## Initial candidate register

All 12 candidates below have cross-provider season start-year overlap at 2026. That overlap is supporting evidence only; it does not prove equivalent season IDs or active-season alignment.

| Competition | Country | Providers observed | Competition-type evidence | Initial review priority |
|---|---|---|---|---|
| Premier League | England | Bzzoiro, football-data.org, OpenFootball, OpenLigaDB | Single-provider type evidence | A |
| Bundesliga | Germany | Bzzoiro, football-data.org, OpenFootball, OpenLigaDB | Single-provider type evidence | A |
| Ligue 1 | France | Bzzoiro, football-data.org, OpenFootball | Single-provider type evidence | A |
| Serie A | Italy | Bzzoiro, football-data.org, OpenFootball | Single-provider type evidence | A |
| Eredivisie | Netherlands | Bzzoiro, football-data.org, OpenFootball | Single-provider type evidence | A |
| Championship | England | Bzzoiro, football-data.org, OpenFootball | Single-provider type evidence | B |
| La Liga | Spain | Bzzoiro, OpenFootball | Type not supplied | B |
| Austrian Bundesliga | Austria | Bzzoiro, LiveScoreFootball | Type not supplied | B |
| 2. Bundesliga | Germany | Bzzoiro, OpenLigaDB | Type not supplied | B |
| Saudi Pro League | Saudi Arabia | Bzzoiro, LiveScoreFootball | Type not supplied | B |
| Scottish Premiership | Scotland | Bzzoiro, LiveScoreFootball | Type not supplied | B |
| MLS | United States | Bzzoiro, LiveScoreFootball | Type not supplied | B |

Priority A is a review order based on breadth of independent provider corroboration and explicit type metadata being present somewhere in the provider set. It is not an approval or a claim of statistical readiness. Priority B candidates need stronger identity/type evidence before season and team onboarding.

## Required readiness gates

A competition can be marked **prediction_ready** only when all hard gates pass:

1. **Competition identity:** exact competition name/alias, country and competition type are verified against reliable evidence. Provider IDs remain namespaced.
2. **Season identity:** provider season records align to the same competition and season window; season-year overlap alone is insufficient.
3. **Team crosswalk:** every team participating in a candidate fixture has an approved canonical team mapping, with home/away orientation preserved.
4. **Fixture:** the selected fixture is upcoming, scheduled, belongs to the verified season and has fresh source evidence.
5. **History:** each participating team has 10 valid completed matches in the selected season/context where available. A 5–9 match sample may be surfaced as limited evidence, but must not be labelled full readiness.
6. **Statistics:** required core tactical statistics are present and validated per team/match. Report field-level coverage; never impute missing values.
7. **Tactical profiles:** playing style, defensive structure and attacking approach have evidence; tactical compatibility is evaluated only when both teams have adequate inputs.
8. **Integrity/freshness:** duplicate, invalid-score, wrong-season and stale-source exclusions are reported. Unknown freshness is not silently treated as fresh.

Optional injuries and confirmed lineups remain explicitly unknown when unavailable; their absence must not be represented as positive evidence.

## Status definitions

- **not_ready:** at least one identity, season, fixture, team-mapping or minimum-data hard gate is absent or contradicted.
- **partially_ready:** identity and fixture path are credible, but one or more preferred history/statistics/tactical coverage targets are incomplete. The report must list blockers and distinguish limited-sample evidence.
- **prediction_ready:** every hard gate passes and the complete readiness evidence is timestamped.

The status is competition/season-specific. A competition must not inherit readiness from another season.

## Implementation sequence

1. Build a read-only competition-level evaluator that consumes explicit canonical identity, approved crosswalk, fixture, history, statistics, freshness and integrity evidence.
2. Add deterministic unit tests for missing country/type, season mismatch, unmapped teams, insufficient history, incomplete statistics, stale evidence and a fully passing case.
3. Produce a machine-readable JSON report and concise Markdown summary with per-competition blockers, evidence timestamps and counts.
4. Integrate the report into scheduled GitHub Actions after provider catalogue/crosswalk refresh.
5. Only after a candidate passes the read-only gate should a separately reviewed promotion workflow create canonical mappings or make fixtures available to prediction selection.

## Safety invariants

- This plan and the readiness audit are read-only.
- No automatic canonical IDs, cross-provider links, team mappings, fixture promotion or prediction-ledger writes.
- No model-weight, TVD, or tactical recency-weight changes.
- Preserve the existing Layer 1/Layer 2 prediction model and the 60% latest-five / 40% previous-five tactical recency rule.
- OpenScores remains historical-observation-only and is not a future-fixture discovery source.
- All provider terms, quotas and non-commercial-use acknowledgements remain respected.

## Success measure

Track the number of competitions by status, not just provider catalogue size or future fixture count. The first milestone is five independently verified prediction-ready competitions; no candidate is counted until all hard gates pass.
