# Layer 11 — A-League Men 2026/27 Priority B identity review

**Queue entry:** `observed_competition_004`  
**Priority:** B — single-provider identity  
**Disposition:** Competition and season supported; provider mapping held because roster evidence and country scope are incomplete

## Provider observation

| Provider | Competition ID | Season ID | Season label | Sample |
|---|---|---|---|---:|
| Bzzoiro | `104` | `104::2144` | A-League 26/27 | 6 raw observations |

Only Bzzoiro contributes this competition/country identity in the approved intake snapshot. Six observations are insufficient to verify full roster coverage or provider season-ID semantics.

## Official A-Leagues evidence

1. The official A-League Men 2026/27 Competition Rules Summary specifies **12 clubs**, **26 matches per club**, and **156 regular-season matches**: https://aleagues.com.au/more/official-documents/
2. The official 2026/27 season guide states that the season begins on 16 October 2026 and confirms Western United is no longer participating: https://aleagues.com.au/news/aleague-men-ultimate-season-guide-news/
3. The official 2026/27 fixture release confirms 28 matchweeks and 26 matches per club: https://aleagues.com.au/news/aleague-men-2026-2027-fixture-list-revealed-key-dates-fixture-information/

## Geographic and roster scope

The official 2026/27 competition includes 12 clubs. Its club list includes:

- Auckland FC — New Zealand
- Wellington Phoenix — New Zealand
- Ten other clubs based in Australia

Therefore, the competition is not Australia-only. The identity queue currently records `Australia` as the country, which is incomplete for the full competition scope. This requires a formal cross-border identity convention; do not silently treat New Zealand clubs as Australian clubs or assign an Australia-only canonical country key.

## Assessment

- Competition type: **men's top-tier professional club league**, officially corroborated.
- Season: **2026/27**, officially corroborated.
- Official scope: **12 clubs, 26 matches per club, 156 regular-season matches**.
- Geographic scope: **Australia and New Zealand**.
- Provider sample: **6 Bzzoiro observations only**.
- Independent provider corroboration: **not available in the intake snapshot**.
- Provider season-ID equivalence: **not independently verified**.
- Queue country field: **Australia-only and incomplete**.

## Decision and safeguards

Keep Bzzoiro competition `104` and season `104::2144` source-scoped.

- Do not create canonical competition, season or team mappings.
- Do not create provider links or enable fixture ingestion.
- Do not alter the queue country scope until the cross-border identity convention is established.
- Do not change prediction eligibility.

Next evidence needed: a broader Bzzoiro roster/fixture sample, an independent provider source, and a formal representation for Australia/New Zealand competition scope.