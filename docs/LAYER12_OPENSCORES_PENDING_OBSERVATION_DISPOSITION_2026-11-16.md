# Layer 12 — OpenScores pending observation disposition

**Date:** 2026-11-16  
**Disposition:** 150 unresolved OpenScores observations marked `discarded_by_operator`; raw records retained.

## 1. Preflight cohort

The read-only preflight identified 300 OpenScores fixture observations:

| Group | Unlinked observations to discard | Existing fixture-linked observations to retain |
|---|---:|---:|
| Bundesliga 2025/26 | 50 | 50 |
| Ligue 1 2025/26 | 50 | 50 |
| World Cup 2026 | 50 | 50 |
| **Total** | **150** | **150** |

The unresolved cohort was selected by both conditions:
- `canonical_fixture_id IS NULL`
- No matching `provider_entity_links` row with `provider='openscores'`, `entity_type='fixture'` and the observation's provider fixture ID.

The observations' current lifecycle status was `outside_upcoming_window`; it was not used as the cohort selector. This avoided accidentally changing the 150 observations that already had fixture links.

## 2. Executed disposition

Controller run #452 updated exactly 150 rows to `discarded_by_operator`.

- Raw observation rows, provider IDs and raw payloads were retained.
- No fixture-linked observation was updated.
- No provider link was inserted, deleted, approved or modified.
- Discarded rows are excluded from future reconciliation and outside-window relabeling.
- Later OpenScores upserts preserve the terminal `discarded_by_operator` status.

## 3. Post-write verification

| Check | Result |
|---|---:|
| Total raw observations retained | 300 |
| `discarded_by_operator` | 150 |
| Existing fixture-linked observations retained | 150 |
| Unresolved/unlinked observations remaining | 0 |
| OpenScores fixture links retained | 150 |
| OpenScores league links retained | 3 |
| OpenScores season links retained | 3 |
| OpenScores team links retained | 60 |
| Total existing OpenScores links retained | 216 |

The independent provider-link approval evidence audit confirms the 150 existing fixture links still have exact reconciled-fixture evidence. They have no exact approval records; this operation did not approve them. The 66 league/season/team links remain evidence-verified, and no approval records were created.

## 4. Controller and CI evidence

- [Read-only preflight — run #451](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43918873278)
- [Operator disposition — run #452](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43919138168)
- [Post-disposition read-only audit — run #455](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43919497081)
- [Provider-link approval evidence audit — run #457](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43920224827)
- [Implementation PR #576](https://github.com/Cyber-Ghorst/football-prediction-app/pull/576)
- [Post-merge Python CI #3255](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43920060735)

## 5. Protected data

No raw observation deletion, canonical ID assignment, provider-link creation/deletion, fixture import, prediction write, prediction-ledger change, model-weight change or TVD change occurred. The operation changed only the reconciliation status and audit note of the 150 unlinked observations.
