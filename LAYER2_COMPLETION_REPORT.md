# Layer 2 release review

**Review date:** 2026-11-10  
**Scope:** Provider adapters, Layer 2 collection, exact-fixture reconciliation, field-level fallbacks, provenance, data freshness, app integration and runtime readiness.

## Release outcome

Layer 2 implementation and automated validation are complete. The weighted prediction engine and TVD remain unchanged. Provider fallbacks are opt-in and default off; Sportmonks remains the current-season primary source.

The latest available deployed-app diagnostic (2026-11-10 08:02 UTC) reported a healthy system: 13 checks passed, zero warnings and zero failures. The selected Sportmonks fixture was fresh and verified; both selected teams had ten valid completed matches and full coverage of the eight core tactical statistics; the central CockroachDB repository supplied both team histories. A subsequent prediction-performance report was generated at 08:48 UTC.

The CI app-startup smoke test is deterministic and deliberately runs without provider credentials. CI cannot access the deployed Streamlit secrets, so a fresh live request to every external provider and a live LiveScore fallback execution have **not** been claimed after the final code merges. The deployed app's provider-health panel and opt-in controls remain the required credentialed smoke-test path.

## Provider integration status

| Provider | Layer 2 role | Implemented behavior | Guardrails |
|---|---|---|---|
| Sportmonks | Primary current-season source | Competitions, seasons, teams, fixtures, results, statistics and supported team/player data | Exact season/team/fixture identity, explicit completion states, strict scores, freshness and coverage gates |
| API-Football v3 | Historical specialist (account-supported 2022–2024) | Historical fixtures/results and supported details | Account/season plan limits; namespaced IDs and canonical validation |
| Highlightly | Independent current-season secondary source | Opt-in missing-stat, exact-fixture lineup and Sportmonks-verified result-history fallbacks; diagnostics | Exact competition/country/season/fixture/team identity; team IDs checked; Sportmonks values preserved; no injury/availability inference |
| API Ninjas | Independent fixture/result/standings and club/squad corroboration | Opt-in Sportmonks-verified result-history fallback and diagnostics | Exact competition mapping and Sportmonks fixture/score verification; no detailed statistics, injuries or lineups |
| LiveScoreFootball | Conditional competition-specific snapshot fallback | Opt-in missing-score fallback for existing completed Sportmonks fixtures | Fresh global, competition and event timestamps; exact season crosswalk; exact home/away and kickoff identity; unique completed score-valid event; ten-date request cap |

## Data-integrity safeguards reviewed

- Source IDs remain provider-namespaced.
- Cross-provider fixture joins require competition, season, home/away orientation and kickoff agreement.
- Ambiguous duplicate fixtures and conflicting duplicate Sportmonks CURRENT score rows are rejected; conflicting scores remain unknown.
- Invalid, partial, missing or period-only scores are not promoted to full-time results.
- Missing statistics remain unknown rather than being converted to zero.
- Secondary-provider statistics fill only missing supported fields; existing Sportmonks values are retained.
- Result-only fallbacks do not fabricate statistics, opponent strength, injuries or player availability.
- TVD tactical evidence remains on its existing primary-source path.
- Prediction weights and tactical recency weighting remain unchanged: latest five matches 60%, previous five 40%.

## Automated validation

- Compile check (python -m compileall -q .) — passed.
- Full unittest discovery — **374 tests passed** on the Streamlit smoke-test PR.
- Streamlit AppTest — app imports and starts without an uncaught exception when the primary provider is deliberately unavailable; the app surfaces the controlled provider-configuration message.
- Default-off checks — result-history, LiveScore score, Highlightly statistics and Highlightly lineup fallbacks all start unchecked.
- GitHub PR checks passed before merges: #120, #121 and #122.

## Credentialed deployment checks still required

Because CI does not receive Streamlit secrets, run the deployed app's provider health and coverage check after deployment. If enabling an optional fallback for the first time, verify its provider response and archived report before relying on the returned fields. In particular, LiveScore will intentionally skip any event whose own update timestamp is missing, invalid, future-dated or stale.

This limitation is a deployment credential boundary, not a failing unit test. No claim is made that every external provider fallback has been exercised live after the final merge.