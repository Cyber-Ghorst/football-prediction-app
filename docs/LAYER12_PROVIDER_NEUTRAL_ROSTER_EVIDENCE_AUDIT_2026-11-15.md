# Layer 12 — Provider-neutral season roster evidence audit

**Audit time:** 2026-11-15 20:55 UTC  
**Season scope:** 2026/27 domestic competitions; 2026 FIFA World Cup  
**Controller run:** https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43760784223  
**Report artifact:** `prediction-lab-controller-report` → `provider-season-roster-audit.json`

## Result

The provider-neutral roster collectors returned the following provider-native evidence:

| Provider | Competition | Source season | Teams observed | Evidence method | Completeness |
|---|---|---:|---:|---|---|
| Highlightly | Bundesliga (Germany) | 2026 | 18 | League-season standings | Standings table returned |
| LiveScoreFootball | German Bundesliga (Germany) | 2026 | 18 | 57 season-window fixtures | Participant evidence; held as incomplete |
| Highlightly | Ligue 1 (France) | 2026 | 18 | League-season standings | Standings table returned |
| LiveScoreFootball | French Ligue 1 (France) | 2026 | 18 | 58 season-window fixtures | Participant evidence; held as incomplete |
| Highlightly | World Cup | 2026 | 48 | 104 season matches | All match pages retrieved |
| LiveScoreFootball | World Cup | — | 0 | No international competition in its current catalogue | Not covered |

Highlightly's documented standings endpoint is scoped by `leagueId` and `season`; where a tournament has no standings, the collector falls back to its paginated matches endpoint and extracts explicit `homeTeam` / `awayTeam` IDs. The LiveScoreFootball roster is derived from fixture participants within an explicit 2026-08-01 to 2027-05-31 date window. The LiveScore result is intentionally labelled incomplete even though the catalogue reports 18 clubs and the collector saw 18 unique participants.

## Exact normalized name overlap — review candidates only

The two independent providers' team names were compared after conservative Unicode/case/punctuation normalization. This is candidate evidence, not identity approval.

| Competition | Exact normalized overlap | Remaining provider-specific name candidates |
|---|---:|---:|
| Bundesliga | 12 of 18 | 6 pairs |
| Ligue 1 | 13 of 18 | 5 pairs |

### Bundesliga name candidates requiring independent evidence

| Highlightly name | LiveScoreFootball name |
|---|---|
| 1899 Hoffenheim | TSG Hoffenheim |
| FC Koln | FC Cologne |
| FC Schalke 04 | Schalke 04 |
| FSV Mainz 05 | Mainz |
| Hamburger SV | Hamburg SV |
| Union Berlin | 1. FC Union Berlin |

### Ligue 1 name candidates requiring independent evidence

| Highlightly name | LiveScoreFootball name |
|---|---|
| Auxerre | AJ Auxerre |
| Estac Troyes | Troyes |
| Monaco | AS Monaco |
| Rennes FC | Stade Rennais |
| Stade Brestois 29 | Brest |

These pairs are not automatically linked. Before any approval, the review still needs independent team identity evidence and must verify competition/season context and the team's club/national, gender, age-group and squad scope. Similar names are not sufficient.

## World Cup result

Highlightly returned 48 unique team IDs across 104 season matches, and pagination was complete. LiveScoreFootball's current catalogue has no international competition coverage, so it provides no independent World Cup roster corroboration. The 48 records therefore remain Highlightly-native participant evidence only.

## Safety and write accounting

The audit was strictly read-only:

- CockroachDB touched: **no**
- Canonical league/season/team rows written: **0**
- Provider identity links written: **0**
- Fixtures imported: **0**
- Prediction model changed: **no**
- Prediction ledger touched: **no**

All provider IDs remain namespaced and provider-native. The 12 Bundesliga and 13 Ligue 1 exact-name overlaps, plus the alias candidates above, are review queues only. No Sportmonks ID or catalogue availability is required to use Highlightly or LiveScoreFootball as independent evidence sources.

## Next objective

Collect independent official team-identity evidence for the 11 remaining alias pairs, and separately review the 12 + 13 exact normalized overlaps against competition and squad scope. Only after those reviews should an explicitly approved provider crosswalk be written. Keep World Cup team identities held until a second provider or authoritative official source corroborates them.
