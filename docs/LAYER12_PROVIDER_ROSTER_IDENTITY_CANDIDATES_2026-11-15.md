# Layer 12 provider roster identity candidate audit — 15 November 2026

## Scope and evidence

This is a read-only comparison of:
- Highlightly league-season standings for Bundesliga (Germany), Ligue 1 (France), and match participants for the 2026 World Cup.
- LiveScoreFootball fixture participants observed in the explicit 2026/27 season window for German Bundesliga (`ger.1`) and French Ligue 1 (`fra.1`).

The audit run completed successfully through Prediction Lab Controller run `43761369869`. The JSON report is retained as a GitHub Actions artifact named `prediction-lab-controller-report` (run ID above).

## Roster collection

| Competition | Highlightly | LiveScoreFootball |
|---|---:|---:|
| Bundesliga (Germany) | 18 standings teams | 18 observed teams |
| Ligue 1 (France) | 18 standings teams | 18 observed teams |
| World Cup 2026 | 48 match participants | No international competition in the audited LiveScore catalogue |

LiveScoreFootball's team set is derived from fixture participants and is therefore observation evidence, not an independently certified complete roster. The World Cup list is likewise a participant set, not a canonical national-team catalogue.

## Exact normalized-name candidates

Only unique exact normalized-name matches were emitted. Diacritics, case, punctuation and whitespace are normalized; no aliases or fuzzy matching are applied. Candidates are review suggestions only.

### Bundesliga — 12 candidates

| Highlightly team | Highlightly ID | LiveScoreFootball team | LiveScore ID |
|---|---:|---|---:|
| Bayer Leverkusen | 143752 | Bayer Leverkusen | 131 |
| Bayern Munich | 134391 | Bayern Munich | 132 |
| Borussia Dortmund | 141199 | Borussia Dortmund | 124 |
| Borussia Mönchengladbach | 139497 | Borussia Mönchengladbach | 268 |
| Eintracht Frankfurt | 144603 | Eintracht Frankfurt | 125 |
| FC Augsburg | 145454 | FC Augsburg | 3841 |
| RB Leipzig | 148007 | RB Leipzig | 11420 |
| SC Freiburg | 136944 | SC Freiburg | 126 |
| SC Paderborn 07 | 158219 | SC Paderborn 07 | 3307 |
| SV Elversberg | 1413444 | SV Elversberg | 10388 |
| VfB Stuttgart | 147156 | VfB Stuttgart | 134 |
| Werder Bremen | 138646 | Werder Bremen | 137 |

Unmatched Highlightly names: FSV Mainz 05, 1899 Hoffenheim, FC Schalke 04, Hamburger SV, Union Berlin, FC Koln.

Unmatched LiveScoreFootball names: Mainz, TSG Hoffenheim, Schalke 04, Hamburg SV, 1. FC Union Berlin, FC Cologne.

### Ligue 1 — 13 candidates

| Highlightly team | Highlightly ID | LiveScoreFootball team | LiveScore ID |
|---|---:|---|---:|
| Angers | 66311 | Angers | 7868 |
| LE Havre AC | 95245 | Le Havre AC | 3236 |
| Le Mans | 1105382 | Le Mans | 2697 |
| Lens | 99500 | Lens | 175 |
| Lille | 68013 | Lille | 166 |
| Lorient | 83331 | Lorient | 273 |
| Lyon | 68864 | Lyon | 167 |
| Marseille | 69715 | Marseille | 176 |
| Nice | 72268 | Nice | 2502 |
| Paris FC | 97798 | Paris FC | 6851 |
| Paris Saint Germain | 73119 | Paris Saint-Germain | 160 |
| Strasbourg | 81629 | Strasbourg | 180 |
| Toulouse | 82480 | Toulouse | 179 |

Unmatched Highlightly names: Monaco, Rennes FC, Stade Brestois 29, Auxerre, Estac Troyes.

Unmatched LiveScoreFootball names: AS Monaco, Stade Rennais, Brest, AJ Auxerre, Troyes.

## Result and safety

- 25 unique exact normalized-name candidate pairs: 12 Bundesliga, 13 Ligue 1.
- 0 duplicate-name ambiguities in those candidate pairs.
- 22 unmatched roster entries across the two domestic competitions (11 per competition); these are held rather than alias-matched.
- No cross-provider team identity is verified by this report.
- No `provider_entity_links` were created.
- No canonical league, season, team or fixture rows were written or changed.
- No fixtures were imported.
- Prediction model, Layer 1, Layer 2, TVD and prediction ledger were untouched.

## Required next evidence before approval

1. Review each of the 25 exact-name pairs against provider-native team detail evidence and the correct country/competition/season context.
2. Resolve the 22 unmatched names only through authoritative provider metadata or independent corroboration; do not promote spelling similarities to links.
3. Obtain an independently supported international competition/team catalogue for the World Cup participant set.
4. Record reviewer, rationale and source evidence for every approved mapping. Only then use the explicit fail-closed mapping writer.

These candidates are not sufficient authorization to create mappings. They must remain namespaced provider identities until reviewed and explicitly approved.
