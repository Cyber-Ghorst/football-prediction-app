# StatsBomb Open Data: zero-cost and licence-safety assessment

**Assessment date:** 2026-11-10  
**Decision:** Research-only candidate; not approved for production prediction use  
**Budget constraint:** USD 0; no paid access, licence, hosting or API subscription

## 1. Source and data shape

The official Hudl StatsBomb Open Data repository is:

- https://github.com/hudl/open-data

The repository README describes the shared data as being made available for research projects and genuine interest in football analytics. It describes JSON files for:

- competitions and seasons;
- match metadata and results;
- match event data;
- lineups; and
- StatsBomb 360 freeze-frame data for selected matches.

The source is a curated historical dataset, not a public live-match API. Coverage is limited to the competitions, seasons and matches published in the repository. The presence of a competition does not imply current-season coverage or complete event/360 coverage.

## 2. Licence and permitted-use gate

The repository includes a separate `LICENSE.pdf` and its README links publication attribution requirements. The README says that research, analysis or insights published, shared or distributed using the data must identify StatsBomb as the data source and use the StatsBomb logo from its Media Pack.

The README describes the purpose as research and genuine interest in football analytics. This assessment has **not** established that those terms authorize use in a public, production, monetized or otherwise commercial prediction application. A repository being publicly readable or downloadable is not, by itself, a commercial-use licence.

Before any data is ingested or used by this application, the project owner must review the complete current StatsBomb User Agreement and `LICENSE.pdf`, complete any required registration, and confirm that the agreement permits the exact intended use at zero cost. If permission is unclear, obtain written clarification from StatsBomb. No assumption of commercial rights is made here.

Official references:

- Repository and stated use/attribution terms: https://github.com/hudl/open-data
- Separate licence document: https://github.com/hudl/open-data/blob/master/LICENSE.pdf
- StatsBomb Resource Centre / registration entry point: https://statsbomb.com/resource-centre/
- StatsBomb Media Pack: https://statsbomb.com/media-pack/

## 3. What the data could support if use is authorized

Subject to coverage and event-field availability, an offline research adapter could derive or inspect:

- shot-level features and the supplied StatsBomb xG field;
- shot locations, outcomes and body parts;
- pass, carry, pressure, duel, interception and recovery events;
- lineup and substitution context; and
- selected 360 positional snapshots.

These are event-level research inputs. They are not a substitute for a continuously updated live feed. The repository does not promise a complete 360 freeze frame for every event or match.

## 4. Integration restrictions until approval

Until the licence gate is resolved:

1. Do not add StatsBomb credentials, API clients, automated downloads or scheduled synchronization.
2. Do not commit or redistribute raw StatsBomb match/event files in this repository.
3. Do not feed StatsBomb data into live predictions, player ratings, model training or backtests.
4. Do not display StatsBomb-derived metrics in the public app.
5. Do not treat missing event or 360 data as zero or infer missing xG.
6. Do not change provider priorities, prediction inputs, model weights, TVD rules or tactical recency weighting.

A future prototype, if authorized, should begin as an isolated offline reader for a locally supplied dataset, with source provenance, competition/season/match identity, schema validation, coverage reporting and explicit attribution metadata. Production integration would require a separate approval gate.

## 5. Go/no-go decision

**Current status: NO-GO for application integration.**

The dataset is technically promising and has no stated subscription price, but the intended application-use rights have not been confirmed. Free download access is not enough to satisfy the project's zero-cost and licence-safety requirements.

Proceed only if all of the following are true:

- the current User Agreement and licence are reviewed;
- the intended private/research or public/production use is explicitly permitted;
- any required registration is completed;
- the permitted use has no fee or recurring charge;
- attribution and logo requirements can be met; and
- the selected competitions and seasons provide enough relevant coverage to justify the engineering effort.

If any condition fails or remains ambiguous, leave StatsBomb out of the app and continue with existing providers and other clearly licensed free sources.

## 6. Protected prediction architecture

This assessment is documentation only. It does not authorize a new provider adapter or any model changes. The existing weighted model, TVD logic, provider priorities and 60/40 tactical recency weighting remain unchanged. Missing evidence continues to remain unknown.
