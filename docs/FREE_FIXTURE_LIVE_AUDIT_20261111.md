# Free future-fixture live audit — 2026-11-11

## Result

The adapter and archive code is implemented, but the five candidates are not
yet approved for production future-fixture routing. This audit distinguishes
publicly observable schedule evidence from prediction-ready fixture evidence.

| Provider | Live evidence observed | Data-quality result | Decision |
|---|---|---|---|
| OpenLigaDB | Public API documentation confirms the season endpoint and fields including MatchID, leagueSeason, team1/team2 and matchDateTimeUTC. The live JSON endpoint could not be retrieved in this audit environment. | A live scheduled row, current-season coverage, freshness and per-competition timestamp quality remain unverified. | Keep disabled. |
| OpenFootball | The public 2026/27 English Premier League JSON file is accessible and contains upcoming matchday 11 entries beginning 2026-11-21. Entries include date and time, but the dataset example/schema does not establish a timezone or stable provider match ID. | Date/time-only rows cannot be converted into exact UTC kickoffs safely. Source-scoped deterministic observation keys are allowed, but are not canonical fixture IDs. | Discovery evidence only; exclude from prediction-ready feed. |
| Open Matchday | The public Premier League 2026/27 fixtures CSV is accessible. Its first upcoming rows are dated 2026-11-21. The file has only gw,date,time,home,away columns. | No provider fixture IDs or team IDs. The data dictionary states date is UTC and time uses a fixed CET-1 convention; the time convention is not a timezone database and may be an hour out during summer. The project is non-commercial-only. | Research-only; exclude from prediction-ready feed and do not use commercially without permission. |
| LiveScoreFootball | Existing client exposes paginated league fixtures with scheduled status and date filters. The public API endpoints did not return a live payload in this audit environment. | Per-competition listener freshness, event-level timezone-aware kickoff, season identity and exact team crosswalk remain unverified. | Keep disabled. |
| Bzzoiro | Current documentation confirms GET /api/v2/events/?status=upcoming, Authorization: Token authentication, limit/offset pagination, results response envelope and UTC ISO-8601 timestamps. | No authenticated live response was available in this audit. Account token access, exact returned fields, competition coverage and licence conditions still require verification. | Keep disabled until authenticated audit and crosswalk checks pass. |

## Important distinction

- An endpoint or dataset containing future-looking rows is not enough to
  populate the prediction-ready catalogue.
- OpenFootball and Open Matchday currently expose future schedule observations,
  but their kickoff timestamps do not satisfy the application's strict
  timezone-aware UTC requirement.
- OpenLigaDB, LiveScoreFootball and Bzzoiro have documented routes suitable for
  further live validation, but this audit did not establish live per-competition
  records for them.
- None of the five sources is promoted to canonical fixture storage by this
  audit. The existing Sportmonks collector remains the only active production
  future-fixture collector.

## Remaining activation gates

1. Capture actual scheduled future rows for each source and target competition.
2. Verify timezone-aware kickoff precision, scheduled status, stable
   provider-scoped IDs and per-event freshness.
3. Verify provider competition and season identity, then create explicit
   canonical competition/season crosswalks.
4. Map both teams by explicit provider IDs or reviewed crosswalks; never use
   name similarity alone as an automatic identity link.
5. Persist immutable raw observations and provenance in the provider snapshot
   archive.
6. Deduplicate by canonical competition, season, home team, away team and
   kickoff; keep conflicts visible.
7. Complete database round-trip and regression tests before enabling any
   provider/competition route.
8. Re-check Open Matchday's non-commercial licence before any deployment that
   could be considered commercial.

## Sources checked

- OpenLigaDB season match endpoint documentation:
  https://skmtc.dev/openligadb/apis/openligadb-api/docs/getmatchdata/:leagueShortcut/:leagueSeason/get
- OpenFootball 2026/27 Premier League data:
  https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/en.1.json
- OpenFootball README and update/licence notes:
  https://github.com/openfootball/football.json
- Open Matchday 2026/27 Premier League fixture CSV:
  https://raw.githubusercontent.com/oladeeayo/open-matchday/master/data/ENG_1_premier-league/fixtures_2627.csv
- Open Matchday data dictionary:
  https://github.com/oladeeayo/open-matchday/blob/master/DATA_DICTIONARY.md
- Bzzoiro football events API:
  https://sports.bzzoiro.com/docs/football/events/
- Bzzoiro authentication and common API conventions:
  https://sports.bzzoiro.com/docs/
- LiveScoreFootball public API repository:
  https://github.com/rezarahiminia/livescoreFootball
