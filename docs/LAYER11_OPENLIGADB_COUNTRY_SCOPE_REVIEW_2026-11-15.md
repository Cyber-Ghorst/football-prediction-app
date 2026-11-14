# Layer 11 — OpenLigaDB country-unscoped source review

**Review date:** 15 November 2026  
**Purpose:** classify the 27 country-unscoped OpenLigaDB source records before any canonical competition or country mapping.  
**Status:** country/scope evidence triage completed for all 27; exact provider identity and canonical mapping remain unapproved.

## Findings

All 27 records in the latest crosswalk's `country_unscoped_sources` list belong to OpenLigaDB. The OpenLigaDB `getavailableleagues` response schema exposes `leagueId`, `leagueName`, `leagueShortcut`, `leagueSeason`, and `sport`, but no country field. Therefore, the missing country is not recoverable from that endpoint's league object alone.

The public OpenLigaDB league overview mixes official-looking competition names with user-created, team-filtered, charity, test, and international tournament entries. A country must not be assigned merely from a familiar name. In particular, the provider lists an official Bundesliga record (ID 4937) separately from a test-labelled `bl1test` record (ID 5957), and lists several separate World Cup-labelled records.

## Record-by-record triage

| OpenLigaDB league ID | Source name | Season | Observations | Initial disposition |
|---|---|---:|---:|---|
| 5972 | 1. Frauen Fußballbundesliga | 2026 | 546 | Named women's league; country and tier/gender must be verified from DFB/official league evidence. |
| 5958 | 2. Bundesliga 2026/27 (Herren) | 2026 | 918 | Men's second tier label; Germany is a candidate, but provider identity must be matched against the exact competition and season. |
| 5960 | BLClaude | 2026 | 174 | User-created/custom label; no canonical competition identity from name alone. |
| 5957 | Bundesliga | 2026 | 3 | OpenLigaDB lists shortcut bl1test; test-labelled duplicate, not interchangeable with official Bundesliga ID 4937. |
| 5985 | DFB Frauen Supercup | 2026 | 3 | Named DFB women's super cup; verify official competition scope and season. |
| 5981 | DFB Nationalspiele | 2026 | 18 | DFB national-team match collection; not necessarily a league. |
| 5984 | DFB U21 | 2026 | 9 | DFB U21 national-team competition/match collection; age-group scope required. |
| 6020 | DFB-Pokal Frauen | 2026 | 120 | Named women's cup; Germany is a candidate, but official DFB competition evidence required. |
| 5959 | Empty Stands Spendenliga 2026/2027 | 2026 | 432 | Charity/custom competition; do not treat as a national league. |
| 6027 | Eredivisie | 2026 | 918 | Netherlands is a candidate; exact OpenLigaDB competition/season must be verified. |
| 4949 | FIFA World Cup | 2026 | 144 | International tournament; country should be represented as international scope, not a host-country league. |
| 5966 | Franz-Beckenbauer-Supercup | 2026 | 3 | Named German super cup; competition type and official status require verification. |
| 5983 | Frauen-Nationalmannschaft | 2026 | 6 | National-team match collection; not a domestic league. |
| 4941 | Freundschafts-und-Testspiele | 2026 | 3 | Generic friendly/test-match collection; teams and match context needed to establish scope. |
| 5998 | Fußball-Regionalliga Nord | 2026 | 918 | Regional competition; Germany is a candidate, but regional association/tier needs verification. |
| 4900 | Hallenstadtmeisterschaft 2026 Bottrop | 2026 | 42 | Local indoor tournament; not a national league. |
| 5991 | NOFV Regionalliga NordOst | 2026 | 918 | Regional competition; Germany is a candidate, with NOFV scope to verify. |
| 6010 | NOFV-Oberliga Süd | 2026 | 720 | Regional competition; Germany is a candidate, with NOFV scope to verify. |
| 6016 | Oberliga Niederrhein | 2026 | 459 | Regional competition; Germany is a candidate, with regional association/tier to verify. |
| 5994 | Regionalliga West Frauen | 2026 | 720 | Women's regional competition; Germany is a candidate, gender/tier scope required. |
| 5992 | Spiele mit Arminia Bielefeld Beteiligung | 2026 | 102 | Team-filtered match collection, not a competition identity. |
| 4922 | tem26 | 2026 | 45 | Custom/opaque label; no canonical competition identity from name alone. |
| 4943 | Testliga Outi77 | 2026 | 81 | Explicit test league; exclude from canonical competition promotion. |
| 4927 | Testspiele Eintracht Frankfurt 26/27 | 2026 | 9 | Team-specific friendly collection; not a competition identity. |
| 4944 | Testspiele2026 | 2026 | 42 | Generic test-match collection; not a canonical competition identity. |
| 4897 | WM | 2026 | 312 | World Cup alias; international tournament scope, not a country league. |
| 4923 | WM 2026 USA | 2026 | 216 | World Cup-labelled source record; international scope; alias/duplicate relationship needs verification. |

## Evidence-based final scope classification

All 27 records now have a defensible *scope/disposition class*. This is not the same as approving provider-to-canonical mappings.

