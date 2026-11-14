# Layer 11 — OpenLigaDB DFB competition evidence supplement

**Review date:** 15 November 2026  
**Scope:** official DFB and regional-federation evidence for selected OpenLigaDB country-unscoped records  
**Status:** evidence classification only; no provider-to-canonical links approved.

## Summary

Official 2026/2027 material confirms Germany's women's top-tier league, women's national cup, women's Supercup, national-team schedules and several regional competitions. This establishes real-world competition scope, but does **not** by itself prove that a particular OpenLigaDB league ID is an exact feed identity. Exact provider ID matching still requires comparing the provider's match/team observations against official fixtures.

## DFB competition and national-team records

| OpenLigaDB ID | Source label | Evidence-based disposition | Country/scope decision | Remaining gate |
|---|---|---|---|---|
| 5972 | 1. Frauen Fußballbundesliga | Strong candidate for Germany's top-tier women's league. The DFB confirms the Google Pixel Frauen-Bundesliga is the top women's division and documents its 2026/27 clubs and fixtures. | Germany; women's first division candidate | Compare the ID's teams, dates and fixtures with the official DFB 2026/27 schedule before linking. |
| 6020 | DFB-Pokal Frauen | Competition identity and scope are confirmed: the DFB documents the 2026/27 DFB-Pokal der Frauen, including its 48-team format and schedule. | Germany; women's national cup | Exact provider fixture/team crosswalk still required. |
| 5985 | DFB Frauen Supercup | A corresponding official DFB women's Supercup exists. For 2026 the DFB calls it the Google Pixel Supercup der Frauen and confirms the 15 August 2026 match. The OpenLigaDB label is not the current official brand. | Germany; women's national super cup, one-match competition | Verify that ID 5985's actual teams/date match the official DFB event; do not equate on label alone. |
| 5981 | DFB Nationalspiele | Treat as a DFB national-team match collection, not a domestic league. | DFB/Germany national-team collection; individual matches may be international | Inspect team identities and match types; do not create a domestic league identity. |
| 5984 | DFB U21 | Treat as an age-group national-team collection, not a domestic league. | Germany U21 national-team collection; international fixtures possible | Inspect teams, age group and match types; keep distinct from senior national-team data. |
| 5983 | Frauen-Nationalmannschaft | Treat as a women's senior national-team match collection, not a domestic league. | Germany women's national-team collection; international fixtures possible | Inspect exact teams and competition labels; do not map to the women's Bundesliga. |

Official DFB evidence:
- [Google Pixel Frauen-Bundesliga 2026/27 participant field and season structure](https://www.dfb.de/news/teilnehmerfeld-der-google-pixel-frauen-bundesliga-steht-fest-alle-sportlich-qualifizierten-klubs-erhalten-zulassung) — identifies the top women's division and 2026/27 participating clubs.
- [DFB-Pokal der Frauen 2026/27 competition information](https://www.dfb.de/frauen/dfb-wettbewerbe-frauen/dfb-pokal/wettbewerbsinformationen) — confirms the women's national cup, format, participating clubs and dates.
- [Google Pixel Supercup der Frauen](https://www.dfb.de/frauen/dfb-wettbewerbe-frauen/google-pixel-supercup-der-frauen) — confirms the official 2026 women's Supercup event and date.
- [Women's national-team fixtures and schedule](https://www.dfb.de/frauen/nationalmannschaften/nationalmannschaft/spiele-und-termine) — confirms the separate national-team schedule and international match context.
- [Women's 2026/27 competition calendar](https://www.dfb.de/news/rahmenterminkalender-der-frauen-2026/2027-verabschiedet) — separately identifies women's Bundesliga, 2. Frauen-Bundesliga, DFB-Pokal and Supercup.

## Regional competition records

| OpenLigaDB ID | Source label | Official evidence | Country/scope decision | Remaining gate |
|---|---|---|---|---|
| 5998 | Fußball-Regionalliga Nord | The Norddeutscher Fußball-Verband publishes the men's Regionalliga Nord 2026/27 participant and admission information. | Germany; men's regional fourth-tier competition candidate | Match OpenLigaDB teams and fixtures to the NFV 2026/27 schedule before linking. |
| 5991 | NOFV Regionalliga NordOst | The NOFV publishes the official Regionalliga Nordost 2026/27 schedule. | Germany; men's regional competition candidate | Verify the exact provider team list and fixture dates against the NOFV schedule. |
| 6010 | NOFV-Oberliga Süd | The NOFV publishes the 2026/27 NOFV-Oberliga Nord and Süd schedules and identifies the South division's participating clubs. | Germany; men's regional fifth-tier competition candidate | Verify the exact provider team list and fixtures against the NOFV South schedule. |
| 6016 | Oberliga Niederrhein | The Fußballverband Niederrhein publishes the 2026/27 men's Oberliga Niederrhein schedule and identifies its clubs. | Germany; men's regional competition candidate | Match exact OpenLigaDB teams and fixtures against the FVN schedule. |
| 5994 | Regionalliga West Frauen | The Westdeutscher Fußballverband confirms the Frauen-Regionalliga West is one of five German women's Regionalligen, limited to clubs from North Rhine-Westphalia, and publishes the 2026/27 participants. | Germany; women's regional competition candidate (North Rhine-Westphalia) | Verify exact provider teams and fixtures against the WDFV schedule. |

Official regional-federation evidence:
- [Norddeutscher Fußball-Verband — Regionalliga Nord der Herren 2026/2027](https://www.nordfv.de/news/regionalliga-nord-der-herren-2026-2027).
- [Nordostdeutscher Fußballverband — Regionalliga Nordost 2026/27 schedule](https://www.nofv-online.de/index.php/aktuelles-leser/regionalliga-nordost-spielplan-fuer-die-saison-2026-27-veroeffentlicht.html).
- [Nordostdeutscher Fußballverband — NOFV-Oberliga Nord and Süd 2026/27 schedules](https://www.nofv-online.de/index.php/aktuelles-leser/veroeffentlichung-der-spielplaene-fuer-die-nofv-oberliga-saison-2026-27.html).
- [Fußballverband Niederrhein — Oberliga Niederrhein 2026/27 schedule](https://fvn.de/news/nachricht/herrenfussball/fortuna-heimspiel-zum-auftakt-spielplan-der-oberliga-niederrhein-fuer-die-saison-2026-2027-im-ueberblick-3102/).
- [Westdeutscher Fußballverband — Frauen-Regionalliga West](https://wdfv.de/spielbetrieb/frauen-regionalliga-west).

## Safety and data-write outcome

- No OpenLigaDB ID is approved as an exact provider link by this supplement.
- No canonical competition, season, team, fixture or prediction-ledger row is created or modified.
- DFB national-team collections remain distinct from domestic league competitions.
- IDs 5972, 6020 and 5985 are promoted only to **evidence-backed manual fixture crosswalk** status, not automatic mapping approval.
- IDs 5998, 5991, 6010, 6016 and 5994 can be removed from the generic "country unknown" research queue for **country/scope classification**, but remain in the exact-identity/manual-fixture-crosswalk queue.
- Next step: obtain the raw OpenLigaDB match lists for these IDs and compare exact team/date/opponent combinations against official federation records. Any unmatched or ambiguous record stays quarantined.
- No canonical mappings or data writes are authorized by this document.
