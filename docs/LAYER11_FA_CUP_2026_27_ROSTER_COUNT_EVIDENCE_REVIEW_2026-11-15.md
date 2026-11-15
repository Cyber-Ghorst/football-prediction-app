# FA Cup 2026/27 Sportmonks roster-count evidence review

**Date:** 15 November 2026  
**Scope:** Read-only comparison of the authenticated Sportmonks team-by-season response with the Football Association's published 2026/27 entry count.

## Evidence

The FA's official announcement dated 26 June 2026 states that **743 clubs were accepted** to participate in the 2026/27 Emirates FA Cup. It links to the accepted-clubs list and exemptions:
- https://www.thefa.com/news/2026/jun/26/clubs-accepted-exemptions-mens-fa-cup-fa-youth-fa-trophy-fa-vase-2026-27

The Sportmonks read-only diagnostic for season ID `28020` made four requests to `GET /v3/football/teams/seasons/28020`:
- `per_page=25&page=1`
- `per_page=25&page=2`
- `per_page=50&page=1`
- `per_page=50&page=2`

Each response contained **699 team records and 699 distinct team IDs**. All four returned the same ordered ID sequence. The response top-level keys were `data`, `rate_limit`, `subscription`, and `timezone`; no pagination object or pagination metadata was returned.

Machine-readable evidence:
- `reports/provider_independent_catalogue/sportmonks_fa_cup_pagination_latest.json`

## Interpretation

The Sportmonks response count is **44 below** the FA's published accepted-entry count (699 versus 743). This is a material coverage discrepancy.

The four identical responses do not establish that 699 is a complete roster. The endpoint's documented pagination parameters did not produce distinct pages or pagination metadata in this account response. The provider response may represent a partial catalogue, a different participation snapshot, or an endpoint/account-specific behavior; the available evidence does not distinguish these explanations.

The official count is for clubs accepted to enter the competition, while the provider count is the set returned by the season endpoint. This comparison is a count-level completeness check only. It does not identify which 44 clubs are absent and does not establish that every accepted club should be represented in Sportmonks' current team-season catalogue.

## Decision and safeguards

- Keep FA Cup season ID `28020` **unverified and excluded from catalogue import**.
- Do not bypass the repeated-page guard or import the 699 records as a complete season roster.
- Do not create canonical team/season links from this count comparison.
- Do not ingest fixtures/statistics or enable prediction eligibility from this evidence.
- Next evidence required: a provider-supported complete roster response (or an independently documented endpoint/account explanation), followed by full participant-set reconciliation against the FA's accepted-clubs list and current competition stage.

**Outcome:** FA Cup roster completeness remains unresolved; no database or prediction state was changed.
