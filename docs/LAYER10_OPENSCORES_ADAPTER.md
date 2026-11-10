# Layer 10 — OpenScores read-only corroboration adapter

## Objective

Add an isolated, read-only connector for OpenScores squad, lineup, player, team and match-event data. The adapter returns raw provider data with retrieval-time and attribution metadata. It is not an xG/shot-quality adapter and is not connected to production prediction inputs.

## Source and operating constraints

- Provider: OpenScores — https://openscores.ai/
- API: documented MCP Streamable HTTP endpoint `https://api.openscores.ai/mcp/` (the trailing slash is required).
- Authentication: free `osk_live_*` API key, supplied as a Bearer token.
- Required deployment secret: `OPENSCORES_API_KEY`.
- Documented tools: `list_leagues`, `list_seasons`, `list_fixtures`, `get_fixture`, `get_standings`, `search_teams`, `get_team`, `search_players`, `get_player`.
- Documented coverage: Premier League, La Liga, Serie A, Bundesliga, Ligue 1 and the 2026 FIFA World Cup. This is not broad global coverage.
- Provider ingest is daily, not minute-by-minute live coverage.
- Terms permit use in personal and commercial products and caching/transformation, but prohibit reselling raw data as a competing dataset/API. Service is provided without uptime, accuracy or completeness guarantees.
- Published default limits: 60 calls/minute and 2,000 calls/hour per API key. The adapter does not automatically retry 429 responses.

## Data integrity and safety

- Every result is returned with provider name, tool name, retrieval timestamp and OpenScores attribution.
- Raw payloads are preserved; no fuzzy team/player identity mapping or automatic field merging is performed here.
- Do not treat absent values as zero or infer a player/fixture match from name similarity alone.
- Any future cross-provider reconciliation must preserve source IDs, source timestamps and field-level provenance, and record conflicts rather than silently choosing or averaging values.
- No provider priorities, model weights, TVD rules, tactical recency policy or production inference behavior are changed.
- The adapter performs no writes to Neon, CockroachDB, the fixture catalogue or prediction ledger.

## Setup

Add the free API key from the OpenScores account dashboard to Streamlit Community Cloud secrets or the GitHub Actions secret store as `OPENSCORES_API_KEY`. Never commit the key or print it in diagnostics.

The adapter can be exercised independently:

```python
from openscores import OpenScoresClient

with OpenScoresClient() as client:
    status = client.test_connection()
    squads = client.get_team(team_id=121)
```

The live connection test requires a valid key. Unit tests use mocked HTTP responses and do not require network access or credentials.

## Known limitations / next validation

- No authenticated live call has been made as part of this implementation until a valid key is configured in the deployment.
- The Streamlit app's Provider readiness panel includes a **Test OpenScores connection** control. It performs one authenticated, read-only `list_leagues` request and reports connection status, returned league count and UTC check time; it never displays the key or imports fixture data.
- Validate actual response shapes and coverage before building normalization or persistence.
- OpenScores does not document structured shot-level xG, shot coordinates or xG chain endpoints in the current public tools reference; do not market this adapter as an xG provider.
- This adapter is secondary research/corroboration only. It must not enter production model inputs without a separate, tested, explicitly approved integration objective.

## Public source references

- Docs: https://openscores.ai/docs
- FAQ and coverage: https://openscores.ai/faq
- Terms: https://openscores.ai/terms
- Changelog: https://openscores.ai/changelog
