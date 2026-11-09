# Football Prediction Lab — Layer 2

This version retains the Layer 1 weighted prediction model and `tvd.py` Tactical Vulnerability Detector while using a role-based multi-provider data architecture.

## Files
- `app.py` — Streamlit interface and data workflow
- `engine.py` — weighted prediction engine with explicit missing-data handling
- `tvd.py` — keep the existing Layer 1 file unchanged
- `api_football.py` — dedicated API-Football v3 client
- `api_ninjas.py` — separate API Ninjas client
- `highlightly.py` — separate Highlightly client
- `data_layer2.py` — fixture normalization and team profile collection
- `form_analyzer.py` — last-10 form, goals and venue performance
- `strength_analyzer.py` — opponent-strength values from competition standings
- `availability.py` — injury/lineup summaries; no invented availability score
- `tactical_indicators.py` — conservative indicators from available match statistics

## Install and configure
1. Copy the files into the repository root, replacing `app.py` and `engine.py` and adding the new modules. Keep the existing `tvd.py` and `sample_teams.json`.
2. Set the provider credentials required for the selected season in Streamlit Community Cloud → App → Settings → Secrets:

```toml
SPORTMONKS_API_TOKEN = "YOUR_SPORTMONKS_TOKEN"  # current seasons 2025+
APISPORTS_API_KEY = "YOUR_API_SPORTS_KEY"        # historical seasons 2022–2024
API_NINJAS_API_KEY = "YOUR_API_NINJAS_KEY"       # optional corroboration
HIGHLIGHTLY_API_KEY = "YOUR_HIGHLIGHTLY_KEY"     # optional corroboration/enrichment
```

Never commit or paste provider keys into public code or chat.

3. Ensure `requirements.txt` contains the supplied dependencies and redeploy/reboot the app.

## Important data notes
- API-Football plan coverage and request limits vary. Match statistics may require one API request per fixture; turn off the statistics option to reduce calls.
- A 2026/27 season is usually represented by season `2026`; select a season supported by the API plan.
- The provider may not return a full ten completed matches early in a season. The prediction is blocked below five matches.
- Injury reports are shown, but no availability rating is fabricated from raw injury counts.
- Tactical metrics are calculated only from statistics actually returned. TVD remains available for evidence-based manual ratings.
- Probabilities are model estimates, not guarantees. Backtest and calibrate before using for decisions.

## Provider configuration status

Provider roles in the current app:
- Sportmonks is the primary current-season source for seasons 2025 onward.
- API-Football v3 is the historical specialist for seasons 2022–2024, subject to account plan coverage.
- Highlightly is an independent corroboration/enrichment source; its player enrichment now performs a quota preflight and refuses to proceed when remaining quota is unknown or insufficient.
- API Ninjas supplies optional fixtures/results/standings and club/squad corroboration. Its adapter includes the documented Danish Superliga slug and exposes available rate-limit headers when returned.
- LiveScoreFootball is a read-only, database-snapshot source. Its automatic fallback remains disabled. The diagnostics build its current-season crosswalk from Sportmonks and require fresh per-competition sync metadata; fixture-level update timestamps must also be validated before an individual fixture can be eligible.

Provider health, account quota, competition coverage, and source-data freshness are distinct checks. A successful unit test or public status page does not prove that a user's credential, plan, quota, or selected competition is available.

See MULTI_SOURCE_API_ARCHITECTURE.md for provider responsibilities, reconciliation rules and remaining integration work.

## LiveScoreFootball read-only source

