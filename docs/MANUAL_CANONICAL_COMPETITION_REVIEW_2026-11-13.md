# Manual canonical competition review — 13 November 2026

## Scope and safety boundary

This review uses the latest archived `reports/free_fixture_crosswalk_audit/latest.json` (generated 2026-11-13 14:49:03 UTC) and `reports/sportmonks_catalogue_sync/latest.json` (completed 2026-11-11 10:55:58 UTC).

The provider-independent report contains 269 distinct competition/country identities, including 18 exact-name-and-country groups observed in at least two providers. These are **review candidates, not canonical approvals**. The source report supplies no competition-type evidence for any of the 18 groups. Season-year overlap is supporting evidence only; it is not proof that two provider season IDs are interchangeable.

This document is a read-only review record. It creates no canonical league, season, team or fixture rows; no provider links; no staging rows; and no prediction records. Explicit provider links still require a human approval reason and existing canonical targets.

## Priority findings

### 1. Premier League — England

**Disposition: strongest candidate for explicit league-link approval.**

- Independent source identities: OpenFootball `en.1`; OpenLigaDB `5996`.
- Provider season identities: OpenFootball `en.1::2026-27` (label `2026-27`); OpenLigaDB `5996::2026` (label `2026`).
- Both providers report a 2026 season start year; exact competition name and country agree.
- Existing Sportmonks canonical target in the catalogue sync report: league `8`, season `28083` (`2026/2027`).
- Competition type is not supplied in the archived source metadata.

**Review conclusion:** identity and season context are strongly corroborated. The two league IDs are suitable for a human-reviewed mapping to Sportmonks league `8`, subject to a final live canonical-row existence check and explicit approval. The two provider season IDs should be mapped to Sportmonks season `28083` only after confirming their provider-parent relationship and the exact canonical season row.

### 2. La Liga — Spain

**Disposition: plausible canonical target; season mapping needs an additional check.**

- Independent source identities: Bzzoiro `3` (display label `LaLiga`); OpenFootball `es.1` (display label `La Liga`).
- Provider season identities: Bzzoiro `3::1307` (label `LaLiga 26/27`); OpenFootball `es.1::2026-27` (label `2026-27`).
- Exact competition/country grouping corroborates the competition identity. OpenFootball provides a 2026 start year; the catalogue's conservative year parser does not extract a four-digit year from Bzzoiro's `26/27` label, so cross-provider season evidence is currently marked insufficient.
- Existing Sportmonks canonical target in the catalogue sync report: league `564`, season `27965` (`2026/2027`).
- Competition type is not supplied in the archived source metadata.

**Review conclusion:** the competition identity is a strong candidate for mapping to Sportmonks league `564`, after verifying the canonical row and the provider's `LaLiga` naming variant. Do not map Bzzoiro season `3::1307` or OpenFootball season `es.1::2026-27` yet; confirm their season identity against Sportmonks season `27965` and their parent competition IDs first.

### 3. Bundesliga — Germany

**Disposition: corroborated identity; no confirmed canonical target in the current imported catalogue.**

- Sources: Bzzoiro `5`; OpenFootball `de.1`; OpenLigaDB `4937`.
- Seasons: Bzzoiro `5::1091` (`Bundesliga 26/27`); OpenFootball `de.1::2026-27`; OpenLigaDB `4937::2026`.
- OpenFootball and OpenLigaDB independently overlap on 2026; Bzzoiro's abbreviated year is not parsed.
- No Bundesliga canonical league/season is listed among the four imported Sportmonks seasons in the current sync report.

**Review conclusion:** competition identity is strongly corroborated, but no provider-to-canonical link can be approved until a verified canonical Bundesliga target and 2026/2027 season exist. Do not create canonical rows from this review.

### 4. Ligue 1 — France

**Disposition: corroborated identity; no confirmed canonical target and season evidence needs checking.**

