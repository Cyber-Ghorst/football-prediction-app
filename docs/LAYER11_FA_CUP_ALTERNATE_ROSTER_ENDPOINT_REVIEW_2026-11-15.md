# FA Cup 2026/27 alternate roster endpoint evidence review

**Review date:** 15 November 2026  
**Season ID under review:** Sportmonks `28020`  
**Status:** Unverified; excluded from canonical catalogue import

## Question

The existing read-only Teams by Season ID diagnostic returned the same 699 team IDs for page 1/page 2 and `per_page=25/50`. The Football Association announced 743 accepted clubs for the 2026/27 Emirates FA Cup. This review tests whether documented ordering parameters or the Season by ID endpoint with `include=teams` expose a different roster.

## Read-only provider observations

The expanded diagnostic ran seven requests against Sportmonks:

| Request | Returned records |
|---|---:|
| `teams/seasons/28020`, page 1, per_page 25 | 699 |
| `teams/seasons/28020`, page 2, per_page 25 | 699 |
| `teams/seasons/28020`, page 1, per_page 50 | 699 |
| `teams/seasons/28020`, page 2, per_page 50 | 699 |
| `teams/seasons/28020`, order asc | 699 |
| `teams/seasons/28020`, order desc | 699 |
| `seasons/28020?include=teams` | 699 |

The latest report is `reports/provider_independent_catalogue/sportmonks_fa_cup_pagination_latest.json`, generated at 2026-11-15T15:27:11Z.

All seven requests returned the same 699-ID set:
- Ascending and descending order returned identical sets.
- Direct page-1 and Season `include=teams` returned identical sets.
- The endpoint returned no usable pagination metadata in these responses.
- The diagnostic records IDs and safe metadata only; it does not retain team names or raw provider payloads.

## Independent competition count

The FA's official announcement states that 743 clubs were accepted for the 2026/27 Emirates FA Cup:
https://www.thefa.com/news/2026/jun/26/clubs-accepted-exemptions-mens-fa-cup-fa-youth-fa-trophy-fa-vase-2026-27

The arithmetic difference between the FA's accepted-club count and the Sportmonks endpoint count is 44.

This count difference does **not** establish that Sportmonks is missing exactly 44 clubs. The two counts may represent different catalogue snapshots, eligibility scopes, inclusion rules, or provider coverage. This review does not identify which clubs account for the difference.

## Decision and safety controls

1. Keep Sportmonks season `28020` unverified and excluded from canonical catalogue import.
2. Do not bypass the repeated-page guard or interpret page/order parameters as effective pagination when the provider returns the same full ID set.
3. Do not create canonical team or season links from these observations.
4. Do not ingest FA Cup fixtures or statistics from this unverified roster.
5. Do not change prediction eligibility.

## Evidence needed to resolve the discrepancy

A future review should obtain a complete named list of the 743 accepted clubs from the FA's official source and a provider-authorized, complete named roster or other independently authoritative coverage evidence for the Sportmonks season. It should then perform set-level reconciliation, preserving unmatched and ambiguous records for review. A count comparison alone is insufficient.

## Diagnostic safety

The seven requests were read-only. The report states `read_only=true`, `database_accessed=false`, `database_writes=0`, `fixtures_requested=0`, and `statistics_requested=0`. No database, provider-link, fixture, statistics, or prediction state was changed.
