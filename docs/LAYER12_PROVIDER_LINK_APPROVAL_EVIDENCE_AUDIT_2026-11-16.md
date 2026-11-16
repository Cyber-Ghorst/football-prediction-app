# Layer 12 — provider-link approval evidence audit (2026-11-16)

## Run and safety

- Read-only controller run: [#447 — provider-link approval evidence audit](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43916184804)
- Report artifact: `prediction-lab-controller-report` (contains `provider-link-approval-evidence-audit.json`)
- Checked at: 2026-11-16T17:14:11.925421+00:00
- `read_only=true`; `database_writes=false`
- 0 canonical IDs assigned, 0 provider links created, 0 fixtures ingested, and prediction ledger untouched.

## Results

| Provider / entity type | Existing links | Exact approval records | Other supporting evidence |
|---|---:|---:|---|
| API-Football / league | 3 | 3 | None required by this audit |
| OpenScores / fixture | 150 | 0 | 150 exact reconciled fixture observations |
| OpenScores / league | 3 | 0 | 3 exact verified-link records |
| OpenScores / season | 3 | 0 | 3 exact verified-link records |
| OpenScores / team | 60 | 0 | 60 exact verified-link records |
| Sportmonks / fixture | 1,911 | 0 | 1,911 provider-native identity anchors |
| Sportmonks / league | 4 | 0 | 4 provider-native identity anchors |
| Sportmonks / season | 7 | 0 | 7 provider-native identity anchors |
| Sportmonks / team | 88 | 0 | 88 provider-native identity anchors |
| **Total** | **2,229** | **3** | **2,166 links have one of the separately reported evidence paths above** |

No link had a link-ID-only approval record with a mismatched tuple or insufficient rationale. No orphan approval records were found.

## Interpretation

The audit deliberately requires the full identity tuple for an approval record: `link_id`, provider, entity type, provider entity ID and canonical entity ID, with a rationale of at least 12 characters.

The 2,166 links with separate supporting evidence are not all equivalent:
- OpenScores fixture links are supported by exact reconciled fixture observations.
- OpenScores league, season and team links have exact verified-link evidence.
- Sportmonks links are namespaced provider-native identity anchors (`sportmonks:<provider_id>`), not cross-provider equivalence claims.

A missing approval row is therefore not automatically evidence that a link is wrong. Conversely, these evidence paths must not be silently converted into cross-provider approval. Any new cross-provider identity link still requires the explicit fail-closed approval process and a recorded rationale.

## Layer 12 disposition

The audit is complete. Existing OpenScores reconciliation evidence and Sportmonks namespaced anchors remain intact. No new cross-provider mappings are authorized by this report. The 201 official team-scope records staged separately remain review-only: 132 domestic senior-team candidates, 48 World Cup candidates with provider team type unverified, and 21 held legacy API-Football rows.

Layer 1, Layer 2, TVD, prediction weights, fixtures, prediction generation and learning/ledger behavior were not changed.
