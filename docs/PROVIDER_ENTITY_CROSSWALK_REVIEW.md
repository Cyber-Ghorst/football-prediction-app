# Provider entity crosswalk review

## Candidate generation

The provider_entity_crosswalk module can generate candidate links for leagues,
seasons and teams. It requires:
- Exact normalized entity names.
- Exact country context for leagues and teams.
- A previously verified canonical parent competition for season matching.
- A unique canonical candidate.

Candidates are never persisted automatically. Ambiguous, unmatched, missing-ID
and missing-country cases are explicitly reported and remain unmapped.

## Explicit approval and persistence

save_explicit_provider_entity_links requires:
- A supported provider.
- A supported entity type.
- Provider-scoped source ID and an existing canonical entity ID.
- An explicit approval reason of at least 12 characters.

The function rejects conflicting existing links instead of overwriting them.
Successful new links are stored in provider_entity_links and their approval
reason is appended to provider_entity_link_approval_audit.

## Current boundary

This adds a review mechanism; it does not create mappings automatically and
does not activate future-fixture routes. Provider IDs remain namespaced. No
fixture, league, season or team rows are inserted into the canonical football
repository by candidate generation. No prediction-ledger data is changed.
