# Competition identity review queue

This queue stages the 97 approved observed competition records for manual identity review. It is ordered for efficient review, not a statement of canonical identity.

## Priority counts

- **A — multi-provider with country context:** 10
- **B — single-provider with country context:** 87
- **C — country missing/ambiguous:** 0

## Required review gates

1. Verify that the competition exists and establish its type (league, cup, tournament, etc.).
2. Verify country/territory from evidence; do not infer it from the competition name.
3. Verify gender, age group, division/tier and senior/reserve scope where relevant.
4. Verify season boundaries and provider-specific season IDs independently.
5. Compare cross-provider names only after country and type context are established.
6. Record provenance for each decision; do not merge similar names without evidence.

## Safety boundary

This is a triage queue only. All entries remain unverified. No canonical identities, provider links, seasons, teams, fixtures, or prediction eligibility are created or approved. Future-fixture routes remain disabled pending their separate gates.

Machine-readable details: [identity_review_queue.json](../reports/provider_independent_catalogue/identity_review_queue.json).
