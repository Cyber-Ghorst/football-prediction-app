# Layer 11 — Brazilian Série A and Série B 2026 Priority B identity review

**Queue entries:** `observed_competition_009`, `observed_competition_010`, `observed_competition_011`, `observed_competition_012`  
**Priority:** B — single-provider source records  
**Disposition:** Official competition tiers and 2026 formats supported; provider mappings held

## Provider observations

| Queue entry | Competition | Provider | Competition ID | Season ID | Season label | Raw observations |
|---|---|---|---:|---|---|---:|
| `observed_competition_009` | Brasileirão Serie A | Bzzoiro | `9` | `9::28` | Brasileiro Serie A 2026 | 35 |
| `observed_competition_011` | Brazilian Serie A | LiveScoreFootball | `630` | `630::2026` | 2026 | 6 |
| `observed_competition_012` | Campeonato Brasileiro Série A | football-data.org | `2013` | `2013::2474` | 2026-01-28 | 31 |
| `observed_competition_010` | Brasileirão Serie B | Bzzoiro | `34` | `34::52` | Brasileiro Serie B 2026 | 21 |

The three Série A records have closely related names and calendar-year labels, and are plausible descriptions of the same national top-tier competition. They remain separate source records pending exact fixture-level crosswalk review. Série B is a distinct second-tier competition and must not be merged with Série A.

## Official CBF evidence

### Campeonato Brasileiro Série A

1. The CBF's official 2026 regulations and 38-round basic schedule: https://www.cbf.com.br/futebol-brasileiro/noticias/copa-verde/masculino/cbf-divulga-tabela-detalhada-das-primeiras-rodadas-do-brasileirao-2026
2. CBF explicitly describes the Série A format as 20 clubs and 38 rounds: https://www.cbf.com.br/futebol-brasileiro/noticias/jogosdehoje-copa-brasil-sub20/a/brasileirao-betano-2026-tem-a-maior-media-de-gols-desde-2007
3. Official CBF 2026 Série A table and competition documents: https://www.cbf.com.br/futebol-brasileiro/tabelas/campeonato-brasileiro/serie-a/2026

### Campeonato Brasileiro Série B

1. CBF confirms 20 participating clubs and 38 rounds in the 2026 Série B, with playoff access for positions 3–6: https://www.cbf.com.br/futebol-brasileiro/noticias/selecao-masculina/comunicado-1/brasileirao-serie-b-comeca-neste-fim-de-semana-com-novo-formato
2. Official 2026 Série B regulations and basic schedule: https://www.cbf.com.br/futebol-brasileiro/noticias/undefined/flamengo-x-heips/cbf-divulga-documentos-tecnicos-do-brasileirao-da-serie-b-de-2026
3. Official CBF 2026 Série B table and competition documents: https://www.cbf.com.br/futebol-brasileiro/tabelas/campeonato-brasileiro/serie-b/2026

## Assessment

- Série A: **men's top-tier domestic professional league**, 20 clubs, 38 rounds, 380 regular-season matches.
- Série B: **men's second-tier domestic professional league**, 20 clubs, 38 rounds, 380 regular-season matches; positions 3–6 enter promotion playoffs.
- Série A provider samples: Bzzoiro **35**, LiveScoreFootball **6**, football-data.org **31** observations.
- Série B provider sample: Bzzoiro **21** observations.
- The similar Série A names indicate candidate counterpart records, not an approved crosswalk.
- Provider season labels are compatible with calendar year 2026, but provider season IDs are not proven equivalent.

## Decision and safeguards

Keep all four provider records source-scoped. Keep Série A and Série B distinct. Do not merge the three Série A records until exact fixtures and timezone-normalized kickoffs corroborate them.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.

Next evidence needed: exact cross-provider fixture pairs for Série A, broader team/fixture coverage for Série B, and explicit provider season metadata for all four records.