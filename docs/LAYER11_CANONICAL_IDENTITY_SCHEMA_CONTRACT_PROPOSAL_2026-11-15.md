# Layer 11 — canonical identity schema contract proposal

**Review date:** 15 November 2026  
**Status:** Proposed additive schema; no migration or database writes  
**Depends on:** PR #368 architecture review, PR #369 dependency inventory, PR #370 team candidate-key helper

## Decision requested

Adopt an additive, application-owned canonical identity layer while retaining the current `football_leagues`, `football_seasons`, `football_teams`, `football_fixtures` and prediction history as compatibility data during a staged migration.

Do not repurpose existing Sportmonks-originated primary keys as if they were provider-neutral. Do not rewrite old fixture IDs, team IDs, season IDs or prediction records in place.

## Proposed canonical entity tables

The following is a logical contract, not executable migration SQL.

### `canonical_competitions`

- `canonical_competition_id`: application-generated opaque stable ID (primary key).
- `name`, `country_or_territory`, `competition_type`: required identity dimensions.
- `gender_scope`, `age_scope`, `tier_scope`: explicit scope dimensions; unknown values are held for review rather than silently defaulted.
- `identity_status`: `candidate`, `verified`, `merged`, `retired`, or `disputed`.
- `created_at`, `updated_at`, `verified_at`, `identity_version`.
- Descriptive metadata such as logo is non-identity metadata and must not influence equality.

### `canonical_seasons`

- `canonical_season_id`: application-generated opaque stable ID.
- `canonical_competition_id`: required parent canonical competition.
- `season_label`, `start_date`, `end_date`: retain source descriptions and validated date boundaries.
- `identity_status`, timestamps and identity version.
- Season identity is scoped to a verified competition. A shared year or display label is not enough to establish equivalence.

### `canonical_teams`

- `canonical_team_id`: application-generated opaque stable ID.
- `name`, `country_or_territory`, `team_type` (club/national), `gender_scope`, `age_group`, `squad_scope`.
- Optional parent/association reference for reserve or youth sides only when independently evidenced.
- `identity_status`, timestamps and identity version.
- Do not use competition participation as the team's identity. Participation is a separate relationship and season-specific.

### `canonical_fixtures`

- `canonical_fixture_id`: application-generated opaque stable ID.
- `canonical_competition_id`, `canonical_season_id`, `home_canonical_team_id`, `away_canonical_team_id`.
- `scheduled_kickoff_utc`, `kickoff_precision`, `fixture_status`, score fields for completed fixtures.
- `identity_status`, timestamps and identity version.
- Require season-parent consistency and distinct home/away teams. Conflicting kickoff evidence is retained and held for review, not averaged.

## Provider source-link contract

Retain `provider_entity_links` as the source-ID crosswalk, but extend the logical contract to include:

- `provider`, `entity_type`, `provider_entity_id` as the source-scoped unique identity.
- `canonical_entity_id` as a foreign reference to the corresponding canonical entity table.
- `link_status`: `proposed`, `approved`, `rejected`, `suspended`, or `superseded`.
- `evidence_ref`, `approval_reason`, `reviewer`, `approved_at`, `first_seen_at`, `last_seen_at`.
- A source ID may have only one active approved canonical target at a time. Retargeting requires a new auditable decision; never silently update the target.
- Provider IDs are unique only within provider + entity type. They are never compared across providers as global IDs.

The current `provider_entity_link_approval_audit` remains append-only. Its records should capture the full old/new target and status, reviewer, reason and evidence reference for each decision.

## Supporting identity governance tables

### `canonical_identity_aliases`

Records alternate names with entity type, canonical entity ID, normalized alias, source/evidence reference, validity dates and review status. Aliases aid candidate generation; they do not independently approve a source link.

### `canonical_identity_events`

Append-only merge, split, correction and retirement events. Each event records affected entity IDs, replacement/successor IDs where applicable, reason, evidence, reviewer and timestamp. Historical IDs remain resolvable.

### `canonical_entity_participation`

Optional but recommended relation linking canonical team, canonical competition and canonical season, with source evidence and verification status. This supports roster/season checks without confusing a team's identity with its competition membership.

## Compatibility strategy

1. Keep current Sportmonks-backed tables and their primary keys unchanged.
2. Add canonical tables and read-only repository facade methods in a later implementation PR.
3. Create a shadow crosswalk from existing rows to proposed canonical IDs. No source link is approved by this step.
4. Compare counts, identity dimensions, season parentage, team rosters, fixture orientation/kickoff and historical prediction references.
5. Add normalized read paths behind a feature flag while all production writes remain on the legacy path.
6. Enable a bounded write path only after parity and explicit approvals. Existing APIs can temporarily resolve canonical IDs to the exact approved provider ID needed for enrichment.
7. Keep legacy columns/views until every consumer is migrated and a rollback window has elapsed.

## Constraints and invariants

- Canonical IDs must be opaque application-generated IDs, not provider IDs or provider-prefixed IDs.
- Every canonical season belongs to exactly one canonical competition.
- Every canonical fixture references one season, its parent competition, and two distinct canonical teams.
- Every approved provider link targets an existing canonical entity of the same entity type.
- Unverified or disputed entities cannot satisfy fixture promotion or prediction readiness.
- No provider-to-provider equivalence is inferred from numeric IDs, name-only matches, common season labels or a single fixture overlap.
- All source payloads and observation snapshots remain immutable and retrievable.
- All merge/split/relink operations are append-only and auditable.
- Model weights, Layer 1, Layer 2 and TVD are out of scope and must remain unchanged.

## Migration and rollback requirements

Before any production migration:
- Inventory every consumer of the existing entity primary keys and provider ID assumptions.
- Snapshot current row counts and foreign-key/reference counts.
- Produce a dry-run mapping report with explicit unresolved and conflicting rows.
- Test idempotent migration on a copy of production data.
- Prove old and new repository reads return equivalent verified records.
- Verify prediction ledger/history can still resolve original fixture/team/season references.
- Prepare a tested rollback that disables canonical reads/writes and leaves legacy data untouched.

## Open questions requiring a design review

1. Which opaque ID format is preferred: UUID/UUIDv7 or readable prefixed random IDs? The format must not encode provider IDs.
2. Should canonical identity statuses be shared across entity types or use entity-specific state machines?
3. Which competition-scope dimensions are mandatory for all supported sports/competitions, and which are optional but review-blocking when ambiguous?
4. Should source-link approval metadata live in `provider_entity_links` plus append-only audit, or should proposed links be stored separately until approval?
5. Which database constraints can safely be enforced in CockroachDB without breaking existing compatibility rows?

**Recommendation:** approve this as the target logical contract only after answering the open questions. The next code step should be a read-only schema prototype and repository facade tests, not a production DDL migration.
