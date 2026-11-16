# Layer 12 — consolidated official team-scope evidence staging

**Checked:** 2026-11-16  
**Controller run:** [#446 — official scope evidence stage](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43915565223)  
**Source audit:** [#445 — official scope audit](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43915371523)

## Staged review table

<badge color="success">201 records staged</badge>

| Evidence class | Records | Status |
|---|---:|---|
| Highlightly domestic club scope | 96 | Complete 2026/27 standings candidates |
| LiveScoreFootball domestic club scope | 36 | Complete 2026/27 standings candidates |
| Highlightly FIFA World Cup national-team scope | 48 | Official FIFA roster context; provider type field unverified |
| Legacy API-Football records | 21 | Held; not members of official 2026/27 rosters |
| **Total** | **201** | All non-promotable |

The 132 domestic candidates carry senior first-team scope from the official 2026/27 competition rosters. The 48 World Cup candidates carry men's senior national-team scope from the official FIFA World Cup 2026 participant list and the Highlightly participant set observed across 104 match pages. Highlightly's `type=national` detail field was not confirmed; the report explicitly retains this limitation.

## Safety and database effects

The staging script wrote only to `provider_official_team_scope_evidence`, a separate review table.

| Protected data | Change |
|---|---:|
| Provider source rows modified | 0 |
| Provider scope columns modified | 0 |
| Canonical IDs assigned | 0 |
| Provider links created | 0 |
| Fixtures imported | 0 |
| Predictions written | 0 |
| Model weights or TVD changed | 0 |
| Prediction ledger touched | 0 |

Every row has `promotion_allowed=false`. The 21 legacy API-Football records remain held, and no cross-provider team identity is approved by this staging operation.

## Related evidence

- [Layer 12 domestic provider detail and alias review](LAYER12_HIGHLIGHTLY_LIVESCORE_API_NINJAS_IDENTITY_REVIEW_2026-11-16.md)
- [FIFA World Cup 2026 official roster review](LAYER12_FIFA_WORLD_CUP_2026_OFFICIAL_ROSTER_REVIEW_2026-11-16.md)
- [Controller run #438 — API Ninjas scope corroboration write](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43911085721)
- [Controller run #439 — post-write corroboration audit](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43911467932)
- [Controller run #446 — official scope stage report](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43915565223)

## Remaining identity boundary

These 201 rows are evidence records, not canonical mappings. A canonical identity/provider-link writer must remain blocked until each cross-provider identity has an independently supported target, explicit reviewer approval, and a complete per-pair rationale. The World Cup has no second-provider team catalogue in the current audited source set, so its 48 provider IDs remain Highlightly-only.
