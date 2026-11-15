# ADR — Provider-neutral canonical identity and repository migration

**Date:** 15 November 2026  
**Status:** Proposed; design only, not approved for database migration  
**Scope:** Layer 12 provider-neutral canonical architecture  
**Decision owners:** Project owner / explicitly assigned reviewer

## Context

The current CockroachDB repository is provider-shaped despite its canonical naming:
- `football_leagues`, `football_seasons`, `football_teams` and `football_fixtures` use string primary keys that are currently formed as `sportmonks:<provider-id>`.
- `football_repository.py` hard-codes Sportmonks in the importers, sync keys, link creation, fixture-statistics resolution and at least one historical fixture query.
- `upsert_discovered_fixtures()` is a legacy Sportmonks-only write path and creates `provider_entity_links` while inserting rows. It must remain retired from future-fixture collection and must not be treated as a safe generic ingestion interface.
- Existing app consumers expect Sportmonks integer IDs and Sportmonks payload shapes. Simply changing the ID prefix or accepting a second provider would break those consumers.
- Provider identity candidates and verified source links are distinct. The 25 exact-name Highlightly/LiveScoreFootball team pairs from the 15 November roster audit remain candidates, not approved mappings.

The project needs a durable application-owned identity model while preserving the legacy repository and prediction history.

## Decision proposed

Adopt an additive canonical identity registry. Keep existing provider-shaped repository rows and identifiers unchanged during migration. Introduce application-owned UUID identities as the stable canonical references, and keep every provider ID namespaced in source-link records.

### 1. Canonical entity registry

Proposed table:

```sql
CREATE TABLE canonical_entities (
    canonical_entity_id UUID PRIMARY KEY,
    entity_type TEXT NOT NULL
        CHECK (entity_type IN ('league', 'season', 'team', 'fixture')),
    identity_key TEXT NOT NULL,
    display_name TEXT NOT NULL,
    country_or_territory TEXT,
    parent_canonical_entity_id UUID,
    identity_status TEXT NOT NULL
        CHECK (identity_status IN (
            'candidate', 'verified', 'legacy_anchor', 'conflict', 'retired'
        )),
    identity_key_version INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (entity_type, identity_key)
);
```

Rules:
- IDs are application-generated UUIDs, not copied from a provider.
- A candidate key does not make an entity verified.
- `legacy_anchor` preserves a pre-migration record without asserting equivalence to any other provider.
- Parent identity is required for season/team/fixture according to entity-specific validation; no parent is inferred from a name alone.
- Conflict and retirement are explicit states; never silently merge or overwrite identities.

### 2. Entity-specific canonical dimensions

A companion `canonical_entity_dimensions` table (or typed tables if query performance requires them) must store the dimensions used by the key:

- League: normalized competition name, country/territory, competition type.
- Season: canonical competition ID, normalized season label, verified start/end dates.
- Team: normalized name, country/territory, team type (club/national), gender, age group, squad scope (first team/reserve/academy), and parent competition only when the competition is genuinely identity-defining.
- Fixture: canonical season and competition, ordered canonical home/away team IDs, kickoff UTC, and verified fixture status.

Team scope must distinguish club from national team, men's/women's/mixed, senior/youth, and first-team/reserve/academy. Missing or placeholder dimensions block verification. A team must not be assigned to a country from its league's country unless provider evidence independently supports that value.

### 3. Candidate evidence separate from approved links

Proposed `provider_entity_link_candidates` table:

```sql
CREATE TABLE provider_entity_link_candidates (
    candidate_id UUID PRIMARY KEY,
    provider TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    provider_entity_id TEXT NOT NULL,
    proposed_canonical_entity_id UUID,
    candidate_status TEXT NOT NULL
        CHECK (candidate_status IN (
            'candidate', 'needs_evidence', 'ambiguous', 'rejected', 'approved'
        )),
    match_method TEXT NOT NULL,
    evidence_reference TEXT,
    evidence_payload JSONB,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, entity_type, provider_entity_id, proposed_canonical_entity_id)
);
```

Candidate rows never satisfy prediction readiness and are never returned by the approved-link resolver.

The existing `provider_entity_links` table remains the approved mapping table. Additive audit columns should include `approved_by`, `evidence_reference`, `approval_method`, and `decision_timestamp`. Keep the existing approval audit history; do not backfill reviewer identities that are not present in the source evidence.

### 4. Provider source identity and payload provenance

