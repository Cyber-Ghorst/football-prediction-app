# Future-fixture discovery and match-data provider separation

## Product workflow

The application must not ask users to guess or manually type teams to obtain a prediction.

1. Collect genuine scheduled fixtures from the dedicated future-fixture sources.
2. Present a searchable catalogue of upcoming fixtures.
3. The user selects one exact fixture.
4. Only then activate the existing weighted prediction model using the selected fixture and validated match context.
5. Store the prediction against the stable fixture identity.
6. After the match, collect a verified final result, evaluate the stored prediction and use the evaluation record for learning and calibration.

The prediction model, its weights, tactical recency policy, TVD and prediction ledger schema are protected by this separation.

## Provider domains

Future-fixture discovery is its own domain: `future_fixtures`. It must not be inferred from a provider having a generic `fixtures` method or supplying historical matches, scores, standings, lineups or statistics.

| Provider | Correct responsibility | Future-fixture discovery status |
|---|---|---|
| Sportmonks | Current-season football data and existing rolling-window scheduled-fixture collector | Implemented current primary, subject to account/competition validation |
| OpenLigaDB | Free public fixture discovery candidate, strongest German coverage | Registered but disabled; adapter/live coverage not yet verified |
| OpenFootball | CC0 public JSON schedule dataset | Registered but disabled; freshness and timezone must be verified |
| Open Matchday | Non-commercial CSV schedule dataset | Registered but disabled; commercial use prohibited absent written permission; fixed CET-1 timestamp needs correction/validation |
| WorldCup26 / LiveScoreFootball API | Public REST fixture candidate | Registered but disabled; actual competition coverage and third-party data rights unresolved |
| Bzzoiro Sports Data | Free-tier football fixture API | Registered but disabled; requires `BZZOIRO_API_TOKEN` and per-competition live validation |
| OpenScores | Read-only historical/result observations and entity-mapping audit | **Not a future-fixture source. Never route it into `future_fixtures`.** |
| Highlightly | Match enrichment: statistics, lineups and supported result corroboration | Not part of the dedicated future-fixture search pipeline |
| API Ninjas | Result/standings and club/squad corroboration; exact result candidates require Sportmonks verification | Not part of the dedicated future-fixture search pipeline |
| API-Football v3 | Historical fixtures/results and supported historical detail within account seasons | Historical only for the configured 2022–2024 account |
| LiveScoreFootball database snapshot | Competition-scoped completed-result/standings corroboration after freshness and identity checks | Not a future-fixture source |

The five free candidates are not considered active sources merely because they are registered. A candidate remains disabled until its adapter has demonstrated future kickoff records, stable IDs, timezone-aware timestamps, scheduled status, competition/season/team identity, freshness, applicable reuse rights, canonical crosswalks, normalization tests and database round-trip behavior. Eligibility is per provider and competition.

## Routing invariants

- `future_fixtures` is the only category used to populate the upcoming-fixture search catalogue.
- OpenScores has no `fixtures` or `future_fixtures` assignment. Its disabled result-validation assignment is audit-only.
- Highlightly, API Ninjas, API-Football and LiveScoreFootball may supply their supported enrichment or historical/result domains, but do not become future-fixture discovery sources by implication.
- The existing collector currently calls Sportmonks only. The five selected free candidates remain disabled until their adapters and live audits are complete.
- No provider may silently overwrite a canonical fixture, kickoff, team identity or score. Conflicts remain visible with provenance.
- Temporary fixture staging is separate from the prediction ledger.

## Activation and prediction safeguards

A selected fixture must have a provider-scoped stable ID, future timezone-aware kickoff, scheduled status, competition and season IDs, and both team identities. Cross-provider records must be reconciled to canonical competition, season and team IDs before the fixture is prediction-ready.

Fixture selection is the trigger for prediction. Background fixture collection must never create predictions for every fixture automatically. Prediction storage and post-match evaluation remain tied to the selected fixture identity.

No change in this provider-routing work authorizes changes to the model weights, TVD, tactical recency, canonical fixture repository or prediction-ledger behavior.
