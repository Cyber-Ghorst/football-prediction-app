# Priority A competition identity evidence dossier

Generated: 14 November 2026

This dossier adds official competition evidence for the ten multi-provider, country-scoped entries in the identity-review queue. It is an evidence aid, **not an approval of canonical identities or provider mappings**.

## Key finding

Official sources support the public competition identity and season context for all ten names. The provider-specific competition IDs and season IDs remain unverified as equivalent identities. Name, country and overlapping season-year evidence alone are not sufficient to create cross-provider links.

| Observed competition | External evidence | Provider-side gap |
|---|---|---|
| Bundesliga — Germany | DFL/Bundesliga identifies the licensed leagues and publishes the 2026/27 calendar. | Bzzoiro season year not parsed; only one provider supplies explicit competition type. |
| Premier League — England | Premier League publishes the 2026/27 club list and identifies the Championship as the second tier. | No provider supplies explicit competition type in this intake record. |
| Ligue 1 — France | LFP publishes the 2026/27 season dates and fixture calendar. | Competition type is supplied by only one provider; source IDs still need validation. |
| Championship — England | EFL identifies the Championship as one of its divisions and provides its official competition page. | No shared parsed season start year; verify this is the men's EFL Championship, not another similarly named competition. |
| 2. Bundesliga — Germany | DFL/Bundesliga distinguishes Bundesliga 2 and gives its 2026/27 start date. | No shared parsed season start year; provider season IDs need validation. |
| Serie A — Italy | Lega Serie A publishes the 2026/27 Serie A calendar and standings, distinct from Coppa Italia. | No shared parsed season start year; verify source records are the men's top division. |
| Eredivisie — Netherlands | Eredivisie/KNVB publishes the 2026/27 calendar. | No shared parsed season start year; verify source records are the men's top division. |
| Saudi Pro League — Saudi Arabia | SPL publishes the 2026/27 Roshn Saudi League schedule and revised calendar. | No shared parsed season start year; verify both providers mean the same competition scope. |
| La Liga — Spain | LALIGA publishes the 2026/27 LALIGA EA SPORTS competition page and fixtures. | No shared parsed season start year; source IDs still need validation. |
| MLS — United States and Canada | MLS describes itself as a top-flight professional league spanning the US and Canada and publishes 2026 competition guidelines. | Confirm the provider's country metadata is not US-only and that its season ID is the calendar-year 2026 MLS season. |

## Official evidence

