# Layer 11 — OpenLigaDB country-unscoped source review

**Review date:** 15 November 2026  
**Purpose:** classify the 27 country-unscoped OpenLigaDB source records before any canonical competition or country mapping.  
**Status:** read-only triage; no mappings or links approved.

## Findings

All 27 records in the latest crosswalk's `country_unscoped_sources` list belong to OpenLigaDB. The OpenLigaDB `getavailableleagues` response schema exposes `leagueId`, `leagueName`, `leagueShortcut`, `leagueSeason`, and `sport`, but no country field. Therefore, the missing country is not recoverable from that endpoint's league object alone.

The public OpenLigaDB league overview also mixes official-looking competition names with user-created, team-filtered, charity, test, and international tournament entries. A country must not be assigned merely from a familiar name. In particular, the provider lists an official-looking Bundesliga record (ID 4937) separately from a test-labelled `bl1test` record (ID 5957), and lists several separate World Cup-labelled records.

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

## Safe disposition rules

1. Keep the source country null until an authoritative competition/federation source or sufficiently strong team-and-fixture evidence establishes scope.
2. Represent international tournaments as international scope, not as a domestic country league.
3. Do not promote team-filtered collections, friendlies, charity competitions, custom labels, or test leagues as canonical competitions without separate proof that they are genuine competitive entities in scope.
4. Preserve provider league IDs and season IDs as namespaced source identifiers. Never merge IDs because names resemble one another.
5. For genuine competition candidates, verify country, competition type, gender/age group, division/tier, active status, season boundaries, teams, and exact fixture overlaps before proposing a mapping.
6. This review does not create canonical rows, provider links, season links, team links, fixtures, or prediction eligibility.

## Source evidence

- [OpenLigaDB public 2026 league overview](https://openligadb.de/Leagues?season=2026) — lists league names, seasons, shortcuts, IDs, creators and separate football/test/sport sections.
- [OpenLigaDB API documentation](https://api.openligadb.de/index.html) — documents the available-leagues endpoint and source API.
- [OpenLigaDB available-leagues response schema](https://skmtc.dev/openligadb/apis/openligadb-api/docs/getavailableleagues/get) — response fields include league ID, name, shortcut, season and sport; no country property.
- [Latest provider crosswalk audit](../reports/free_fixture_crosswalk_audit/latest.json) — source of the 27 country-unscoped records and their observation counts.

**Outcome:** this resolves the *cause and triage category* of the 27-record country gap, but does not falsely claim that all 27 have verified country mappings. The next review must use official competition evidence and exact provider fixture/team observations for each genuine competition candidate.
