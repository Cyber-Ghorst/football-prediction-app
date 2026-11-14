# Layer 11 — OpenLigaDB DFB competition evidence supplement

**Review date:** 15 November 2026  
**Scope:** official DFB evidence for selected OpenLigaDB country-unscoped records  
**Status:** evidence classification only; no provider-to-canonical links approved.

## Summary

The DFB's official 2026/2027 material confirms that Germany has an active top-tier women's league, a women's national cup, and a women's Supercup. It also confirms national-team schedules. This establishes the relevant German football structures and competition scope, but it does **not** by itself prove that a particular OpenLigaDB league ID is an exact feed identity. Exact provider ID matching still requires comparing the provider's match/team observations against official fixtures.

## Record dispositions

| OpenLigaDB ID | Source label | Evidence-based disposition | Country/scope decision | Remaining gate |
|---|---|---|---|---|
| 5972 | 1. Frauen Fußballbundesliga | Strong candidate for Germany's top-tier women's league. The DFB confirms the Google Pixel Frauen-Bundesliga is the top women's division and documents its 2026/27 clubs and fixtures. | Germany; women's first division candidate | Compare the ID's teams, dates and fixtures with the official DFB 2026/27 schedule before linking. |
| 6020 | DFB-Pokal Frauen | Competition identity and scope are confirmed: the DFB documents the 2026/27 DFB-Pokal der Frauen, including its 48-team format and schedule. | Germany; women's national cup | Exact provider fixture/team crosswalk still required. |
| 5985 | DFB Frauen Supercup | A corresponding official DFB women's Supercup exists. For 2026 the DFB calls it the Google Pixel Supercup der Frauen and confirms the 15 August 2026 match. The OpenLigaDB label is not the current official brand. | Germany; women's national super cup, one-match competition | Verify that ID 5985's actual teams/date match the official DFB event; do not equate on label alone. |
| 5981 | DFB Nationalspiele | Treat as a DFB national-team match collection, not a domestic league. | DFB/Germany national-team collection; individual matches may be international | Inspect team identities and match types; do not create a domestic league identity. |
| 5984 | DFB U21 | Treat as an age-group national-team collection, not a domestic league. | Germany U21 national-team collection; international fixtures possible | Inspect teams, age group and match types; keep distinct from senior national-team data. |
| 5983 | Frauen-Nationalmannschaft | Treat as a women's senior national-team match collection, not a domestic league. | Germany women's national-team collection; international fixtures possible | Inspect exact teams and competition labels; do not map to the women's Bundesliga. |

## Official evidence

- DFB, [Google Pixel Frauen-Bundesliga 2026/27 participant field and season structure](https://www.dfb.de/news/teilnehmerfeld-der-google-pixel-frauen-bundesliga-steht-fest-alle-sportlich-qualifizierten-klubs-erhalten-zulassung) — identifies the top women's division and 2026/27 participating clubs.
- DFB, [DFB-Pokal der Frauen 2026/27 competition information](https://www.dfb.de/frauen/dfb-wettbewerbe-frauen/dfb-pokal/wettbewerbsinformationen) — confirms the women's national cup, format, participating clubs and dates.
- DFB, [Google Pixel Supercup der Frauen](https://www.dfb.de/frauen/dfb-wettbewerbe-frauen/google-pixel-supercup-der-frauen) — confirms the official 2026 women's Supercup event and date.
- DFB, [women's national-team fixtures and schedule](https://www.dfb.de/frauen/nationalmannschaften/nationalmannschaft/spiele-und-termine) — confirms the separate national-team schedule and international match context.
- DFB, [women's 2026/27 competition calendar](https://www.dfb.de/news/rahmenterminkalender-der-frauen-2026/2027-verabschiedet) — separately identifies women's Bundesliga, 2. Frauen-Bundesliga, DFB-Pokal and Supercup.

## Safety and data-write outcome

- No OpenLigaDB ID is approved as an exact provider link by this supplement.
- No canonical competition, season, team, fixture or prediction-ledger row is created or modified.
- DFB national-team collections remain distinct from domestic league competitions.
- The 5972, 6020 and 5985 records are promoted only to **evidence-backed manual fixture crosswalk** status, not automatic mapping approval.
- Next step: obtain the raw OpenLigaDB match lists for these IDs and compare exact team/date/opponent combinations against DFB records. Any unmatched or ambiguous record stays quarantined.
