# Layer 11 — Saudi Pro League 2026/27 identity evidence review

**Review date:** 15 November 2026  
**Queue entry:** `observed_competition_072`  
**Disposition:** Evidence reviewed; canonical mapping not approved

## Provider observations

| Provider | Competition ID | Season ID | Season label | Observed coverage |
|---|---:|---|---|---|
| Bzzoiro | `17` | `17::1631` | Saudi Pro League 26/27 | 110 observations; 18 unique team names; 11 eligible scheduled observations; 99 marked postponed |
| LiveScoreFootball | `21231` | `21231::2026` | 2026 | 11 timezone-aware scheduled observations; only Al Ahli and Al Nassr observed |

The independent observation audit found one exact cross-provider fixture overlap:

- Al Ahli vs Al Nassr
- 20 November 2026, 17:30 UTC
- Both Bzzoiro and LiveScoreFootball

## Official competition evidence

1. The [Saudi Pro League's 2026/27 fixture announcement](https://www.spl.com.sa/en/news/spl-announces-2026-27-rsl-fixture-schedule), published 24 July 2026, states that the season runs from 13 August 2026 to 29 May 2027 and comprises 34 rounds and 306 fixtures.
2. The [SPL revised calendar announcement](https://www.spl.com.sa/en/news/rsl-schedule-2026-27), published 9 November 2026, confirms the league resumes on 20 November with Al Ahli hosting Al Nassr.
3. The [official SPL fixture PDF](https://images.spl.com.sa/image/private/fl_attachment/prd/m54jmnwpd2embhoz8bvb.pdf) lists Al Ahli vs Al Nassr on Friday 20 November 2026 at 20:30 local time. This agrees with the independent provider overlap at 17:30 UTC.

## Assessment

The official evidence establishes that the Saudi Pro League is a Saudi domestic league for 2026/27 and corroborates the shared Al Ahli–Al Nassr fixture. It is strong evidence that the two provider feeds refer to the same competition at the broad competition level.

It does **not** yet establish that the provider-specific competition and season IDs are interchangeable or that both providers expose the complete 18-club season scope:

- Bzzoiro has 18 team names, but its bounded sample contains 99 postponed observations and only 11 eligible scheduled observations.
- LiveScoreFootball has only two teams and one fixture in the sampled observations.
- LiveScoreFootball's season label is the calendar year `2026`, while Bzzoiro labels the season `2026/27`. The official season boundaries help interpret the calendar year but do not prove the provider's season-ID semantics.

## Decision and safeguards

- Competition existence and country: **corroborated**.
- Broad 2026/27 season context: **corroborated by official SPL evidence**.
- Exact cross-provider fixture: **one confirmed overlap**.
- Full roster and season-ID equivalence: **not established**.
- Canonical competition/season/team mappings: **not approved**.
- Provider links, fixture ingestion, and prediction eligibility: **unchanged and disabled**.

Next evidence needed: a broader LiveScoreFootball roster/fixture sample for the 2026/27 season and provider-specific season metadata that confirms its 2026 season ID's actual start/end scope. Until then, keep both provider records source-scoped.
