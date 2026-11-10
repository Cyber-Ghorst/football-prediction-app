# Free future-fixture adapter implementation

## Scope

The five selected free sources now have read-only parsing/transport adapters.
This is an implementation milestone, not production activation. The adapters
return source-scoped observations with raw payload, retrieval time, source URL,
licence note, status, kickoff and provider identities. They do not write
canonical fixtures, create predictions, or change provider routing.

## Adapter status

| Provider | Adapter | Current behavior | Remaining gate |
|---|---|---|---|
| OpenLigaDB | Implemented | Fetches the documented league-shortcut/season match endpoint; uses MatchID, UTC kickoff and team IDs; respects matchIsFinished. | Live per-league coverage/freshness and reuse rights; canonical competition/season/team crosswalks. |
| OpenFootball | Implemented | Reads football.json season files, including season subdirectories; stable source-scoped keys are used when upstream IDs are absent. | The public schema commonly supplies date-only fixtures; only explicit timezone-bearing date/time values are eligible. Upstream update cadence and canonical crosswalks remain to be checked. |
| Open Matchday | Implemented | Reads the documented fixtures CSV columns (gw,date,time,home,away). | Date/time follows the fixed CET-1 convention and is not silently converted. All such timestamps remain excluded until an approved timezone policy is established. Non-commercial-only terms block commercial deployment without permission. |
| LiveScoreFootball | Implemented | Existing API client fetches paginated events; normalization extracts event, competition, season and home/away identities. | Live freshness, precise kickoff offsets, and exact per-competition canonical crosswalks. |
| Bzzoiro | Implemented | Uses documented v2 GET /api/v2/events/?status=upcoming with Authorization: Token, limit/offset pagination and results envelope. | Requires BZZOIRO_API_TOKEN; verify account access, live coverage, field schema, licence and canonical crosswalks. |

## Safety rules

- A row is eligible for canonical review only when it is future-dated, scheduled,
  has an offset-aware ISO-8601 kickoff, has both distinct team names, and has
  competition and season identifiers.
- Missing source fixture IDs may receive deterministic provider-scoped
  observation keys. Those keys are not canonical fixture IDs.
- OpenFootball date-only/timezone-less values are excluded from prediction-ready
  use. Open Matchday's fixed CET-1 clock is not guessed or treated as a modern
  timezone database.
- No adapter is wired into the production collector. Sportmonks remains the
  only active future-fixture collector until the live evidence, crosswalk,
  persistence round-trip and conflict audits pass.
- No source values are averaged or allowed to silently overwrite canonical
  kickoff/team/competition identity.
- Bzzoiro's raw data may not be redistributed as a standalone feed/database/API;
  only permitted app display and derived outputs may be considered.
- Open Matchday remains unsuitable for commercial use without written rights.

## Tests

The test_free_fixture_adapters.py suite covers provider payload normalization,
timezone rejection, provider-scoped static keys, Bzzoiro authentication/response
handling, LiveScoreFootball event normalization, and eligibility filtering.
