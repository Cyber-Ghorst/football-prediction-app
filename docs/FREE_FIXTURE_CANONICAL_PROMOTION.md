# Free-source canonical fixture promotion

Free-provider observations remain in the append-only provider snapshot archive until all required checks pass. The Streamlit Provider Readiness area now provides a preview and an explicit promotion action.

## Promotion gates

- A user must explicitly acknowledge that the selected provider's licence and reuse terms permit this app's collection, internal storage and fixture display. Open Matchday additionally requires confirmation that the use is non-commercial.
- The observation must be marked eligible by its adapter, have a timezone-aware retrieval timestamp, be no more than 24 hours old, and have a precise timezone-aware kickoff in the next seven days.
- The provider status must indicate a scheduled/not-started fixture.
- Competition, season, home team and away team must each have an existing explicit provider-to-canonical link.
- All canonical targets must be existing Sportmonks entities because the current prediction profile, season and player-availability workflow uses Sportmonks IDs. The canonical season must belong to the mapped competition.
- The home and away teams must map to different canonical teams.
- An existing exact canonical fixture is linked as provenance. A kickoff disagreement within 12 hours or a reused source fixture ID with a different identity is held as a conflict; records are never averaged or overwritten.

## Persistence and app catalogue

Promotion inserts only football_fixtures rows whose canonical entity mappings already exist. It never creates or changes leagues, seasons or teams. Source URLs, licence labels, retrieval time, provider fixture ID, snapshot ID and raw observation are retained in football_fixture_sources and the fixture payload. Every decision is written to free_fixture_promotion_audit.

Accepted free-provider fixtures are added to Neon upcoming_fixture_staging using an additive, no-delete, no-overwrite operation. The regular Sportmonks full refresh remains responsible for replacing its own rolling fixture set. Free-source staging therefore cannot erase Sportmonks fixtures or other approved source rows.

The promotion path does not run predictions, modify prediction weights, or write to the Neon prediction ledger. The selected-fixture prediction flow must still verify the canonical team/season context and will use Sportmonks for historical performance and any available match-detail enrichment.