Every provider identity remains namespaced by the tuple:

`(provider, entity_type, provider_entity_id)`

Do not treat a numeric ID as globally unique. Preserve provider raw payloads and source timestamps. Multiple providers may map to one canonical entity only after explicit approval. One provider entity may not map to multiple active canonical entities.

### 5. Fixture reconciliation contract

A fixture candidate may be linked only after:
1. The provider competition is linked to the canonical competition.
2. The provider season is linked to the canonical season and that season belongs to the canonical competition.
3. Home and away team links both resolve to distinct canonical teams.
4. Home/away ordering matches exactly.
5. Kickoff UTC is within the established five-minute tolerance.
6. Provider fixture IDs and statuses are unique and non-conflicting.
7. All required mappings are approved and auditable.

Any missing, ambiguous, duplicate, reordered, stale or conflicting identity is held without writes. A fixture's source provider ID remains attached to the canonical fixture as provenance.

## Compatibility and migration plan

### Phase A — inventory and read-only parity (no DB writes)

- Freeze the current schema and legacy ID behavior.
- Build a read-only adapter that exposes normalized records while retaining legacy source IDs.
- Produce parity reports for existing league, season, team, fixture and statistics reads.
- Confirm every existing consumer and workflow, including app, Layer 2, TVD, fixture search, prediction readiness, result sync and learning evaluation.
- Test that no prediction inputs or probabilities change when a legacy Sportmonks record is read through the normalized adapter.

### Phase B — additive schema migration (requires explicit owner approval)

- Create canonical identity and candidate-evidence tables.
- Add approval metadata columns without changing or dropping existing columns.
- Create canonical UUID records for legacy rows with status `legacy_anchor`; do not infer cross-provider links.
- Verify row counts, referential integrity, rollback and backup/restore before enabling any writes.
- Do not migrate prediction ledger IDs or rewrite historical prediction records.

### Phase C — shadow identity resolver

- Resolve each source entity to its namespaced source ID and, only where approved, its canonical UUID.
- Compare old and new repository reads without changing app behavior.
- Report unresolved, conflicting and stale mappings.
- Keep the old Sportmonks code path as a compatibility adapter until parity is proven.

### Phase D — provider-neutral ingestion and enrichment

- Normalize provider responses at adapter boundaries into one internal record contract.
- Write source observations using namespaced IDs and provenance.
- Do not create approved `provider_entity_links` during ingestion.
- Resolve canonical IDs only through the approved-link resolver.
- Select enrichment sources by capability, coverage, freshness and verified mapping—not by a Sportmonks prefix.

### Phase E — prediction consumer migration

- Convert selected stored fixtures and history to normalized canonical references.
- Keep all current prediction weights, Layer 1, Layer 2 and TVD unchanged.
- Prediction remains user-selection-triggered; discovering or storing fixtures must never run a prediction.
- Preserve prediction ledger history and existing evaluation provenance.
- Run shadow comparisons and require exact readiness/prediction parity before rollout.

### Phase F — controlled rollout

- Start with one approved competition and one independent provider.
- Require an explicit approval record, test evidence, parity report and rollback path.
- Expand only after the previous slice passes all integrity and operational checks.

## Non-goals and safety invariants

- This ADR does not authorize a CockroachDB migration or any data writes.
- It does not authorize promotion of the 25 Highlightly/LiveScoreFootball team candidates.
- It does not authorize fixture ingestion, prediction execution or ledger writes.
- OpenScores remains a historical observation/reconciliation source, not a future-fixture discovery source.
- No model weights, Layer 1, Layer 2, tactical analysis or TVD behavior changes.
- No Sportmonks dependency is removed from live consumers until a normalized compatibility path has parity evidence.
- No provider becomes canonical merely because it has a larger catalogue or an active subscription.

## Acceptance criteria before implementation

1. Project owner approves this identity model and migration sequence.
2. Tests prove namespaced provider IDs cannot collide and canonical IDs are application-owned.
3. Tests prove candidate links cannot satisfy approved-link resolution.
4. Tests prove season parent, team scope and fixture home/away/kickoff constraints.
5. Read-only parity reports cover all legacy records and all known consumers.
6. Backup, rollback and staged-write plan are documented.
7. No production schema or data write occurs before these gates pass.

**Recommendation:** approve the design only after review. The next implementation step is a read-only canonical repository facade and parity suite; the database migration remains gated.
