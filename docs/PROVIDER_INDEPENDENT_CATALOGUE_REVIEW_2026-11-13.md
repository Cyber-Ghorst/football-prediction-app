# Provider-independent competition catalogue review — 13 November 2026

## Purpose

This review advances the competition catalogue toward a provider-neutral design. Provider IDs remain namespaced to their source. No provider, including Sportmonks, is treated as the owner of canonical identity.

This is a documentation/review artifact based on the successful live read-only crosswalk report generated at **2026-11-13 15:11:30 UTC**:

- `reports/free_fixture_crosswalk_audit/latest.json`
- Workflow: [Read-only live provider crosswalk audit](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43449640690)

It does not create or approve canonical records, provider links, seasons, teams, fixtures or predictions. It does not write to CockroachDB.

## Live provider evidence

Six independent providers returned usable observations:

| Provider | Observations | Competitions | Seasons | Teams |
|---|---:|---:|---:|---:|
| Bzzoiro | 1,349 | 51 | 48 | 762 |
| Football-Data.org | 26 | 1 | 1 | 18 |
| Highlightly | 3,715 | 205 | 205 | 2,703 |
| LiveScore Football | 132 | 13 | 13 | 88 |
| OpenFootball | 8,748 | 8 | 8 | 0 |
| OpenLigaDB | 14,733 | 38 | 38 | 456 |
| **Total** | **28,703** | — | — | — |

API Ninjas and Open-Matchday were skipped in this run. A skipped provider is not evidence that it lacks coverage; its current audit status simply supplied no usable observation set.

The provider-independent grouping found **269 competition/country identities**:
- 18 exact normalized competition-name/country groups represented by at least two providers.
- 251 groups represented by one provider.
- 27 source records lacked country context and were not used to corroborate an identity.
- 0 provider links created and 0 automatic mapping approvals.

These are source-observation counts, not approved canonical competition counts. The audit report does not provide fresh live row counts for the canonical league, season and team tables; those counts must not be inferred from the source catalogue totals.

## Highest-confidence identity and season evidence

| Competition | Country | Provider competition IDs | Observation evidence | Season evidence | Review status |
|---|---|---|---:|---|---|
| Premier League | England | OpenFootball `en.1`; OpenLigaDB `5996` | 1,140 + 1,140 | Both identify 2026 start year; labels `2026-27` and `2026` | Strongest initial identity/season candidate |
| Bundesliga | Germany | OpenFootball `de.1`; OpenLigaDB `4937`; Bzzoiro `5` | 918 + 918 + 3 | OpenFootball and OpenLigaDB both identify 2026; Bzzoiro label `26/27` is not parsed to a four-digit year | Strong identity and two-source season candidate |
| MLS | United States | Bzzoiro `18`; LiveScore Football `770` | 6 + 6 | Both identify 2026 | Corroborated, low-volume candidate |
| Copa Colombia | Colombia | Bzzoiro `81`; Highlightly `205875` | 6 + 5 | Both identify 2026 | Corroborated, low-volume candidate |
| USL Championship | United States | Bzzoiro `57`; Highlightly `217789` | 6 + 5 | Both identify 2026 | Corroborated, low-volume candidate |

For the first two rows, provider season identities are:
- Premier League: OpenFootball `en.1::2026-27`; OpenLigaDB `5996::2026`.
- Bundesliga: OpenFootball `de.1::2026-27`; OpenLigaDB `4937::2026`; Bzzoiro `5::1091`.

Matching season start years are supporting evidence only. They do not prove that provider season IDs are interchangeable or that season boundaries, stages and competition formats are identical.

## Remaining multi-provider review queue

