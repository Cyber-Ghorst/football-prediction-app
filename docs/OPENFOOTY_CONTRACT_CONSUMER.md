# OpenFooty read-only contract consumer

**Contract:** `openfooty-prediction-data-v1`  
**Pinned schema:** `contracts/prediction-data-response.v1.schema.json`  
**Golden fixture:** `contracts/examples/prediction-data-response.v1.example.json`

The app-side `openfooty_contract.py` module validates an engine response artifact and request correlation. It performs no network calls, provider collection, database writes, source mutation or prediction calculation.

The consumer rejects unsupported contract versions, mismatched request IDs, non-UTC timestamps, invalid fixture identity, mismatched home/away team IDs, malformed provenance, non-finite numeric observations and invalid diagnostics. It returns a detached JSON-safe copy so downstream code cannot mutate the original response object by reference.

A valid `DATA_AVAILABLE` response is only a structurally valid data envelope. It does not establish freshness or model-component completeness. The prediction app must still apply its own data freshness checks and strict component-readiness policy. Observations with `quarantined`, `invalid` or `conflict` provenance must not be used as model inputs.

This consumer is not wired into the live prediction path yet. The global integration switch remains OFF until the engine stored-data adapter, artifact retrieval, cross-repository golden tests and failure/retry acceptance tests are complete.
