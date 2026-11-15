# Scottish Premiership 2026/27 cross-provider identity evidence review

**Review date:** 15 November 2026  
**Country:** Scotland  
**Provider competition IDs:** Bzzoiro `13`; LiveScoreFootball `735`  
**Provider season IDs:** Bzzoiro `13::1355`; LiveScoreFootball `735::2026`  
**Status:** Strong cross-provider competition/season corroboration; canonical mapping not approved

## Evidence reviewed

The committed Priority A provider-observation audit records:
- Bzzoiro: 24 raw observations, 24 eligible timezone-aware kickoffs, 12 unique teams.
- LiveScoreFootball: 6 raw observations, 6 eligible timezone-aware kickoffs, 12 unique teams.
- Four exact cross-provider fixture overlaps, each with the same normalized home/away teams and UTC kickoff.
- Both provider observations are country-scoped to Scotland and use 2026 season-year evidence. Bzzoiro labels its season "Premiership 26/27"; LiveScoreFootball labels its season "2026".

The official SPFL William Hill Premiership fixture schedule for Saturday 21 November 2026 independently corroborates all four exact fixture overlaps:

| Home | Away | Provider UTC kickoff | SPFL listed kickoff |
|---|---|---|---|
| Celtic | St. Mirren | 2026-11-21 15:00Z | 15:00 |
| Hibernian | Dundee United | 2026-11-21 15:00Z | 15:00 |
| Kilmarnock | Aberdeen | 2026-11-21 15:00Z | 15:00 |
| Motherwell | Rangers | 2026-11-21 20:00Z | 20:00 |

Official SPFL source:
https://spfl.co.uk/league/premiership/fixtures

The SPFL standings on its official results page list 12 Premiership clubs, consistent with the 12 unique team count reported by each provider:
https://spfl.co.uk/league/premiership/results

## Assessment

The combined evidence strongly supports that Bzzoiro competition `13` / season `13::1355` and LiveScoreFootball competition `735` / season `735::2026` describe the same Scottish Premiership 2026/27 competition scope:
1. Same competition name and country.
2. Season labels are compatible with 2026/27.
3. Both provider snapshots contain 12 unique teams.
4. Four exact, timezone-aware fixture overlaps match the official SPFL schedule in both pairing and kickoff time.

This is stronger than name-only or date-only matching. It independently corroborates the provider-to-provider competition and season relationship.

## Remaining canonical identity gate

The review does **not** approve a link to an existing Sportmonks or other canonical provider entity. Provider IDs are source-specific, and the current authenticated Sportmonks catalogue snapshot does not establish a matching Scottish Premiership 2026/27 canonical season/roster. A provider-independent canonical competition record and its governance rules must be established before writing canonical provider links.

## Decision and safeguards

- Record the Bzzoiro and LiveScoreFootball competition-season pair as strongly corroborated evidence for the same Scottish Premiership 2026/27 competition.
- Do not infer that their numeric IDs are interchangeable.
- Do not create provider links, canonical team links, or fixture/statistics writes in this evidence-only review.
- Do not change prediction eligibility.
- Retain the source-specific IDs and evidence so a later canonical identity review can decide whether to create a provider-independent competition record.

No database was accessed or modified for this review.
