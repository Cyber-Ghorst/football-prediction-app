# Layer 11 — Romania, Slovakia, Spain and Sweden Priority B identity review

**Queue entries:** `observed_competition_071`, `074`, `084`, `085`, `086`, `087`, `088`, `089`  
**Priority:** B — source-scoped provider records  
**Disposition:** Official competition context supported; provider crosswalks held

## Provider observations

| Queue entry | Competition | Provider | Competition ID | Season ID | Season label | Observations |
|---|---|---|---:|---|---|---:|
| `071` | Superliga | Bzzoiro | `23` | `23::1396` | Superliga 26/27 | 9 |
| `074` | Niké liga | Bzzoiro | `109` | `109::2243` | Superliga 26/27 | 4 |
| `084` | Spanish Copa del Rey | LiveScoreFootball | `3951` | `3951::2026` | 2026 | 5 |
| `085` | Spanish LALIGA | LiveScoreFootball | `740` | `740::2026` | 2026 | 1 |
| `086` | Spanish LALIGA 2 | LiveScoreFootball | `3921` | `3921::2026` | 2026 | 1 |
| `087` | Spanish Liga F | LiveScoreFootball | `20956` | `20956::2026` | 2026 | 9 |
| `088` | Allsvenskan | Bzzoiro | `26` | `26::9` | Allsvenskan 2026 | 4 |
| `089` | Superettan | Bzzoiro | `106` | `106::2182` | Superettan 2026 | 2 |

## Romania — Superliga 2026/27

- The official Superliga schedule lists 16 teams and the 2026/27 fixture programme: https://www.superliga.ro/articole/cunoastem-programul-superligii-pentru-sezonul-20262027-f9b16479
- The official standings distinguish the 30-round regular phase, six-team play-off and ten-team play-out: https://www.superliga.ro/clasament

The Bzzoiro sample contains nine observations and does not verify full roster coverage or season ID `23::1396`.

## Slovakia — Niké liga 2026/27

- The league operator lists the 12 participating clubs: https://www.nikeliga.sk/text/8-ulk
- Official 2026/27 fixture schedule: https://www.nikeliga.sk/clanok/4784-majster-zacne-u-novacika-pozname-program-nike-ligy-2026-2027
- Official game model specifies 22 regular rounds and ten additional rounds in the two six-team groups: https://www.nikeliga.sk/text/56-herny-model

Bzzoiro contributes four observations. The provider season label `Superliga 26/27` does not match the public competition name, so the provider ID and label need explicit review before any mapping.

## Spain — candidate provider aliases

The following LiveScoreFootball records are consistent with Spanish competitions already reviewed under other provider names. They are candidate aliases only:

- **Spanish Copa del Rey:** RFEF's 2026/27 regulations specify 106 clubs: https://rfef.es/sites/default/files/pdf/circulares/102_con_anexos_20250624.pdf
- **Spanish LALIGA:** LALIGA's official 2026/27 standings and 20-club, 38-round structure: https://www.laliga.com/laliga-easports/clasificacion and https://assets.laliga.com/assets/2025/03/24/originals/5408fc235e5b383d670bef19ab1fd196.pdf
- **Spanish LALIGA 2:** LALIGA's official 22-club, 42-round structure and 2026/27 standings: https://assets.laliga.com/assets/2025/03/24/originals/5408fc235e5b383d670bef19ab1fd196.pdf and https://www.laliga.com/laliga-hypermotion/clasificacion
- **Spanish Liga F:** official Liga F 2026/27 16-club announcement and fixture calendar: https://ligaf.es/noticia/los-clubes-de-liga-f-moeve-arrancan-la-temporada-20262027 and https://ligaf.es/noticia/liga-f-moeve-ya-tiene-definido-el-calendario-de-emparejamientos-de-la-temporada-20262027

The generic 2026 season labels and small samples (5, 1, 1 and 9 observations) do not prove that these records match the provider-specific 2026/27 season IDs already indexed. Do not merge or create links based on names alone.

## Sweden — 2026 Allsvenskan and Superettan

- Svenska Fotbollförbundet's official 2026 series composition lists 16 clubs in each division: https://www.svenskfotboll.se/4afe1c/globalassets/svff/dokumentdokumentblock/tavling/arsplaner--seriesammansattningar/2026/faststalld-seriesammansattning-allsvenskan-och-superettan-2026.pdf
- The Allsvenskan schedule confirms round 30: https://www.svenskfotboll.se/nyheter/serier/2026/09/allsvenskans-slutomgangar-spikade
- The Superettan schedule confirms the 2026 season programme: https://www.svenskfotboll.se/nyheter/serier/2025/12/spelordning-for-superettan-2026/

Both divisions are distinct men's competitions, each with 16 clubs and 30 rounds. Bzzoiro's samples are four Allsvenskan observations and two Superettan observations, insufficient for full roster or season-ID verification.

## Decision and safeguards

Keep all provider records source-scoped. Treat the four Spanish LiveScoreFootball rows as candidate aliases of existing Spanish competitions only; no provider crosswalk is approved.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.

Remaining evidence: complete rosters, exact fixture-level comparisons, and verified provider season metadata.