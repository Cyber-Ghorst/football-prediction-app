# Layer 12 — FIFA World Cup 2026 official participant roster review

**Review date:** 2026-11-16  
**Competition:** FIFA World Cup 2026 (men's senior tournament)  
**Highlightly competition:** `World Cup`, provider competition ID `1635`, season `2026`  
**Disposition:** 48/48 participant names match FIFA's completed official roster and 48 non-promotable national-team scope evidence rows have been staged in the separate official scope review table. No cross-provider identity approval.

## 1. Evidence and provenance

The existing Highlightly season-roster audit examined **104 match pages** and observed **48 unique team IDs** as 2026 World Cup participants (controller run #43760784223, checked 2026-11-15). The audit was read-only and did not write database rows.

FIFA's official qualification article confirms that all 48 places were filled and publishes the full participant list. FIFA separately reported Iraq as the 48th and final qualifier on 1 April 2026.

- [FIFA — all 48 qualified teams (Portuguese official list)](https://www.fifa.com/pt/tournaments/mens/worldcup/canadamexicousa2026/articles/classificados-copa-do-mundo-2026)
- [FIFA — World Cup 2026 line-up complete as Iraq claim final spot](https://inside.fifa.com/organisation/news/world-cup-2026-line-up-complete-as-iraq-bolivia-play-off-fixtures)
- [Highlightly provider roster source — controller run #43760784223](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43760784223)
- [FIFA roster comparison report — controller run #444](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43914509175)
- [Combined official scope audit — controller run #445](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43915371523)
- [Official scope evidence staging — controller run #446](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43915565223)

## 2. Comparison result

| Check | Result |
|---|---:|
| FIFA official teams | 48 |
| Highlightly season participant teams | 48 |
| Unique Highlightly provider IDs | 48 |
| Official roster matches | 48 |
| Unmatched participants | 0 |
| Duplicate provider IDs/names | 0 |
| Explicit official-name variants | 7 |

### Provider IDs and FIFA official names

| Highlightly team ID | Highlightly participant name | FIFA official name | Match basis |
|---:|---|---|---|
| 10145 | Panama | Panama | Exact normalized |
| 10996 | Japan | Japan | Exact normalized |
| 11847 | Senegal | Senegal | Exact normalized |
| 1278135 | Ivory Coast | Côte d'Ivoire | Official-name alias |
| 1280688 | Ghana | Ghana | Exact normalized |
| 1284092 | Congo DR | Congo DR | Exact normalized |
| 1303665 | South Africa | South Africa | Exact normalized |
| 1304516 | Algeria | Algeria | Exact normalized |
| 1305367 | Cape Verde | Cabo Verde | Official-name alias |
| 1318132 | Jordan | Jordan | Exact normalized |
| 1334301 | Iraq | Iraq | Exact normalized |
| 1335152 | Uzbekistan | Uzbekistan | Exact normalized |
| 1336003 | Qatar | Qatar | Exact normalized |
| 13549 | Switzerland | Switzerland | Exact normalized |
| 14400 | Mexico | Mexico | Exact normalized |
| 15251 | South Korea | Korea Republic | Official-name alias |
| 1635 | Belgium | Belgium | Exact normalized |
| 17804 | Australia | Australia | Exact normalized |
| 19506 | Iran | IR Iran | Official-name alias |
| 2026164 | Paraguay | Paraguay | Exact normalized |
| 2027866 | Ecuador | Ecuador | Exact normalized |
| 2029568 | USA | USA | Exact normalized |
| 2031270 | Haiti | Haiti | Exact normalized |
| 20357 | Saudi Arabia | Saudi Arabia | Exact normalized |
| 22059 | Germany | Germany | Exact normalized |
| 22910 | Argentina | Argentina | Exact normalized |
| 23761 | Portugal | Portugal | Exact normalized |
| 24612 | Tunisia | Tunisia | Exact normalized |
| 2486 | France | France | Exact normalized |
| 27165 | Morocco | Morocco | Exact normalized |
| 28016 | Egypt | Egypt | Exact normalized |
| 3337 | Croatia | Croatia | Exact normalized |
| 3977507 | New Zealand | New Zealand | Exact normalized |
| 4705963 | Canada | Canada | Exact normalized |
| 4706814 | Curaçao | Curaçao | Exact normalized |
| 5039 | Sweden | Sweden | Exact normalized |
| 5890 | Brazil | Brazil | Exact normalized |
| 656054 | Czech Republic | Czechia | Official-name alias |
| 660309 | Austria | Austria | Exact normalized |
| 662011 | Turkey | Türkiye | Official-name alias |
| 6741 | Uruguay | Uruguay | Exact normalized |
| 7592 | Colombia | Colombia | Exact normalized |
| 8443 | Spain | Spain | Exact normalized |
| 928374 | Norway | Norway | Exact normalized |
| 9294 | England | England | Exact normalized |
| 943692 | Scotland | Scotland | Exact normalized |
| 947947 | Bosnia & Herzegovina | Bosnia and Herzegovina | Official-name alias |
| 952202 | Netherlands | Netherlands | Exact normalized |

## 3. Provider detail limitation

A separate attempt to resolve the 48 Highlightly IDs through `GET /teams/{id}` failed for all 48 with HTTP errors (controller run #443). No further requests were made to avoid repeated calls against a potentially exhausted or restricted endpoint. Therefore:

- Provider-local `type=national` was **not** confirmed from Highlightly team detail.
- The national-team, men's, senior and national-team-squad scope candidate is based on the official FIFA senior men's World Cup roster plus the teams' observed participation in Highlightly's 2026 World Cup match pages.
- Country is not inferred from team names.
- This evidence does not establish that Highlightly IDs can be linked to IDs from another provider.

The Highlightly API documentation defines the team `type` field as `club` or `national`, but the failed lookup means the value remains unverified for these 48 IDs: [Highlightly team endpoint documentation](https://highlightly.net/football-api/documentation/teams/).

## 4. Disposition

- 48 teams have official FIFA roster matches and 48 national-team scope candidates are staged in `provider_official_team_scope_evidence`.
- All 48 remain `promotion_allowed=false`.
- No canonical IDs assigned; no provider links created; no fixture or prediction data changed.
- LiveScoreFootball's audited catalogue has no World Cup team catalogue, so no second-provider World Cup team IDs are available.
- Cross-provider identity remains held until an independent provider's World Cup team catalogue and provider-local identifiers are obtained, or until a separately authorized identity review resolves the gap.
