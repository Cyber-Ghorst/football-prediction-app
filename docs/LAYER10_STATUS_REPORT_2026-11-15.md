# Layer 10 — advanced football data intelligence status report

**Review date:** 2026-11-15  
**Status:** Source assessment and read-only OpenScores validation complete; no-go for production xG/shot-quality integration under the current zero-cost and broad-coverage requirements.

## Decisions carried forward

The free-source review in `docs/FREE_ADVANCED_DATA_SOURCE_REVIEW.md` remains controlling:

- No reviewed provider currently meets all three requirements: USD 0 recurring cost, usable advanced shot/player metrics, and relevant broad competition coverage.
- OpenScores has free commercial-use terms and useful fixtures, lineups, squads, player profiles, match events and team/player aggregates, but its documented API does not expose shot-level xG, shot coordinates or xG chain.
- American Soccer Analysis exposes xG, xPass and Goals Added under CC BY-SA 4.0, but coverage is North-American only and share-alike/attribution obligations require segregated handling.
- OpenFoot's advanced xG endpoints are paid. PitchAPI's advertised free advanced tier still lacks sufficiently verified reuse terms/provenance. StatsBomb Open Data remains research-only under its custom terms.
- Therefore, no new advanced xG source is approved for production integration in this milestone. Do not pay for an API or assume rights that have not been established.

## Live OpenScores validation

Two read-only controller operations passed on 2026-11-15:

- Connection check: authenticated successfully; 6 competitions returned; 1 season and 50 fixtures sampled.
- Entity mapping candidate audit: 300 stored fixture observations across 6 competitions and 6 seasons; 144 distinct teams seen home or away.
- The 300 observations are historical snapshots, not a future-fixture feed. The audit found zero upcoming fixtures and zero fixtures in the next seven days across the six stored competition-season groups.
- The canonical Sportmonks catalogue at audit time contained 4 leagues, 7 seasons and 88 teams.

Controller runs:
- Connection: https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43752569411
- Initial read-only mapping audit: https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43752656394
- Post-fix read-only mapping audit: https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43753159796

## Audit correction merged

PR #430 merged the following safe improvements:

- Resolve the OpenScores ISO-3 league country codes DEU, ESP, FRA, ENG and ITA, with a fail-closed policy for unknown codes.
- Match season candidates by an exact two-year season pair when source and canonical labels differ only by a competition prefix and source dates are unavailable.
- Add regression tests for country-code matching, exact season-year matching and unknown-code rejection.

Post-fix candidate results:
- 3 league candidates require human review: La Liga → Sportmonks 564 (Spain), Premier League → Sportmonks 8 (England), Serie A → Sportmonks 384 (Italy).
- Bundesliga (Germany), Ligue 1 (France) and World Cup have no matching canonical league in the current Sportmonks catalogue.
- 3 unique season candidates require human review: the 2025/2026 season for La Liga, Premier League and Serie A. Their match basis is the exact season-year pair; the OpenScores season metadata does not provide usable start/end dates in the returned sample.
- 45 of 144 observed teams have a unique exact-name candidate. 105 have no exact-name candidate and remain unresolved. Name-only team candidates are not proof of identity.
- All candidates are review-only. No provider entity links were created.

Post-merge Python tests passed on main: https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43753146904

## Safety and production boundary

- OpenScores remains a secondary, read-only corroboration source.
- The adapter is not a future-fixture discovery provider and must not be used to populate the upcoming-fixture cache.
- No automatic canonical mappings or provider links are approved by this report.
- No fixtures, canonical entities, provider links, prediction-ledger rows, prediction inputs, model weights, tactical recency rules or TVD behavior were changed.
- Missing advanced metrics must remain missing, never be imputed as zero.
- Any future production enrichment requires independently verified source rights, current-season coverage, exact fixture/player identity, source timestamps, field-level provenance, conflict handling and separate tests/approval.

## Layer 10 disposition

The source review, OpenScores read-only adapter, live connectivity check, candidate audit and audit-parser correction are complete. The advanced xG/shot-quality production integration is explicitly **no-go** under the current zero-spend and broad-coverage constraints; this is a deliberate evidence-based hold, not an unfinished integration silently treated as delivered.

The next immediate project priority is Layer 6 — Application Interface and UX. Layer 10 must not be reopened unless a genuinely free, legally usable and sufficiently broad advanced-data source becomes available, or the user explicitly changes the zero-spend constraint.