| Competition | Country | Provider competition IDs | Observation counts | Season evidence |
|---|---|---|---:|---|
| Girabola | Angola | Bzzoiro `98`; Highlightly `338631` | 6 + 2 | Insufficient parsed cross-provider year evidence |
| League One | England | Bzzoiro `86`; Highlightly `35675` | 39 + 36 | Insufficient parsed cross-provider year evidence |
| League Two | England | Bzzoiro `87`; Highlightly `36526` | 36 + 35 | Insufficient parsed cross-provider year evidence |
| National League | England | Bzzoiro `91`; Highlightly `37377` | 39 + 36 | Insufficient parsed cross-provider year evidence |
| Coupe de France | France | Bzzoiro `44`; Highlightly `56950` | 259 + 225 | Insufficient parsed cross-provider year evidence |
| Ligue 1 | France | Bzzoiro `6`; OpenFootball `fr.1` | 3 + 918 | Insufficient parsed cross-provider year evidence |
| 2. Bundesliga | Germany | Bzzoiro `94`; OpenLigaDB `4938` | 6 + 918 | Insufficient parsed cross-provider year evidence |
| Eerste Divisie | Netherlands | Bzzoiro `108`; Highlightly `76523` | 51 + 23 | Insufficient parsed cross-provider year evidence |
| Liga Portugal 2 | Portugal | Bzzoiro `88`; Highlightly `81629` | 27 + 10 | Insufficient parsed cross-provider year evidence |
| Saudi Pro League | Saudi Arabia | Bzzoiro `17`; LiveScore Football `21231` | 30 + 3 | Insufficient parsed cross-provider year evidence |
| Copa del Rey | Spain | Bzzoiro `41`; Highlightly `122477` | 21 + 15 | Insufficient parsed cross-provider year evidence |
| La Liga | Spain | Bzzoiro `3`; OpenFootball `es.1` | 3 + 1,140 | Insufficient parsed cross-provider year evidence |
| Segunda División | Spain | Bzzoiro `38`; Highlightly `120775` | 36 + 27 | Insufficient parsed cross-provider year evidence |

The report supplies no competition-type evidence for the 18 groups. Before a competition is accepted into the canonical catalogue, its identity, country, competition type (league/cup/etc.), gender/age scope where applicable, active status and season structure need verification. In particular, a cup must not be conflated with a league simply because its name matches across providers.

## Provider-neutral identity rules to implement

1. **Canonical identity is application-owned.** Generate a stable canonical competition key independently of any provider's numeric ID, slug or account entitlement.
2. **Provider IDs are namespaced.** Store the provider name, entity type and source ID together. Never equate IDs across providers.
3. **Country is mandatory for automatic candidate grouping.** Country aliases may be normalized, but ambiguous or absent country context must remain unresolved.
4. **Competition type is a required review attribute.** Distinguish league, domestic cup, continental competition, international tournament, youth, women's and reserve competitions when evidence supports those distinctions.
5. **Seasons are children of a verified competition.** Store provider season IDs separately. Validate parent competition, season label/date range, stages and active status before linking a season.
6. **Teams are scoped by identity, not name alone.** Require country and competition/club context where needed; preserve separate men's/women's, senior/youth and reserve entities.
7. **Consensus proposes; it does not approve.** Two or more providers create a review candidate, never an automatic database write. Conflicts and low-volume corroboration remain visible.
8. **Fixture capability is a separate provider capability.** An observation of a competition or historical match does not prove that a provider exposes scheduled future fixtures. Future-fixture activation requires a dedicated endpoint test, date-window coverage, timezone validation, freshness checks, licence review and repeatable monitoring.
9. **No single provider is the canonical authority.** Sportmonks may remain one source adapter while it is useful, but its catalogue IDs must not define canonical IDs or be required for a competition to exist in the app.

## Recommended implementation sequence

1. Add provider-neutral canonical competition and season identity structures alongside the existing source-link model; do not repurpose Sportmonks IDs as canonical keys.
2. Add read-only validation for the five strongest candidates above, beginning with Premier League and Bundesliga. Verify competition type and current season from independent provider catalogues and authoritative competition sources.
3. Extend the audit to report live canonical table counts and exact conflicts without writing.
4. Generate proposed source-to-canonical links only after a canonical identity has been reviewed and created through an explicitly approved migration.
5. Add provider-neutral team and fixture identity only after competition and season parent relationships are verified.
6. Test future-fixture endpoint capability separately for every provider before enabling it in discovery or promotion.
7. Keep fixture promotion, prediction inputs and the prediction ledger disabled for unapproved or unresolved identities.

## Safety state at review time

- Read-only audit completed successfully.
- Six providers supplied usable observations; two configured providers were skipped.
- Provider links created: **0**.
- Automatic mapping approvals: **0**.
- Canonical rows created by the audit: **0**.
- Canonical fixture writes: **0**.
- Prediction-ledger writes: **0**.
- No provider mappings or canonical rows were changed by this review.

## Source

- [Latest live crosswalk audit report](../reports/free_fixture_crosswalk_audit/latest.json)
- [Workflow run 43449640690](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43449640690)
- Existing implementation: `provider_independent_competition_catalogue.py`
- Existing review/promotion safeguards: `provider_entity_crosswalk.py`, `free_fixture_canonical_promotion.py`, and `docs/FREE_FIXTURE_CANONICAL_PROMOTION.md`
