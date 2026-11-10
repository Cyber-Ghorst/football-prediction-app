# Layer 9 — independent prediction benchmark source

## Selected free source: TipMaster consensus

TipMaster publishes a free, read-only API of locked football prediction shares
from its player community. The National mode covers real matches across major
leagues and 15 countries. Its Top 20%, Top 25% and All-player groups are based
on recorded player performance; the Top 20%/Top 25% National cohorts are ranked
using the eight weeks before the match week.

- API: `GET https://tipmaster.de/api/agent/v1/consensus?mode=national`
- Authentication: none
- Rate limit: 60 requests/minute/IP; responses are cached for 60 seconds
- Attribution: link to https://tipmaster.de/agents/
- Terms: https://tipmaster.de/agents/terms/

## Important interpretation

TipMaster explicitly says its outcome shares measure group agreement, **not
calibrated probabilities**. The app must label them as crowd/expert consensus
shares, not as a competing model's calibrated probability. They can be scored
as a distributional comparator on the exact same completed fixture subset,
but interpretation must retain the cohort sample size and the provider's
warning. They are not ground truth.

The first adapter version accepts only National-mode matches whose status is
`locked` or `played`, whose crowd deadline is present and strictly before
kickoff, and whose identity and group distributions validate. Each published
group must have at least 20 participants. It preserves:
- provider match ID, competition, teams and kickoff;
- the immutable `deadlineUtc` as `prediction_locked_at`;
- provider `updatedAt` and response `generatedAt`;
- Top 20%, Top 25% and All-player shares and cohort sample sizes;
- source attribution URL and the time this app fetched the record.

Final scores/results are deliberately excluded from the normalized benchmark
record. The app's existing verified-result pipeline remains authoritative for
settlement.

## Isolation and safeguards

- Diagnostic benchmark only: `prediction_inputs_eligible=false`.
- Must not change prediction probabilities, weights, recency weighting, TVD,
  team profiles, feature snapshots or the prediction engine.
- No training or tuning against this feed.
- Do not scrape the website; use the documented API and respect its rate limit.
- Do not expose individual player data; the API provides aggregates only.
- Display the required TipMaster attribution wherever shares are shown.
- Coverage is limited to the matches TipMaster publishes. A missing match is
  unknown, not a zero-probability result.

## Why this source was selected

The API is public, free, read-only, keyless and documents its cohort selection,
freeze deadline, sample sizes, source attribution and usage terms. Unlike
market-derived probabilities, this is an independent human-consensus
comparator. It is not equivalent to Opta's statistical model, so reports must
identify it accurately as an expert/crowd consensus benchmark.
