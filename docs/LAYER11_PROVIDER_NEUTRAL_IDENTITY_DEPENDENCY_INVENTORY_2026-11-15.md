# Layer 11 — provider-neutral identity dependency inventory

**Review date:** 15 November 2026  
**Base:** `main` after PR #368  
**Status:** Read-only code inventory; no runtime database inspection or migration

## Executive finding

The codebase has provider-independent discovery, observation archives, crosswalk review and source-link concepts, but the canonical repository and several consumers still treat Sportmonks identifiers as the operational identity namespace. The clearest hard blocker is the free-fixture promotion gate, which explicitly rejects canonical targets that are not `sportmonks:` IDs. Prediction-readiness and the main Streamlit collection/prediction flow also directly consume Sportmonks-shaped IDs and payloads.

A safe provider-neutral migration therefore needs a compatibility layer and staged consumer migration. It must not simply change the prefix check or create new canonical IDs while existing consumers still interpret them as Sportmonks IDs.

This inventory is based on the current `main` source files listed below. It does not claim to enumerate every dynamic or external consumer.

## Confirmed dependency inventory

| Area | Current implementation evidence | Migration implication |
|---|---|---|
| Canonical repository schema | `football_repository.py`: `football_leagues`, `football_seasons`, `football_teams`, `football_fixtures` use string primary keys; league/season/team records also require `source_provider`. | Existing primary keys are not intrinsically provider-neutral. Keep them stable during migration; introduce explicit application-owned IDs in an additive schema or a carefully versioned compatibility design. |
| Provider links | `provider_entity_links` stores provider + entity type + provider entity ID + canonical entity ID; `provider_entity_link_approval_audit` stores approval reason. | This is a useful source-link foundation, but the target rows and IDs still need provider-independent semantics. Audit schema should also retain reviewer, evidence reference and decision metadata where not already available. |
| Sportmonks catalogue import | `sportmonks_catalogue_sync.py` calls `import_sportmonks_season`; current imported canonical entities originate from Sportmonks. | Import path must eventually accept reviewed provider-neutral canonical IDs without assuming Sportmonks is the creator/owner. |
| Crosswalk review and persistence | `provider_entity_crosswalk.py` loads existing canonical tables and saves explicit links only after target-existence checks; season links depend on a verified parent competition link. | Preserve the conservative approval model. Generalize canonical target access behind repository interfaces only after target ID semantics are settled. |
| Competition registry | `competition_registry.py` pairs provider-native league/season IDs and creates provider-namespaced discovery identities; candidates remain unverified and prediction-ineligible. | Discovery identities should remain separate from canonical identities. Do not turn provider registry keys into canonical IDs automatically. |
| Provider-neutral candidate keys | `provider_neutral_identity.py` produces deterministic competition keys from name/country/type and season keys scoped to an existing canonical competition. It has no corresponding team key. | Add team identity only after agreeing mandatory scope dimensions (club/national, gender, age, reserve/first team, country/territory); keep keys as candidates until reviewed. |
| Fixture promotion | `free_fixture_canonical_promotion.py` requires four explicit entity links, verifies parent season/competition and team distinction, then rejects any canonical ID that does not start with `sportmonks:`. | This is a direct Sportmonks dependency. Remove it only after downstream consumers can resolve provider-neutral canonical entities and enrichment provider selection is independent. |
| Prediction readiness | `prediction_readiness.py` imports Sportmonks fixture-state logic and expects integer home/away/season IDs and Sportmonks fixture payload shape. | Introduce a normalized fixture/profile contract and provider-specific adapters. Preserve existing readiness gates and scoring inputs. |
| Streamlit app | `app.py` imports Sportmonks clients and Layer 2 collectors, fetches teams/standings/fixtures/squads using integer IDs, archives Sportmonks responses and labels the active Layer 2 path as Sportmonks current-season. | App orchestration is a major migration surface. Split selected canonical fixture identity from provider-specific enrichment IDs; do not rewrite the whole UI in one step. |
| Provider routing | `provider_core.py` defines capability-specific provider order. The current rolling future-fixture collector is documented as retired; new future discovery is handled by free-provider refresh workflow. | Keep future-fixture capability routing distinct from historical/statistics enrichment. Never enable a provider merely because it is listed in a role table. |
| Provider configuration/readiness | `provider_config.py` distinguishes implemented adapters from unverified coverage, licensing, crosswalk and route activation. | Retain explicit readiness states. Adapter presence is not canonical identity approval or route authorization. |
| Upcoming fixture collector | `upcoming_fixture_collector.py` is explicitly retired as Sportmonks-only and directs callers to `free_fixture_provider_refresh.py`. | Keep it retired; do not revive it as a shortcut for canonical ingestion. |
| Prediction result and history | App result sync and Layer 2 paths include Sportmonks-specific fixture/result lookups. Prediction ledger and evaluation records store fixture/provider and competition/season context. | Preserve historical prediction records. Add provider-neutral fixture identity alongside existing provenance; never rewrite old IDs in place without a verified migration and parity plan. |

