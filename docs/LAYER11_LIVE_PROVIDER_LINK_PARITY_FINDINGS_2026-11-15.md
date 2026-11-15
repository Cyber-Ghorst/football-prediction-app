# Layer 11 — Live provider-link parity audit findings

**Audit report:** `reports/provider_independent_catalogue/approved_link_parity_latest.json`  
**Audit generated:** 2026-11-15T16:26:21.949943Z  
**Mode:** Read-only; the audit set the CockroachDB transaction to read-only  
**Database writes:** None

## Scope

The committed audit enumerated provider names currently represented in `provider_entity_links` and audited league, season, team and fixture rows. At the time of this snapshot, two provider names were present: OpenScores and Sportmonks.

This is a database-link inventory, not a catalogue coverage report. It does not establish whether providers currently have API access to every competition, whether future-fixture endpoints are available, or whether an identity not represented in the link table is absent from the wider provider catalogue.

## Results

| Provider | Total link rows | Approved-link audit matches | Separate verified links | Reconciled fixture observations | Native identity anchors | Unapproved | Ambiguous | Missing approved/native targets |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| OpenScores | 216 | 0 | 66 | 150 | 0 | 0 | 0 | 0 |
| Sportmonks | 2,010 | 0 | 0 | 0 | 2,010 | 0 | 0 | 0 |
| **Total** | **2,226** | **0** | **66** | **150** | **2,010** | **0** | **0** | **0** |

### OpenScores breakdown

- League links: 3, all 3 have exact verification-ledger status `verified`.
- Season links: 3, all 3 have exact verification-ledger status `verified`.
- Team links: 60, all 60 have exact verification-ledger status `verified`.
- Fixture links: 150, all 150 have a matching provider fixture observation whose reconciliation status is `matched` or `outside_upcoming_window`.
- No OpenScores link was approved through the separate append-only provider-link approval audit in this snapshot.

OpenScores therefore acts here as an observation/reconciliation source. These rows do not authorize OpenScores as a future-fixture discovery source and do not make it a prediction-eligible provider.

### Sportmonks breakdown

- Fixture native identity anchors: 1,911.
- League native identity anchors: 4.
- Season native identity anchors: 7.
- Team native identity anchors: 88.
- All 2,010 native anchors have a corresponding legacy target row.
- No Sportmonks cross-provider approval-audit links were counted.

Sportmonks native anchors represent the legacy repository's own source identity namespace. They are not proof that an independent provider has been mapped to those entities.

## Interpretation

The audit found no orphaned approved/native targets, no ambiguous canonical targets, no unapproved links, and no rejected or review-required verification rows in the two provider sets present.

However, **zero approved cross-provider links** were found. The 66 OpenScores verified links and 150 reconciled fixture observations use their own verification/reconciliation evidence paths; they are not equivalent to human-approved cross-provider identity links. Sportmonks native anchors remain source-native legacy identities.

Consequently, this clean parity result is a data-integrity result, not completion of provider-neutral identity integration. The outstanding work is still to establish reviewed canonical competition, season and team identities; collect source-specific evidence; obtain explicit approval where required; and then implement any controlled promotion only after parity and rollback checks.

## Safeguards

This audit did not:

- create or approve canonical identities;
- add or modify provider links;
- modify catalogue, fixture or statistics rows;
- ingest future fixtures;
- create predictions or change prediction eligibility;
- alter model weights, Layer 1, Layer 2 or TVD.

## Next required checks

1. Re-run this read-only audit after any approved-link migration or identity promotion.
2. Extend provider parity only when a provider has explicit evidence and a supported source link; do not infer links from similar names.
3. Keep OpenScores restricted to observation/reconciliation unless a separate future-fixture capability is independently verified.
4. Keep Sportmonks subscription-limited competitions (including the previously tested Bundesliga, Ligue 1 and World Cup catalogue access) held until authenticated catalogue access is demonstrated.
5. Require exact country/competition/season/team scope and evidence-backed review before any cross-provider approval.
