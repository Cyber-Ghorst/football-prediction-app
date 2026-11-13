# Provider-to-canonical competition mapping preview — 13 November 2026

## Purpose and safety boundary

This is a read-only approval preview built from the archived provider crosswalk audit generated at `2026-11-13T14:49:03Z` and the Sportmonks catalogue sync report completed at `2026-11-11T10:55:58Z`.

It proposes **league-level mappings only**. It does not approve or create links, canonical rows, season links, team links, fixture rows, or predictions. The archived crosswalk code labels exact contextual matches `candidate_requires_manual_approval`; that status is not an approval.

A fresh live CockroachDB query was not available during this review. Therefore the imported catalogue report is evidence of the prior sync, not a claim that the canonical rows were re-queried live on 13 November.

## Canonical targets in the latest Sportmonks catalogue sync report

| Competition | Country | Sportmonks league ID | Sportmonks season ID | Season |
|---|---|---:|---:|---|
| Premier League | England | `8` | `28083` | 2026/2027 |
| La Liga | Spain | `564` | `27965` | 2026/2027 |

The sync report records both competitions as imported, with 20 teams each. The report is marked successful, although the overall catalogue sync is marked incomplete because another competition pagination request failed. These two imported rows are individually listed in its `imported_seasons` array.

## Exact league-level mapping candidates

| Provider | Provider competition ID | Provider display name | Country | Proposed canonical target | Archived candidate status |
|---|---|---|---|---|---|
| OpenFootball | `en.1` | Premier League | England | Sportmonks league `8` | `candidate_requires_manual_approval` |
| OpenLigaDB | `5996` | Premier League | England | Sportmonks league `8` | `candidate_requires_manual_approval` |
| OpenFootball | `es.1` | La Liga | Spain | Sportmonks league `564` | `candidate_requires_manual_approval` |
| Bzzoiro | `3` | La Liga | Spain | Sportmonks league `564` | `candidate_requires_manual_approval` |

The candidate generator reports exact normalized name and country-context matches for all four league candidates. The provider-independent catalogue independently groups OpenFootball `en.1` and OpenLigaDB `5996` as Premier League (England), and Bzzoiro `3` and OpenFootball `es.1` as La Liga (Spain).

Evidence volume in the archived observation snapshots:
- Premier League: 1,140 observations from OpenFootball and 1,140 from OpenLigaDB.
- La Liga: 1,140 observations from OpenFootball and 3 from Bzzoiro. Bzzoiro's league identity is a candidate, but its low observation count makes it weaker corroboration than the Premier League pair.

No automatic approvals were made. The archived report shows zero existing provider league, season, and team links for these provider records at the time of the audit.

## Season mapping: deliberately not proposed yet

| Provider | Provider season ID | Label | Decision |
|---|---|---|---|
| OpenFootball | `en.1::2026-27` | 2026-27 | Hold until its parent league link is approved and a fresh parent-scoped season candidate is generated |
| OpenLigaDB | `5996::2026` | 2026 | Hold until its parent league link is approved and the provider season entity is confirmed in a fresh audit |
| OpenFootball | `es.1::2026-27` | 2026-27 | Hold until its parent league link is approved and a fresh parent-scoped season candidate is generated |
| Bzzoiro | `3::1307` | LaLiga 26/27 | Hold; the archived parser did not extract a four-digit start year from this abbreviated label, and only 3 observations were archived |

The provider crosswalk implementation intentionally refuses to propose a season target until the provider competition has an existing canonical parent link. The next safe sequence is therefore:
1. Obtain a fresh live canonical-row and existing-link read.
2. If all four league rows still match these exact IDs and no conflicting links exist, request explicit approval for the four league links.
3. Only after approval and persistence, regenerate season candidates using the now-verified parent links.
4. Review each season candidate separately; do not infer season equivalence solely from abbreviated labels.

## Approval boundary

This preview is not the user's approval to persist links. No database write has been performed. Bundesliga, Ligue 1, MLS, 2. Bundesliga, and all other candidates remain outside this preview until a valid canonical target is verified.

## Source files

- `reports/free_fixture_crosswalk_audit/latest.json`
- `reports/sportmonks_catalogue_sync/latest.json`
- `docs/MANUAL_CANONICAL_COMPETITION_REVIEW_2026-11-13.md`
- `provider_crosswalk_review_report.py`
- `provider_entity_crosswalk.py`