| Class | OpenLigaDB IDs | Count | Disposition |
|---|---|---:|---|
| Domestic league candidates | 5972, 5958, 6027, 5998, 5991, 6010, 6016, 5994 | 8 | Country and competition family established from official DFB/DFL/KNVB/regional federation material. Keep in exact team/fixture identity review. |
| Domestic cup/supercup candidates | 6020, 5985, 5966 | 3 | Germany; official DFB/DFL women's cup and men's/women's supercup structures confirmed. Keep exact match identity review. |
| National-team collections | 5981, 5984, 5983 | 3 | DFB senior, U21 and women's national-team collections; not domestic leagues. Preserve as national-team match collections, not domestic competition identities. |
| International tournament records | 4949, 4897, 4923 | 3 | World Cup scope is international. Do not assign USA or another host country as the competition country; alias/duplicate relationship still requires exact event evidence. |
| Custom/test/friendly/team-filtered/local records | 5960, 5957, 5959, 4941, 4900, 5992, 4922, 4943, 4927, 4944 | 10 | Keep raw provider observations for provenance, but exclude from canonical domestic-league promotion unless separate evidence establishes a real in-scope competition. ID 4900 remains a local indoor tournament candidate, not a national league. |
| **Total** | | **27** | Every source record has an explicit scope/disposition class. |

### Evidence supporting the genuine competition candidates

- DFB, [Google Pixel Frauen-Bundesliga 2026/27 participant field and season structure](https://www.dfb.de/news/teilnehmerfeld-der-google-pixel-frauen-bundesliga-steht-fest-alle-sportlich-qualifizierten-klubs-erhalten-zulassung) — top-tier women's league and participating clubs.
- DFB, [DFB-Pokal der Frauen 2026/27 competition information](https://www.dfb.de/frauen/dfb-wettbewerbe-frauen/dfb-pokal/wettbewerbsinformationen) — women's national cup, format, teams and dates.
- DFB, [Google Pixel Supercup der Frauen](https://www.dfb.de/frauen/dfb-wettbewerbe-frauen/google-pixel-supercup-der-frauen) — official women's Supercup event.
- DFL/Bundesliga, [2026 Franz Beckenbauer Supercup details](https://www.bundesliga.com/en/bundesliga/news/dfl-confirm-details-2026-franz-beckenbauer-supercup-bayern-munich-borussia-dortmund-37584) — official men's Supercup match, teams and date.
- DFL/Bundesliga, [2026/27 Bundesliga 2 fixture dates](https://www.bundesliga.com/en/bundesliga/news/confirmed-kick-off-times-dates-2026-27-fixtures-23955) and DFB, [2. Bundesliga 2026/27 schedule](https://datencenter.dfb.de/competitions/3/seasons/current) — official second-tier competition context.
- KNVB, [Definitive 2026/27 competition programme](https://www.knvb.nl/node/71918) — confirms the Eredivisie 2026/27 programme.
- Norddeutscher Fußball-Verband, [Regionalliga Nord der Herren 2026/2027](https://www.nordfv.de/news/regionalliga-nord-der-herren-2026-2027).
- Nordostdeutscher Fußballverband, [Regionalliga Nordost 2026/27 schedule](https://www.nofv-online.de/index.php/aktuelles-leser/regionalliga-nordost-spielplan-fuer-die-saison-2026-27-veroeffentlicht.html) and [NOFV-Oberliga Nord/Süd 2026/27 schedules](https://www.nofv-online.de/index.php/aktuelles-leser/veroeffentlichung-der-spielplaene-fuer-die-nofv-oberliga-saison-2026-27.html).
- Fußballverband Niederrhein, [Oberliga Niederrhein 2026/27 schedule](https://fvn.de/news/nachricht/herrenfussball/fortuna-heimspiel-zum-auftakt-spielplan-der-oberliga-niederrhein-fuer-die-saison-2026-2027-im-ueberblick-3102/).
- Westdeutscher Fußballverband, [Frauen-Regionalliga West](https://wdfv.de/spielbetrieb/frauen-regionalliga-west) — confirms this is one of five German women's regional leagues, limited to clubs from North Rhine-Westphalia.

## Safe disposition rules

1. Preserve provider league IDs and season IDs as namespaced source identifiers. Never merge IDs because names resemble one another.
2. Represent international tournaments as international scope, not as a domestic country league.
3. Do not promote team-filtered collections, friendlies, charity competitions, custom labels, or test leagues as canonical competitions without separate proof that they are genuine competitive entities in scope.
4. For genuine competition candidates, verify exact team sets, fixture dates, opponents, competition type, gender/age group, division/tier, season boundaries and provider ID before proposing a mapping.
5. No canonical rows, provider links, season links, team links, fixture writes, or prediction eligibility are created by this review.

## Source evidence for the original gap

- [OpenLigaDB public 2026 league overview](https://openligadb.de/Leagues?season=2026) — lists league names, seasons, shortcuts, IDs, creators and separate football/test/sport sections.
- [OpenLigaDB API documentation](https://api.openligadb.de/index.html) — documents the available-leagues endpoint and source API.
- [OpenLigaDB available-leagues response schema](https://skmtc.dev/openligadb/apis/openligadb-api/docs/getavailableleagues/get) — response fields include league ID, name, shortcut, season and sport; no country property.
- [Latest provider crosswalk audit](../reports/free_fixture_crosswalk_audit/latest.json) — source of the 27 country-unscoped records and their observation counts.

**Outcome:** the original 27-record *country/scope triage* is now classified. The remaining blocker is exact OpenLigaDB ID identity validation against raw teams and fixtures. The source API's available-leagues endpoint does not expose country, and the raw match-list API could not be retrieved through the current connected GitHub/web access. Until those observations are available, the genuine competition candidates remain quarantined from canonical mapping and prediction use.