The project includes a read-only adapter for the public [LiveScoreFootball API](https://github.com/rezarahiminia/livescoreFootball), hosted at https://worldcup26.ir. Its documented public endpoints currently require no API key. Set LIVESCORE_FOOTBALL_BASE_URL only when using a different compatible deployment. The API reads stored MongoDB snapshots fed by a separate listener, so it is not a guaranteed real-time feed. The public catalogue currently reports 33 active competitions across multiple countries; the exact per-competition catalogue and coverage must be read at runtime. A competition is eligible for a cross-provider mapping only when its name and country match exactly, it is active, it reports stored data, and its season matches. The adapter is implemented but is not yet enabled as an automatic Layer 2 fallback. See MULTI_SOURCE_API_ARCHITECTURE.md.

## Canonical provider reconciliation

The repository now includes `canonical_data.py`, which normalizes LiveScoreFootball and API-Football v3 match records into a common schema and reconciles matched fields with provider priority and conflict provenance. Cross-provider matching requires an explicit shared competition key, season, home/away team identity and a close kickoff time. Source IDs remain namespaced. The layer is covered by `test_canonical_data.py` and is not yet enabled as automatic fallback in the Streamlit app pending verified competition mappings and source freshness checks.

## Competition crosswalk and provider health (2026-11-07)

- `competition_crosswalk.py` builds a runtime crosswalk from Sportmonks for current seasons and API-Football for historical seasons. It does not guess numeric IDs or fuzzy-match similar competition names.
- A LiveScoreFootball competition is marked verified only after exact normalized competition-name and country matching, active status, stored-data coverage, matching requested season, and a fresh per-competition `coverage.lastSyncedAt`. Ambiguous duplicates and missing/mismatched seasons or stale/missing timestamps fail closed.
- `provider_health.py` also exposes fixture-level timestamp validation. A fresh global or competition sync does not make an individual fixture eligible when its own update timestamp is missing or stale.
- `provider_health.py` separates transport/account health from data freshness. It uses domain-specific freshness limits; a missing or invalid source timestamp is reported as unknown and is never treated as fresh.
- The Streamlit sidebar now includes an opt-in **Run provider health & coverage check** action. It checks API-Football account status/quota, LiveScoreFootball health and sync metadata, and displays the exact competition crosswalk. It does not expose account identity or API keys.
- API-Football documents a quota-exempt `/status` endpoint and daily request counters. Highlightly and API Ninjas are not probed because no verified health/status contract has been added for them.
- These checks are diagnostics only. No automatic provider fallback is activated yet; source match IDs remain namespaced, and match-level freshness/identity validation must pass before data is handed to Layer 2.

## Provider API archive database (CockroachDB candidate)

The project now includes `provider_data_storage.py`, a separate PostgreSQL-wire-compatible storage module intended for CockroachDB. It does not replace the existing Neon prediction ledger.

1. Create a CockroachDB Serverless cluster and copy its PostgreSQL connection string from the CockroachDB console. Keep the TLS/SSL parameters supplied by CockroachDB.
2. In Streamlit Community Cloud → App → Settings → Secrets, add:

```toml
PROVIDER_DATABASE_URL = "YOUR_COCKROACHDB_POSTGRESQL_CONNECTION_STRING"
```

3. Keep the existing `DATABASE_URL` secret unchanged; it continues to point to Neon and stores prediction-ledger rows.
4. The provider archive module creates two tables on first use:
   - `provider_api_snapshots`: append-only JSONB responses with provider, resource type, request parameters, source IDs, retrieval time, expiry and payload hash.
   - `provider_collection_runs`: collection success/failure diagnostics, including HTTP status and bounded error text.
5. Cache keys are provider-scoped and deterministic. Callers must not include API tokens, passwords or other credentials in request parameters. A failed API call is recorded separately and must never replace the last successful snapshot.

The storage module is integrated into the Sportmonks collection path for leagues, seasons, teams, standings, season fixtures, individual fixture details and date-range fixture lookups. The app checks CockroachDB for a fresh provider-scoped snapshot before making a live request, then archives successful responses with provenance and a TTL. Individual fixture details and date-range verification lookups currently use a five-minute freshness window; historical statistics backfill deliberately bypasses the cache and fetches the provider directly. The in-process Streamlit cache remains an additional performance layer. Highlightly/API Ninjas corroboration paths are not yet fully routed through the archive. Existing prediction inputs, provider hierarchy, model weights, recency rules and TVD behavior remain unchanged. Do not migrate or delete Neon ledger data.