## Hard blockers and order

### Blocker 1 — Canonical identity contract
Define application-owned IDs and the canonical entity schema for competition, season, team and fixture. Specify source-link uniqueness, aliases, merge/split history, evidence references and conflict states. Existing Sportmonks IDs must remain available as provider source IDs.

### Blocker 2 — Repository compatibility interface
Provide repository methods that accept canonical IDs and return normalized entity records while preserving existing legacy methods. Add read-only parity tests comparing old Sportmonks-keyed reads with new canonical reads for already imported seasons. No production writes during this phase.

### Blocker 3 — Provider-specific enrichment adapters
Separate canonical team/fixture identity from provider IDs required to fetch historical match data, player availability, lineups and statistics. A canonical team may have more than one verified provider link; selection must be capability- and freshness-aware, not hard-coded to the canonical ID prefix.

### Blocker 4 — Prediction readiness contract
Refactor readiness checks to consume normalized fixture identity and normalized history/profile records. Keep all current quality gates: exact home/away identity, season consistency, completed-match status, score validity, duplicate exclusion and required data coverage. Preserve the current model weights and TVD.

### Blocker 5 — Promotion and write path
Only after Blockers 1–4 pass in shadow mode, replace the Sportmonks-prefix requirement with canonical-target validation and an explicit approved-provider link check. Maintain audit, conflict holds, source provenance, idempotency and rollback.

### Blocker 6 — Future-fixture selection and learning
Ensure a selected stored future fixture resolves to a provider-neutral canonical fixture identity, while every source fixture ID remains traceable. Prediction creation stays user-selection-triggered. Do not make provider discovery itself run predictions.

## Recommended implementation sequence

1. **Schema design ADR:** exact canonical tables/columns, ID generation, alias/merge history, source-link and approval audit contracts.
2. **Team identity candidate keys:** deterministic candidate generation with explicit scope dimensions; unit tests for ambiguous club/national/youth/reserve cases.
3. **Read-only canonical repository facade:** normalized get/list methods and parity reports over current imported Sportmonks catalogue rows.
4. **Provider ID resolver:** resolve a canonical entity to approved source IDs by provider capability and freshness, never by guessing numeric ID equivalence.
5. **Prediction input adapter:** convert provider-specific fixture/history/profile payloads into a stable normalized contract and compare predictions/readiness inputs in shadow mode.
6. **Promotion refactor:** only after parity, allow approved non-Sportmonks source links to target application-owned canonical entities.
7. **Bounded rollout:** one competition and one provider at a time, explicit approvals, data-integrity checks and rollback.

## Required safety invariants

- No provider ID is treated as globally unique or reused as a canonical ID.
- No provider mapping is created from name similarity, shared numeric IDs or season-year overlap alone.
- Canonical entities are not created from provider consensus alone; identity evidence and human approval remain required.
- Existing Sportmonks-backed IDs and prediction history remain readable throughout migration.
- Unresolved competition, season, team or kickoff conflicts block fixture promotion.
- Future fixture collection does not trigger predictions.
- Prediction runs only after a user selects a stored future fixture.
- Layer 1/Layer 2 weights and TVD remain unchanged.
- No database schema/data writes until the schema ADR, compatibility tests and rollback plan are reviewed.

## Source files inspected

- `football_repository.py`
- `sportmonks_catalogue_sync.py`
- `provider_entity_crosswalk.py`
- `competition_registry.py`
- `provider_neutral_identity.py`
- `free_fixture_canonical_promotion.py`
- `prediction_readiness.py`
- `app.py`
- `provider_core.py`
- `provider_config.py`
- `upcoming_fixture_collector.py`
- `provider_data_storage.py`

**Disposition:** the next code change should establish and test the canonical repository contract and read-only compatibility facade. Do not remove the Sportmonks promotion gate until all normalized consumer paths are implemented and verified.
