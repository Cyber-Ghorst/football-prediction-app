# Zero-cost advanced football data source review

**Assessment date:** 2026-11-10  
**Budget ceiling:** USD 0, including recurring fees  
**Decision:** No new advanced-data provider is approved for production integration in this milestone.

## Executive decision

The review found two sources with explicit reuse terms and useful data, but neither currently meets the app's combined requirements for (a) zero cost, (b) usable advanced shot/player metrics, and (c) relevant broad competition coverage.

- American Soccer Analysis (ASA) exposes xG, xPass and Goals Added under CC BY-SA 4.0, but its documented competitions are North American leagues only. Share-alike and attribution obligations need to be respected.
- OpenScores permits commercial and non-commercial use at no charge under its terms, and covers the top-five European leagues plus the 2026 World Cup. Its documented API exposes fixtures, events, lineups, squads, player profiles and team/player aggregates, but does not document shot-level xG or shot maps. Its ingest is described as daily, not a live minute-by-minute feed.

The best zero-cost option is therefore **not yet a drop-in Opta replacement**. OpenScores may be evaluated separately for basic player/team intelligence if its data provenance and coverage are verified; ASA can be considered for a segregated North-American research path. Neither should be wired into the prediction model on the strength of this assessment alone.

## Source comparison

### 1. American Soccer Analysis (ASA)

Official API client documentation:
https://american-soccer-analysis.github.io/itscalledsoccer-r/

- Data licence: CC BY-SA 4.0.
- Documented metrics include player/team xG (xGoals), xPass and Goals Added (g+).
- Documented coverage: MLS, NWSL, USL Championship, USL League One, USL Super League, MLS NEXT Pro and historical NASL.
- The API/client is public and does not describe a subscription charge.
- Limitation: this is North-American competition coverage, not a source for the app's general European, African or global fixture universe.
- Licence implication: attribution is required; adaptations/redistributions of covered material may trigger share-alike obligations. Legal compatibility should be checked before combining or redistributing derived data in the app.

**Assessment:** technically useful for advanced metrics, but only for matching competitions and only after licence-compatible handling. Do not apply ASA values to teams/players in unrelated competitions or infer missing metrics.

### 2. OpenScores

Official documentation:
https://openscores.ai/docs  
Terms:
https://openscores.ai/terms  
FAQ:
https://openscores.ai/faq

- Pricing: documented as free, with no credit card or paid tier required for its public service.
- Terms explicitly permit use to power personal or commercial products and permit caching/transforming responses inside an application.
- Restrictions include not reselling raw data as a competing dataset/API and not abusing the service.
- Documented competition coverage: top-five European leagues and the 2026 FIFA World Cup.
- Documented data: fixtures, standings, match event timelines, lineups/formations, squads, player profiles, career aggregates and recent appearances.
- The docs do not currently document shot-level xG, shot coordinates or xG chain as structured API endpoints.
- FAQ describes daily ingest and explicitly says it is not yet minute-by-minute live in-play coverage.
- Terms disclaim uptime, accuracy and completeness; rate limits may change and access can be revoked.

**Assessment:** the clearest zero-cost commercial-use terms among the reviewed candidates and potentially useful for basic squad/player/lineup corroboration. It is not an advanced shot-quality source based on the documented API. Any future adapter must independently validate provenance, timestamps, competition coverage, identity mapping and reliability.

### 3. OpenFoot API

Official documentation:
https://openfootapi.com/docs  
Pricing:
https://openfootapi.com/pricing

- Free Starter is $0 and documents fixtures, scores, schedules, standings, form tables and team search.
- The documented xG shot maps, lineups and live events are in the $14/month Developer plan, not the $0 Starter plan.
- Therefore it fails the project's strict zero-spend requirement for xG.

**Assessment:** reject for advanced xG integration unless the vendor later makes the required endpoints genuinely free. Do not sign up for a paid plan.

### 4. PitchAPI

Public product page:
https://pitchapi.dev/

- The page advertises a no-charge plan with 77 leagues, unlimited requests, shots, xG and player statistics.
- This review did not establish sufficiently clear, authoritative terms covering commercial reuse, redistribution, source-data rights, attribution or service guarantees.
- A free price claim alone does not establish permission to use the data in this app.

**Assessment:** do not integrate until written terms/licence and upstream provenance are clear. Reassess only if the terms confirm zero cost and the intended use.

### 5. StatsBomb Open Data (previous assessment)

Official repository:
https://github.com/hudl/open-data

- Useful historical event and shot-level research data.
- The custom user agreement restricts commercial exploitation and redistribution; it is not an unrestricted production-data licence.
- It remains research-only unless StatsBomb confirms the intended use is permitted at no cost.

**Assessment:** remains NO-GO for production use under the current zero-budget rule.

## Recommended path

1. Keep existing configured providers as the authoritative live prediction pipeline.
2. Do not add ASA to global fixtures; consider it only for North-American competitions and only after implementing the CC BY-SA attribution/share-alike requirements.
3. If useful, separately assess OpenScores as a free secondary source for lineups, squads and player/team profile corroboration. Do not label it an xG/shot-quality provider.
4. Do not use OpenFoot's paid xG endpoints.
5. Keep PitchAPI and StatsBomb disabled until licence/provenance questions are resolved.
6. Never scrape services whose terms prohibit automated access, and never treat absent advanced metrics as zero.
7. Require exact fixture/player identity, source timestamps, field-level provenance, coverage and conflict auditing before any new source can influence a prediction.

## Go/no-go

**No-go for a new advanced xG/shot-quality production adapter in this milestone.**

The only reviewed source with broad documented commercial-use permission at $0 (OpenScores) does not document the advanced shot metrics sought. ASA has the advanced metrics and a clear open licence but only covers North-American competitions. OpenFoot's xG is paid. PitchAPI's advertised free advanced tier lacks sufficiently verified reuse terms in this review. StatsBomb's custom agreement is not suitable for assumed commercial use.

This is a deliberate cost and data-rights safeguard, not a permanent rejection of all free sources. The next implementation candidate, if separately approved, should be a limited OpenScores read-only adapter for lineup/squad/player corroboration, not xG. It must remain non-authoritative and must not change prediction weights or provider priorities.

## Protected model architecture

No runtime code, provider configuration, model inputs, provider priorities, weights, TVD rules or tactical recency weighting are changed by this documentation assessment. The existing model and data-quality gates remain in force.
