# LiveScoreFootball scheduled-fixture validation and freshness

The provider API's documented `from` and `to` query parameters use
`YYYYMMDD`, not `YYYY-MM-DD`. The collector accepts strict ISO calendar
dates and converts them to the compact API format before requesting fixtures.
Both representations are retained in the observation batch metadata.

The API is backed by stored MongoDB snapshots rather than on-demand upstream
requests. Therefore, the retrieval time of our request is not proof that the
underlying competition schedule is fresh. The refresh collector now captures
each league catalogue row's `lastSyncedAt` value and attaches it to every
fixture observation from that league.

Promotion requires a valid, non-future, no-older-than-24-hour competition sync
timestamp for LiveScoreFootball. Missing or stale values block promotion even
when the returned event has a future kickoff and scheduled status. The manual
staging flow also attempts to retrieve the league catalogue; if the sync time
is unavailable, observations remain archived for diagnostics but cannot be
promoted.

The route remains disabled until a successful scheduled refresh demonstrates
actual events, current per-competition sync times, timezone-aware kickoff
timestamps and reviewed canonical competition/season/team links.
