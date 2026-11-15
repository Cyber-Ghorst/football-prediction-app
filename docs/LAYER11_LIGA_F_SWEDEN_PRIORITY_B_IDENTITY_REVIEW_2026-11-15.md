# Layer 11 — Spanish Liga F and Swedish league Priority B review

**Queue entries:** `observed_competition_087`, `088`, `089`  
**Priority:** B — source-scoped provider records  
**Disposition:** Official competition context supported; provider crosswalk held

## Provider observations

| Queue entry | Competition | Provider | Competition ID | Season ID | Season label | Observations |
|---|---|---|---:|---|---|---:|
| `087` | Spanish Liga F | LiveScoreFootball | `20956` | `20956::2026` | 2026 | 9 |
| `088` | Allsvenskan | Bzzoiro | `26` | `26::9` | Allsvenskan 2026 | 4 |
| `089` | Superettan | Bzzoiro | `106` | `106::2182` | Superettan 2026 | 2 |

## Spain — Liga F candidate alias

Liga F's official 2026/27 sources identify 16 clubs and publish the full season calendar:

- Official 16-club season announcement: https://ligaf.es/noticia/los-clubes-de-liga-f-moeve-arrancan-la-temporada-20262027
- Official 2026/27 fixture calendar: https://ligaf.es/noticia/liga-f-moeve-ya-tiene-definido-el-calendario-de-emparejamientos-de-la-temporada-20262027
- RFEF women's football season calendar: https://rfef.es/es/noticias/repasa-las-fechas-clave-del-futbol-femenino-para-la-temporada-202627

Sixteen clubs in a home-and-away format produce 30 rounds and 240 matches. The LiveScoreFootball record is a plausible counterpart to the existing Bzzoiro Liga F record, but its generic 2026 season label and nine observations do not establish exact provider season equivalence. Do not link it automatically.

## Sweden — Allsvenskan and Superettan 2026

- Svenska Fotbollförbundet's official 2026 series composition lists 16 clubs in each division: https://www.svenskfotboll.se/4afe1c/globalassets/svff/dokumentdokumentblock/tavling/arsplaner--seriesammansattningar/2026/faststalld-seriesammansattning-allsvenskan-och-superettan-2026.pdf
- The Allsvenskan official schedule confirms round 30: https://www.svenskfotboll.se/nyheter/serier/2026/09/allsvenskans-slutomgangar-spikade
- The Superettan official schedule gives the 2026 season programme: https://www.svenskfotboll.se/nyheter/serier/2025/12/spelordning-for-superettan-2026/

Both are distinct men's competitions, each with 16 clubs and 30 rounds (240 matches). Bzzoiro contributes four Allsvenskan observations and two Superettan observations; these samples are too small to verify complete roster coverage or provider season-ID semantics.

## Decision and safeguards

Keep the LiveScoreFootball Liga F record as a candidate alias only. Keep Allsvenskan and Superettan separate as Sweden's first and second tiers.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.

Remaining evidence: larger provider samples, explicit season metadata and exact fixture comparisons before any cross-provider mapping.