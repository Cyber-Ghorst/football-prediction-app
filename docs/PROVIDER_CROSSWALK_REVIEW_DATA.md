# Crosswalk review data loading

The provider snapshot store now exposes a bounded query for recent
future_fixture_observations batches. It returns provider, request metadata,
source IDs, payload, retrieval time and payload hash; it does not modify stored
snapshots.

The crosswalk module can extract unique source competition, season and team
entities from archived observations. Duplicate source IDs are consolidated,
observation counts are retained, and conflicting display-name variants remain
visible for review.

Country is extracted only when present in the raw provider payload. The
candidate builder requires exact country context for league/team suggestions;
missing country therefore produces no automatic suggestion. Static-source team
keys are deterministic provider/competition-scoped observation keys, not
canonical team IDs.

This data-loading layer does not approve or persist mappings. Use
save_explicit_provider_entity_links only after a human has reviewed the source
and canonical identities and supplied an approval reason.
