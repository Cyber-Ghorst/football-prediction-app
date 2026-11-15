# Competition identity review queue

This queue stages the 97 approved observed competition records for manual identity review. It is ordered for efficient review, not a statement of canonical identity.

## Priority counts

- **A — multi-provider with country context:** 12
- **B — single-provider with country context:** 85
- **C — country missing/ambiguous:** 0

## Required review gates

1. Verify that the competition exists and establish its type (league, cup, tournament, etc.).
2. Verify country/territory from evidence; do not infer it from the competition name.
3. Verify gender, age group, division/tier and senior/reserve scope where relevant.
4. Verify season boundaries and provider-specific season IDs independently.
5. Compare cross-provider names only after country and type context are established.
6. Record provenance for each decision; do not merge similar names without evidence.

## Safety boundary

This is a triage queue only. All entries remain unverified. No canonical identities, provider links, seasons, teams, fixtures, or prediction eligibility are created or approved. Future-fixture routes remain disabled pending their separate gates.

Machine-readable details: [identity_review_queue.json](../reports/provider_independent_catalogue/identity_review_queue.json).

## Disposition update — 15 November 2026

All 97 entries now have an explicit machine-readable review disposition:

- Priority A (12): official-source and raw-observation evidence reviewed; canonical mapping remains unapproved.
- Priority B (85): held as single-provider-only because no second independent source corroborates the exact competition/country identity.
- Priority C (0): no entries.
- 27 country-unscoped source records remain outside identity groups and are held until country evidence is available.

This closes the intake triage. It does **not** authorize canonical mappings. The latest read-only provider crosswalk and Priority A raw-observation reports are linked from [the Layer 11 closeout report](LAYER11_COMPLETION_REPORT_2026-11-14.md). The 85 single-provider records must remain source-scoped until independent evidence exists.



Two records were re-triaged from Priority B to Priority A after the refreshed provider crosswalk found independent source coverage and shared 2026 season-year evidence, and official competition schedules were reviewed:

- **Austrian Bundesliga — Austria:** Bzzoiro and LiveScoreFootball; provider competition IDs 96 and 3907; season IDs `96::1999` and `3907::2026`. No exact UTC fixture overlap was found in the selected observation window.
- **Scottish Premiership — Scotland:** Bzzoiro and LiveScoreFootball; provider competition IDs 13 and 735; season IDs `13::1355` and `735::2026`. Four exact UTC fixture overlaps were found and corroborated against the SPFL 2026/27 fixture calendar.

The queue now contains **12 Priority A** and **85 Priority B** identities. All remain unverified for canonical mapping. The 27 country-unscoped OpenLigaDB records remain separately held. No canonical rows, provider links, fixture rows or prediction records were written.


## Saudi Pro League 2026/27 evidence review — 15 November 2026

The Saudi Pro League entry (Priority A) now has a competition-level evidence review. Official SPL sources confirm the 2026/27 competition and corroborate one exact Bzzoiro/LiveScoreFootball fixture overlap (Al Ahli vs Al Nassr, 20 November 2026). Full roster coverage and provider-specific season-ID equivalence remain unverified; the entry remains unapproved. See [the detailed evidence review](LAYER11_SAUDI_PRO_LEAGUE_IDENTITY_REVIEW_2026-11-15.md).
