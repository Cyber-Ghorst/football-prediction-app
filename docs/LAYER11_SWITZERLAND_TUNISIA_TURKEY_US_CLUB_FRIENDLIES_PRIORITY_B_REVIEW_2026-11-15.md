# Layer 11 — Switzerland, Tunisia, Turkey and United States Priority B review

**Queue entries:** `observed_competition_090`, `091`, `092`, `093`, `095`, `096`, `097`  
**Priority:** B — source-scoped provider records  
**Disposition:** Official competition identities supported to varying degrees; generic friendly category is not a competition identity

## Provider observations

| Queue entry | Competition | Provider | Competition ID | Season ID | Season label | Observations |
|---|---|---|---:|---|---|---:|
| `090` | Super League | Bzzoiro | `15` | `15::1395` | Super League 26/27 | 3 |
| `091` | Tunisian Ligue Professionnelle 1 | Bzzoiro | `47` | `47::1634` | Ligue 1 26/27 | 12 |
| `092` | Trendyol 1. Lig | Bzzoiro | `107` | `107::2201` | 1. Lig 26/27 | 7 |
| `093` | Trendyol Super Lig | Bzzoiro | `11` | `11::1539` | Super Lig 26/27 | 4 |
| `095` | NWSL | Bzzoiro | `72` | `72::1540` | National Womens Soccer League 2026 | 6 |
| `096` | USL Championship | Bzzoiro | `57` | `57::1435` | USL Championship 2026 | 6 |
| `097` | Club Friendlies | Bzzoiro | `79` | `79::1552` | Club Friendly Games 2026 | 77 |

## Switzerland — Brack Super League 2026/27

The official Swiss Football League match centre lists the 2026/27 Brack Super League and its 12 participating clubs:

- Official season match centre and club group: https://matchcenter-sfl.football.ch/default.aspx?a=mgr&ln=11011&lng=1&ls=25694&oid=2&s=2027&sg=0
- Official SFL competition hub: https://matchcenter-sfl.football.ch/

Bzzoiro's three observations do not establish full roster coverage, the complete season format or provider season-ID semantics. Keep the row source-scoped.

## Tunisia — Ligue I Professionnelle

The Tunisian Football Federation's published regulations identify Ligue I Professionnelle as the country's top professional division and specify a 16-club single group for 2025/26:

- Official FTF regulations: https://www.ftf.org.tn/fr/wp-content/uploads/2025/08/REGLEMENTS-GENERAUX-Juillet2025-1.pdf

A reliable official 2026/27 format announcement was not located in this review. Do not assume the 2025/26 format carried forward without confirmation. Bzzoiro's 12 observations and the season label alone do not prove the 2026/27 format or provider season ID.

## Turkey — Trendyol 1. Lig and Süper Lig 2026/27

### Trendyol 1. Lig

- Official TFF 2026/27 schedule and standings show 38 rounds and 20 clubs: https://www.tff.org/default.aspx?pageID=142
- TFF's official professional-league calendar announcement: https://www.tff.org/Default.aspx?ftxtId=50517&pageId=200

### Trendyol Süper Lig

- Official TFF 2026/27 competition regulations specify 18 clubs and a double round-robin format: https://www.tff.org/Resources/TFF/Documents/STATULER/2026-2027/2026-2027-sezonu-super-lig-musabakalari-statusu.pdf
- Official TFF 2026/27 fixture list and standings: https://www.tff.org/Default.aspx?hafta=27&macId=318081&pageId=198

The two Turkish divisions are distinct tiers. Bzzoiro's seven 1. Lig and four Süper Lig observations are insufficient for full roster/fixture verification or provider season-ID validation.

## United States — NWSL and USL Championship 2026

### NWSL

The official 2026 NWSL Competition Rules list 16 clubs, a 30-game regular season per club and an eight-team single-elimination playoff:

- Official NWSL 2026 Competition Rules: https://images.nwslsoccer.com/image/private/t_q-good/prd/tstudhfledlk7z8ygtzd.pdf

### USL Championship

The official 2026 competition-format announcement lists 25 clubs across two conferences, a 30-game regular season per club and the top eight in each conference advancing to playoffs:

- Official USL Championship format: https://www.uslchampionship.com/news_article/show/1351433

Both Bzzoiro records have only six observations; full club coverage and provider season-ID semantics remain unverified.

## Club Friendlies — reclassification required

`Club Friendlies` is not one league or cup. It is a broad event category for exhibition matches between clubs. It has no shared competition table, league membership or champion. The 77 raw observations may represent many unrelated fixtures.

- Preserve the Bzzoiro classification as a provider event-type label.
- Do not create a canonical competition or season for `79::1552`.
- Individual friendly fixtures should be identified and classified at fixture level, with the teams, date and match type retained.

## Decision and safeguards

Keep all actual league records source-scoped. Tunisia's 2026/27 format remains unverified. Treat Club Friendlies as an event category, not a canonical competition.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.

Remaining evidence: explicit provider season metadata, broader roster and fixture samples, and exact fixture-level comparisons. For Club Friendlies, classify individual matches instead of promoting the aggregate category to a league identity.