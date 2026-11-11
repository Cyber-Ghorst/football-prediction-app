# Free fixture observation pipeline

The pipeline connects each free-source adapter to the append-only provider
snapshot archive. It is a staging workflow, not a production fixture collector.

## Supported collection entry points

- collect_openligadb_observations(database_url, scopes, client=None)
  - scopes: league_shortcut + numeric season.
- collect_openfootball_observations(database_url, datasets, client=None)
  - datasets: season_file + competition.
- collect_openmatchday_observations(database_url, datasets, client=None)
  - datasets: raw CSV url + competition + season.
- collect_livescore_observations(database_url, league_slugs, date_from, date_to, client=None)
  - requests scheduled events for the explicit league slugs and date window.
- collect_bzzoiro_observations(database_url, params=None, client=None)
  - requires BZZOIRO_API_TOKEN; forces status=upcoming.
- collect_highlightly_observations(database_url, date_from, days=7, client=None)
  - queries each UTC date separately, follows limit/offset pagination and keeps only explicit `Not started` rows with stable match/team IDs.
- collect_api_ninjas_observations(database_url, season, leagues=None, client=None)
  - restricts discovery to the eight competitions documented for the free current-season plan; uses scheduled status, stable game/team IDs and UTC start_time.

Each provider is collected independently. A failed scope is reported without
discarding successful scopes from the same provider. A batch is archived only
when at least one scope completed successfully.

## Example

```python
from free_fixture_observation_pipeline import collect_openfootball_observations

result = collect_openfootball_observations(
    database_url=provider_database_url,
    datasets=[
        {"season_file": "2026-27/en.1.json", "competition": "Premier League"},
        {"season_file": "2026-27/de.1.json", "competition": "Bundesliga"},
    ],
)
```

## Safety

- Uses the CockroachDB provider observation archive only.
- No canonical fixture upsert, no prediction creation, and no prediction-ledger
  write occurs.
- OpenFootball and Open Matchday timezone limitations remain enforced by the
  adapters; the pipeline does not infer timezones.
- Bzzoiro credentials are supplied through BZZOIRO_API_TOKEN and are never
  included in archived request parameters.
- Highlightly and API Ninjas credentials are supplied through their dedicated
  secrets and are never included in archived request parameters.
- API Ninjas' free tier is non-commercial and current-season only; its free
  competition set is explicitly bounded in code.
- A successful archive does not imply a competition/team crosswalk or
  prediction-ready status.
- The production upcoming-fixture collector and provider routing remain
  unchanged until explicit per-competition validation is complete.
