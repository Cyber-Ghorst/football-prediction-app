# Layer 12 — Multi-primary provider routing

## Objective

Introduce a policy layer that supports multiple primary/co-primary providers by
data category and competition, rather than one global provider winner. Primary
providers may contribute in parallel; fallback sources address missing coverage
or failed requests; validation sources remain independent.

## Current routing policy

- Sportmonks remains active primary for current fixtures, results, match
  statistics, lineups and player data.
- API-Football is primary for the existing historical fixture/statistics
  category, separate from current-season Sportmonks collection.
- OpenScores is registered as a competition-scoped co-primary candidate for
  fixtures and results in the six leagues returned during its authenticated
  connection check: Premier League, La Liga, Serie A, Bundesliga, Ligue 1 and
  2026 FIFA World Cup.
- OpenScores assignments are deliberately disabled in production routing for
  now. Its adapter returns raw read-only MCP payloads and has not been normalized,
  reconciled or round-trip persisted. Enabling it before those steps risks
  malformed fixture identities and duplicate records.

## Routing semantics

`provider_routing.py` provides immutable assignments with provider name, data
category, role (`primary`, `co_primary`, `fallback`, `validation`), priority,
optional competition scope and an explicit enabled flag.

`ProviderRegistry.primary_sources(category, competition)` returns all eligible
primary and co-primary sources; it does not pick one winner. Competition keys
are normalized labels. Production ingestion must resolve them to canonical
competition identities before routing. Numeric IDs from different providers
must never be compared directly.

## Integration safety gates

Before activating another source in production:
1. Normalize fixture, team, competition and season identifiers.
2. Establish provider-to-canonical entity crosswalks using verified IDs; do not
   fuzzy-merge teams by name alone.
3. Reconcile fixtures only when canonical competition, canonical home/away teams
   and kickoff agree within an explicitly configured tolerance.
4. Preserve provider fixture IDs, raw payloads, retrieval timestamps and
   field-level source provenance.
5. Record conflicting values; do not average scores/statistics or silently
   replace a source value.
6. Deduplicate statistics by canonical fixture, team, metric and source. Never
   sum the same metric across providers.
7. Keep fallback and validation records separate from primary model inputs.
8. Run provider-specific live coverage and database round-trip checks before
   enabling an assignment.

This policy layer does not change prediction weights, tactical recency rules,
TVD, the prediction ledger or current fixture collection. The automatic
collector continues to ingest Sportmonks only until OpenScores normalization
and cross-provider reconciliation pass the integration gates above.

## Tests

`test_provider_routing.py` covers co-primary resolution, competition scoping,
role separation, disabled candidates and registry validation.
