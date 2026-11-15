# Layer 11 — MLS 2026 identity evidence review

**Review date:** 15 November 2026  
**Queue entry:** `observed_competition_094`  
**Disposition:** Competition identity and calendar-year season supported; provider mapping and country-scope representation not approved

## Provider observations

| Provider | Competition ID | Season ID | Season label | Observation quality |
|---|---|---|---|---|
| Bzzoiro | `18` | `18::158` | MLS 2026 | 35 timezone-aware observations; 6 unique fixture IDs; 12 unique teams |
| LiveScoreFootball | `770` | `770::2026` | 2026 | 22 timezone-aware observations; 2 unique fixture IDs; 4 unique teams |

Both provider labels identify a calendar-year 2026 season. The Priority A audit found **zero exact cross-provider fixture overlaps**. The observed samples are too small to establish full provider roster coverage or provider-ID equivalence.

## Official Major League Soccer evidence

1. MLS describes itself as the top-flight professional league in the United States and Canada and confirms 30 clubs for 2026: https://www.mlssoccer.com/news/about-major-league-soccer-x4174
2. The official 2026 competition guidelines list 30 clubs across the Eastern and Western Conferences and state that each club plays 34 regular-season matches: https://www.mlssoccer.com/about/competition-guidelines
3. The official 2026 regular-season schedule confirms the 21–22 February opening weekend and 7 November Decision Day: https://www.mlssoccer.com/news/mls-unveils-2026-regular-season-schedule

## Scope and roster comparison

- Official competition scope: **30 clubs**, split into 15 Eastern and 15 Western Conference clubs.
- Official geographic scope: **United States and Canada**.
- Bzzoiro sample: **12/30 clubs observed**.
- LiveScoreFootball sample: **4/30 clubs observed**.
- Shared provider teams in the bounded samples include FC Cincinnati, Orlando City SC, Real Salt Lake and Seattle Sounders FC; however, no exact fixture overlap was confirmed.
- Both provider season labels are consistent with the 2026 calendar year, but the IDs `18::158` and `770::2026` are not proven equivalent.
- The identity queue currently records the country as United States only. That is incomplete for MLS, whose official competition scope also includes Canadian clubs. A cross-border country-scope convention is needed before a canonical competition key can be approved.

## Assessment

- Competition identity: **externally corroborated**.
- Competition type: **men's top-flight professional league, externally corroborated**.
- Season context: **2026 calendar-year season, externally corroborated**.
- Official club count: **30**.
- Bzzoiro sample: **12/30 clubs**.
- LiveScoreFootball sample: **4/30 clubs**.
- Exact cross-provider fixture corroboration: **0**.
- Geographic scope: **United States and Canada**; current queue country field is incomplete.
- Provider competition/season ID equivalence: **not established**.

## Decision and safeguards

Keep both provider records source-scoped. Do not approve a US-only canonical country identity for this transnational competition.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.

Next evidence needed: a formal country-scope representation for cross-border competitions, complete provider roster evidence, and a confirmed cross-provider fixture pair. Human review is required before changing queue scope or creating links.