- **Bundesliga:** [2026/27 calendar](https://www.bundesliga.com/en/bundesliga/news/calendar-for-2026-27-season-world-cup-34676); [DFL competition regulations](https://media.dfl.de/sites/2/2026/03/Spielordnung-SpOL-2026-03-06-Stand.pdf).
- **Premier League:** [Official 2026/27 competition and club guide](https://www.premierleague.com/en/news/4365156).
- **Ligue 1:** [LFP 2026/27 season dates](https://ligue1.com/en/articles/l1_article_3812-); [official 2026/27 calendar](https://ligue1.com/fr/articles/l1_article_5284-ligue-1-mcdonald-s-le-calendrier-de-la-saison-26-27).
- **Championship:** [EFL competitions](https://www.efl.com/about-the-efl/our-competitions/); [EFL Championship page](https://www.efl.com/competitions/efl-championship/).
- **2. Bundesliga:** [Bundesliga and Bundesliga 2 2026/27 calendar](https://www.bundesliga.com/en/bundesliga/news/calendar-for-2026-27-season-world-cup-34676); [DFL competition regulations](https://media.dfl.de/sites/2/2026/03/Spielordnung-SpOL-2026-03-06-Stand.pdf).
- **Serie A:** [Lega Serie A 2026/27 dates](https://www.legaseriea.it/serie-a/news/le-date-della-stagione-2026-2027); [official 2026/27 standings](https://www.legaseriea.it/serie-a/classifica?lang=en).
- **Eredivisie:** [Official 2026/27 calendar](https://eredivisie.nl/nieuws/speeldagenkalender-betaald-voetbal-seizoen-2026-27-vastgesteld/).
- **Saudi Pro League:** [2026/27 fixture schedule](https://www.spl.com.sa/en/news/spl-announces-2026-27-rsl-fixture-schedule); [revised 2026/27 calendar](https://www.spl.com.sa/en/news/rsl-schedule-2026-27).
- **La Liga:** [LALIGA EA SPORTS 2026/27](https://www.laliga.com/en-US/laliga-easports).
- **MLS:** [About MLS and the 2026 season](https://www.mlssoccer.com/news/about-major-league-soccer-x4174); [2026 competition guidelines](https://www.mlssoccer.com/league-reports/competition-guidelines/).

## Required safeguards

- No canonical competition or season records are created.
- No provider links are written.
- No fixtures are ingested and no prediction eligibility is granted.
- No future-fixture provider route is enabled.
- Each source record must pass country, competition type, gender/age/tier, season, participant and schedule checks before any mapping proposal.
- Any mapping proposal remains subject to explicit human approval.

Machine-readable evidence: `reports/provider_independent_catalogue/priority_a_external_evidence.json`.

## Raw provider audit findings (14 November 2026)

The read-only audit at [latest.json](../reports/provider_independent_catalogue/priority_a_provider_observation_audit/latest.json) examined 41,894 raw observations across the selected provider snapshots. It found 11 exact cross-provider fixture overlaps across the ten Priority A competition entries.

| Competition | Exact fixture overlaps | Material provider-side finding |
|---|---:|---|
| Bundesliga | 6 | OpenFootball's 1,530 rows have local date/time values without timezone evidence and are not eligible for exact UTC matching; football-data.org's sampled row lacks country. |
| Premier League | 1 | OpenFootball's 1,900 rows have local date/time without timezone evidence; no eligible exact UTC matches from that source. |
| Ligue 1 | 0 | OpenFootball's 1,530 rows have local date/time without timezone evidence; the sampled football-data.org row lacks country. |
| Championship | 0 | OpenFootball's 2,760 rows have local date/time without timezone evidence; no exact UTC cross-provider corroboration in this snapshot. |
| 2. Bundesliga | 3 | Bzzoiro and OpenLigaDB provide timezone-aware fixture observations; season labels differ (2026/27 vs 2026). |
| Serie A | 0 | OpenFootball's 1,900 rows have local date/time without timezone evidence; no eligible exact UTC corroboration from that source. |
| Eredivisie | 0 | OpenFootball's 1,530 rows have local date/time without timezone evidence; no eligible exact UTC corroboration from that source. |
| Saudi Pro League | 1 | Bzzoiro's snapshot contains 50 raw rows but only 5 eligible rows; LiveScoreFootball has 5 eligible rows. |
| La Liga | 0 | OpenFootball's 1,900 rows have local date/time without timezone evidence; no eligible exact UTC corroboration from that source. |
| MLS | 0 | Official league scope spans the United States and Canada, while one provider's observed country field says United States; provider geography needs reconciliation. |

### Interpretation and action

- An overlap count of zero means no exact match was found in this selected snapshot; it is not proof that the providers describe different competitions.
- Local date/time values without an authoritative timezone must remain ineligible for exact UTC fixture matching. Do not assume the provider's local timezone.
- The football-data.org country omissions and the MLS cross-border country-scope difference remain explicit evidence gaps.
- Provider competition IDs and provider season IDs remain unverified even where external official competition identity is supported.
- No canonical mappings, provider links, fixture writes, route changes or prediction eligibility are authorized by these findings.

The machine-readable audit is the source of truth for per-provider row counts and kickoff-quality counters. This summary is a review aid, not a replacement for the raw audit report.



## 15 November 2026 — refreshed review order

The corrected read-only audit completed successfully on 15 November 2026. Its per-entry exact-overlap counts and the current Sportmonks catalogue import state give the following review sequence. A catalogue target being present is **not** an approved identity link; it only means a potential canonical competition/season record is available for a later controlled comparison.

| Priority A identity | Exact fixture overlaps | Sportmonks 2026/27 target in current import | Review disposition |
|---|---:|---|---|
| Premier League — England | 2 | Present: league 8, season 28083 | First candidate for controlled source-to-target verification; provider IDs still unapproved |
| Bundesliga — Germany | 8 | Not present | Strongest fixture corroboration; canonical target must be sourced/verified before any link |
| 2. Bundesliga — Germany | 5 | Not present | Strong fixture corroboration; keep separate from Bundesliga |
| Saudi Pro League — Saudi Arabia | 1 | Not present | Verify provider competition scope and season independently before target search |
| La Liga — Spain | 0 | Present: league 564, season 27965 | Target exists; zero exact overlaps means source-side fixture/season evidence is still needed |
| Serie A — Italy | 0 | Present: league 384, season 27895 | Target exists; zero exact overlaps means source-side fixture/season evidence is still needed |
| Ligue 1 — France | 0 | Not present | Hold pending stronger cross-provider fixture/season evidence and canonical target |
| Championship — England | 0 | Not present | Hold; explicitly verify men's EFL Championship scope and season |
| Eredivisie — Netherlands | 0 | Not present | Hold; three distinct date/team leads are not exact UTC corroboration |
| MLS — United States/Canada | 0 | Not present | Hold; reconcile provider country metadata with MLS's cross-border competition scope |

The audit reports 20 exact overlaps overall, but only **16 belong to these ten Priority A identities**: Bundesliga 8, 2. Bundesliga 5, Premier League 2 and Saudi Pro League 1. The other four exact overlaps concern Scottish Premiership, which is outside this ten-entry Priority A queue and must not be counted as evidence for one of these identities.

The date-level report contains 162 candidate records representing **155 distinct date/team fixture leads** (seven repeated provider-pair records). Those leads are concentrated in Bundesliga (96), Premier League (56) and Eredivisie (3). They remain non-confirmatory because at least one source lacks timezone-aware kickoff evidence.

### Canonical target coverage limitation

The latest Sportmonks catalogue report is still partial: 4 of 5 selected seasons imported, covering Premier League, La Liga, La Liga 2 and Serie A (82 teams, 90 Sportmonks source links). The FA Cup season 28020 remains held after a repeated-page response. No fixtures were imported by that catalogue-only run. Therefore, target presence above is limited to the three imported Priority A competitions; it is not evidence that the other seven competitions do not exist in the canonical catalogue.

### Safe next actions

1. Verify Premier League source IDs against the available canonical target using official competition/season identity, team membership and timezone-aware fixture evidence. Keep the link proposal separate from approval.
2. Preserve Bundesliga and 2. Bundesliga as distinct competitions while locating verified canonical targets and checking their season scopes.
3. Investigate the Saudi Pro League provider-scope difference before looking for a canonical target.
4. For La Liga and Serie A, use official season/club evidence and independent provider schedules to address the lack of exact overlaps before proposing any source link.
5. Keep all remaining entries held until the evidence gates are met.

No new canonical records, provider links, fixture rows, future-fixture routes or prediction-ledger rows are authorized by this review-order update.

Machine-readable source: [refreshed Priority A observation audit](../reports/provider_independent_catalogue/priority_a_provider_observation_audit/latest.json). Canonical target coverage source: [Sportmonks catalogue sync report](../reports/sportmonks_catalogue_sync/latest.json).