- Sources: Bzzoiro `6`; OpenFootball `fr.1`.
- Seasons: Bzzoiro `6::1311` (`Ligue 1 26/27`); OpenFootball `fr.1::2026-27`.
- Only OpenFootball contributes a parsed four-digit start year; current report marks season evidence insufficient.
- No Ligue 1 canonical league/season is listed among the imported Sportmonks seasons in the current sync report.

**Review conclusion:** preserve as a corroborated competition candidate, but do not link until a canonical target and season are independently verified.

### 5. Other high-interest candidates

| Competition | Source provider IDs | Season evidence | Review disposition |
|---|---|---|---|
| 2. Bundesliga (Germany) | Bzzoiro `94`; OpenLigaDB `4938` | Insufficient parsed cross-provider year evidence | No confirmed canonical target; hold |
| MLS (United States) | Bzzoiro `18`; LiveScoreFootball `770` | Shared start year 2026 | No confirmed canonical target; hold |
| Copa Colombia (Colombia) | Bzzoiro `81`; Highlightly `205875` | Shared start year 2026 | No confirmed canonical target; hold |
| USL Championship (United States) | Bzzoiro `57`; Highlightly `217789` | Shared start year 2026 | No confirmed canonical target; hold |
| Saudi Pro League (Saudi Arabia) | Bzzoiro `17`; LiveScoreFootball `21231` | Insufficient parsed cross-provider year evidence | No confirmed canonical target; hold |
| Eerste Divisie (Netherlands) | Bzzoiro `108`; Highlightly `76523` | Insufficient parsed cross-provider year evidence | Hold |
| Liga Portugal 2 (Portugal) | Bzzoiro `88`; Highlightly `81629` | Insufficient parsed cross-provider year evidence | Hold |
| Copa del Rey (Spain) | Bzzoiro `41`; Highlightly `122477` | Insufficient parsed cross-provider year evidence | Hold |
| Segunda División (Spain) | Bzzoiro `38`; Highlightly `120775` | Insufficient parsed cross-provider year evidence | Hold |
| Coupe de France (France) | Bzzoiro `44`; Highlightly `56950` | Insufficient parsed cross-provider year evidence | Hold |
| Girabola (Angola) | Bzzoiro `98`; Highlightly `338631` | Insufficient parsed cross-provider year evidence | Hold |
| League One (England) | Bzzoiro `86`; Highlightly `35675` | Insufficient parsed cross-provider year evidence | Hold |
| League Two (England) | Bzzoiro `87`; Highlightly `36526` | Insufficient parsed cross-provider year evidence | Hold |
| National League (England) | Bzzoiro `91`; Highlightly `37377` | Insufficient parsed cross-provider year evidence | Hold |

All candidates above lack provider-supplied competition-type evidence. The names and countries are corroborated by the exact normalized-name/country grouping, but season equivalence and canonical target existence remain separate checks.

## Recommended order of work

1. Verify the live canonical rows for Premier League `8` and La Liga `564` and their 2026/2027 seasons `28083` and `27965`.
2. Generate the provider-specific league/season crosswalk preview against those live canonical rows. Confirm every source ID and parent competition before proposing a link.
3. Ask for explicit approval of the exact proposed links, with a written reason for the approval audit.
4. Only after approval, persist league links first, then re-run season candidate generation using those verified parent links. Team links remain a separate review.
5. For Bundesliga, Ligue 1, MLS and the remaining candidates, wait for a verified canonical target; do not seed new canonical entities solely from provider consensus.

## Verified safety invariants from the latest reports

- Automatic mapping approvals: `0`.
- Provider links created by the provider-independent catalogue audit: `0`.
- Canonical fixture writes in the collection run: `0`.
- Prediction-ledger writes in the collection run: `0`.
- Automatic promotion remains disabled.

## Source reports

- [Provider-independent crosswalk audit](../reports/free_fixture_crosswalk_audit/latest.json)
- [Sportmonks catalogue sync](../reports/sportmonks_catalogue_sync/latest.json)
- [Provider crosswalk review rules](PROVIDER_ENTITY_CROSSWALK_REVIEW.md)
