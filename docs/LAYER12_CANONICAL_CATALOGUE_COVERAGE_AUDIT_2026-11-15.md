# Layer 12 — canonical catalogue coverage audit

> **Disposition update (2026-11-16):** The 150 unresolved OpenScores observations described in this historical report were subsequently marked `discarded_by_operator` per the user's instruction. Raw observations were retained; 150 existing fixture-linked observations and 66 league/season/team links were left unchanged. See [the disposition report](LAYER12_OPENSCORES_PENDING_OBSERVATION_DISPOSITION_2026-11-16.md) for the verified final state.
 (2026-11-15)

## Scope and safety

This is a read-only evidence report supporting the OpenScores-to-canonical reconciliation work. It does not approve provider mappings or authorize fixture ingestion. The OpenScores reconciliation remains restricted to pre-existing verified links. No database rows, canonical fixtures, prediction-model configuration, or prediction-ledger records were changed by these audits.

## OpenScores reconciliation result

Workflow: [reconciliation run](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43754310967)

- 300 staged OpenScores observations checked.
- 150 reported as matched and 150 remain pending entity mapping.
- No canonical fixture non-matches, ambiguous fixture matches, or crosswalk conflicts were reported.
- 0 entity links inserted, 0 verified links created, and 0 canonical fixtures imported or modified.
- Prediction model unchanged; prediction ledger untouched.
- Pending groups include 50 observations each for Germany's Bundesliga (OpenScores league/season 4/4), France's Ligue 1 (6/6), and the World Cup (7/7).

The controller's successful workflow status means the audit/reconciliation job ran successfully; the reconciliation data status is **partial**. The 150 pending observations remain blocked until auditable league, season, and team crosswalk evidence is available.

## Sportmonks account catalogue access

Workflow: [Sportmonks catalogue audit](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43755289556)

The authenticated account catalogue returned five leagues and 15 season records:

| Sportmonks league ID | Competition | Country | Seasons returned |
|---|---|---|---:|
| 8 | Premier League | England | 3 |
| 24 | FA Cup | England | 3 |
| 384 | Serie A | Italy | 3 |
| 564 | La Liga | Spain | 3 |
| 567 | La Liga 2 | Spain | 3 |

The three pending competitions were not visible in the account catalogue. Germany and France country searches returned successfully but no matching target league. Direct probes for Sportmonks league IDs 82 (Bundesliga), 301 (Ligue 1), and 732 (World Cup) returned the provider's “no results or no subscription access” response. The audit therefore cannot distinguish provider-wide absence from account entitlement restrictions. No Sportmonks IDs are approved for these targets.

## Alternative provider catalogue evidence

Workflow: [Highlightly and LiveScoreFootball catalogue audit](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43755356267)

### Highlightly

- Authenticated catalogue responded with 913 competitions, 169 countries, and 4,745 season records; the reported plan was BASIC and stated all data was available under the current plan.
- Exact country-qualified catalogue entries were found:
  - Germany Bundesliga: competition ID 67162, seasons include 2025 and 2026.
  - France Ligue 1: competition ID 52695, seasons include 2025 and 2026.
  - World Cup: competition ID 1635, seasons include 2022 and 2026.
- Other competitions share the names “Bundesliga” or “Ligue 1” in other countries. Country qualification is mandatory; name-only matching is unsafe.

### LiveScoreFootball

- Catalogue responded with 35/35 active, data-backed competitions and fresh metadata; 3,271 stored matches and 42 standings groups were reported.
- German Bundesliga is present as `ger.1` (57 match records, 18 clubs).
- French Ligue 1 is present as `fra.1` (58 match records, 18 clubs).
- The audited catalogue reports zero active international competitions, so it does not provide World Cup coverage in this snapshot.
- Its competition catalogue does not expose the same season identifiers as the OpenScores/Sportmonks crosswalk, so these records are corroborating catalogue evidence only, not approved season/team mappings.

## Decisions and next safe steps

1. Keep the 150 pending OpenScores observations on hold.
2. Do not create Sportmonks links for Bundesliga, Ligue 1, or World Cup while the account cannot return those canonical league/season/team records.
3. Treat Highlightly's country-qualified competition and season entries, and LiveScoreFootball's club-competition catalogue entries, as candidate evidence only. Before any cross-provider link write, collect season-scoped team rosters and stable provider IDs, verify the competition/season identity, and reconcile ordered home/away teams plus kickoff within the existing five-minute tolerance.
4. World Cup remains blocked until a canonical international competition and season roster can be sourced and verified.
5. Preserve the fail-closed approval gate: no mapping write without explicit reviewer approval and a recorded rationale.

No changes to Layer 1, Layer 2, TVD, prediction weights, prediction generation, or learning/ledger behavior are proposed by this report.
