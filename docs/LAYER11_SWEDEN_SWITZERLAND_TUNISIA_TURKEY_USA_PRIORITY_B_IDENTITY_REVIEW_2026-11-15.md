# Layer 11 — Sweden, Switzerland, Tunisia, Turkey and North American leagues Priority B identity review

**Queue entries:** `observed_competition_087`–`observed_competition_093`, `observed_competition_095`–`observed_competition_097`  
**Priority:** B — source-scoped provider records  
**Disposition:** Official competition scope supported; generic friendlies require taxonomy reclassification

## Provider observations

| Queue entry | Competition | Provider | Competition ID | Season ID | Raw observations |
|---|---|---|---:|---|---:|
| `observed_competition_087` | Spanish Liga F | LiveScoreFootball | `20956` | `20956::2026` | 9 |
| `observed_competition_088` | Allsvenskan | Bzzoiro | `26` | `26::9` | 4 |
| `observed_competition_089` | Superettan | Bzzoiro | `106` | `106::2182` | 2 |
| `observed_competition_090` | Swiss Super League | Bzzoiro | `15` | `15::1395` | 3 |
| `observed_competition_091` | Tunisian Ligue Professionnelle 1 | Bzzoiro | `47` | `47::1634` | 12 |
| `observed_competition_092` | Trendyol 1. Lig | Bzzoiro | `107` | `107::2201` | 7 |
| `observed_competition_093` | Trendyol Super Lig | Bzzoiro | `11` | `11::1539` | 4 |
| `observed_competition_095` | NWSL | Bzzoiro | `72` | `72::1540` | 6 |
| `observed_competition_096` | USL Championship | Bzzoiro | `57` | `57::1435` | 6 |
| `observed_competition_097` | Club Friendlies | Bzzoiro | `79` | `79::1552` | 77 |

## Sweden — Allsvenskan and Superettan

- The official Swedish FA 2026 series composition lists **16 clubs in Allsvenskan and 16 in Superettan**: https://www.svenskfotboll.se/4afe1c/globalassets/svff/dokumentdokumentblock/tavling/arsplaner--seriesammansattningar/2026/faststalld-seriesammansattning-allsvenskan-och-superettan-2026.pdf
- Allsvenskan's official page confirms 16 clubs and 30 rounds: https://allsvenskan.se/om-oss/
- Superettan's official fixture release covers rounds 27–30 and confirms a 30-round season: https://superettan.se/nyheter/sa-spelas-omgang-27-30-av-superettan/

## Switzerland — Brack Super League

- Swiss FA regulations specify **12 Super League clubs**: https://org.football.ch/portaldata/28/Resources/dokumente/de/02_wettspielreglement_und_spielregeln/2.1._Wettspielreglement_Dezember_2025.pdf
- The official Swiss Football League match center lists the 12 clubs and 2026/27 competition phase: https://matchcenter-sfl.football.ch/default.aspx?a=mgr&ln=11011&lng=1&ls=25694&oid=2&s=2027&sg=0

## Tunisia — Ligue Professionnelle 1

- FTF regulations specify Ligue I Professionnelle as a single-table, 16-club home-and-away championship: https://www.ftf.org.tn/fr/wp-content/uploads/2025/08/REGLEMENTS-GENERAUX-Juillet2025-1.pdf
- FTF's official 2026/27 season notices: https://www.ftf.org.tn/fr/2026/07/

## Turkey — Trendyol 1. Lig and Süper Lig

- TFF's 2026/27 1. Lig regulations specify **20 clubs** in a double round-robin: https://www.tff.org/Resources/TFF/Documents/STATULER/2026-2027/2026-2027-sezonu-tff-1-lig-musabakalari-statusu.pdf
- TFF's official 2026/27 fixture release confirms 20 clubs and season dates: https://www.tff.org/default.aspx?ftxtID=50964&pageID=287
- TFF's 2026/27 Süper Lig regulations specify **18 clubs**: https://www.tff.org/Resources/TFF/Documents/STATULER/2026-2027/2026-2027-sezonu-super-lig-musabakalari-statusu.pdf
- Official TFF table shows rounds 1–34: https://www.tff.org/Default.aspx?hafta=27&macId=318081&pageId=198

## United States — NWSL and USL Championship

- Official 2026 NWSL rules specify **16 teams**, **30 regular-season matches per club**, and an eight-team single-elimination playoff: https://images.nwslsoccer.com/image/private/t_q-good/prd/tstudhfledlk7z8ygtzd.pdf
- Official 2026 NWSL schedule confirms all 16 clubs in opening weekend: https://www.nwslsoccer.com/news/the-2026-nwsl-schedule-is-here
- Official USL Championship format confirms **25 clubs**, 13 Eastern and 12 Western, with 30 league matches per club: https://www.uslsoccer.com/news_article/show/1351433
- The official schedule's 375 games also includes USL Cup group games; keep cup fixtures separate from USL Championship league fixtures: https://www.uslchampionship.com/news_article/show/1351833

## Spain — women's Liga F

- Liga F confirms 16 clubs for 2026/27: https://ligaf.es/noticia/los-clubes-de-liga-f-moeve-arrancan-la-temporada-20262027
- RFEF sets 30 Liga F matchdays: https://rfef.es/es/noticias/repasa-las-fechas-clave-del-futbol-femenino-para-la-temporada-202627
- LiveScoreFootball's Spanish Liga F record is a plausible counterpart to Bzzoiro's Liga F record, but exact fixtures and season IDs have not been crosswalked.

## Club Friendlies — classification correction

This is **not a single competition**. It is a generic category for non-competitive friendly matches between clubs from many countries. It has no single tournament roster, table or season.

**Decision:** Reclassify `observed_competition_097` from the competition identity queue to a fixture-type taxonomy after schema review. Do not create a canonical competition or season for it.

## Safeguards and remaining work

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.
- Keep men's and women's competitions distinct.
- Keep Club Friendlies as a fixture category, not a competition.
- Keep USL Cup matches separate from USL Championship league fixtures.
