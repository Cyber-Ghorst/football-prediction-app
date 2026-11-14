# Layer 11 — Priority B potential cross-provider alias queue

**Review date:** 15 November 2026  
**Source:** `reports/provider_independent_catalogue/identity_review_queue.json`  
**Status:** manual review shortlist only; no aliases or provider links approved.

## Purpose

The Priority B queue contains 87 single-provider competition identities. A subset have names and country context that suggest they may be alternate labels for the same real-world competition in another provider. This shortlist groups those likely overlaps so that the next evidence pass can focus on exact team sets, fixtures, season boundaries and competition scope.

These are **not** approved aliases. Name similarity, a shared country, or a shared calendar year is not enough to link provider IDs. The underlying queue preserves every provider's namespaced competition and season IDs.

## Candidate groups

| Possible real-world scope | Queue entries | Provider source records | Raw observations in queue | Required check |
|---|---|---|---:|---|
| Argentina — Liga Profesional | observed_competition_002: Argentine Liga Profesional de Fútbol; observed_competition_003: Liga Profesional de Fútbol | livescore_football 745 (745::2026; 1 obs)<br>bzzoiro 85 (85::1635; 3 obs) | 4 | Confirm same top-tier competition and same season; names are close but fixture/team overlap is required. |
| Belgium — Pro League | observed_competition_006: Belgian Pro League; observed_competition_008: Pro League | livescore_football 3901 (3901::2026; 1 obs)<br>bzzoiro 14 (14::1327; 7 obs) | 8 | Confirm Belgian top-flight identity; 'Pro League' is ambiguous without country and team/fixture evidence. |
| Brazil — Série A | observed_competition_009: Brasileirão Serie A; observed_competition_011: Brazilian Serie A; observed_competition_012: Campeonato Brasileiro Série A | bzzoiro 9 (9::28; 35 obs)<br>livescore_football 630 (630::2026; 6 obs)<br>football_data_org 2013 (2013::2474; 31 obs) | 72 | Compare exact club lists and fixture timestamps across all three feeds. |
| England — Premier League | observed_competition_032: Premier League; observed_competition_026: English Premier League | bzzoiro 1 (1::1058; 7 obs)<br>openfootball en.1 (en.1::2026-27; 1140 obs)<br>openligadb 5996 (5996::2026; 1140 obs)<br>livescore_football 700 (700::2026; 10 obs) | 2297 | Compare LiveScoreFootball record with the already multi-provider Priority A group. |
| England — Championship | observed_competition_020: Championship; observed_competition_022: English League Championship | bzzoiro 12 (12::1111; 11 obs)<br>openfootball en.2 (en.2::2026-27; 1656 obs)<br>livescore_football 3914 (3914::2026; 11 obs) | 1678 | Compare LiveScoreFootball record with the already multi-provider Priority A group. |
| England — League One | observed_competition_023: English League One; observed_competition_029: League One | livescore_football 3915 (3915::2026; 15 obs)<br>bzzoiro 86 (86::1655; 50 obs) | 65 | Confirm identical EFL division and season; compare team sets and fixtures. |
| England — League Two | observed_competition_024: English League Two; observed_competition_030: League Two | livescore_football 3916 (3916::2026; 30 obs)<br>bzzoiro 87 (87::1674; 48 obs) | 78 | Confirm identical EFL division and season; compare team sets and fixtures. |
| England — National League | observed_competition_025: English National League; observed_competition_031: National League | livescore_football 3917 (3917::2026; 33 obs)<br>bzzoiro 91 (91::1903; 50 obs) | 83 | Confirm National League (fifth tier) and season; compare team sets and fixtures. |
| France — Ligue 1 | observed_competition_040: Ligue 1; observed_competition_039: French Ligue 1 | bzzoiro 6 (6::1311; 8 obs)<br>football_data_org 2015 (2015::2497; 1 obs)<br>openfootball fr.1 (fr.1::2026-27; 918 obs)<br>livescore_football 710 (710::2026; 1 obs) | 928 | Compare LiveScoreFootball record with the existing Priority A group; require exact fixtures. |
| Germany — Bundesliga | observed_competition_045: Bundesliga; observed_competition_047: German Bundesliga | bzzoiro 5 (5::1091; 9 obs)<br>football_data_org 2002 (2002::2522; 1 obs)<br>openfootball de.1 (de.1::2026-27; 918 obs)<br>openligadb 4937 (4937::2026; 918 obs)<br>livescore_football 720 (720::2026; 1 obs) | 1847 | Compare LiveScoreFootball record with the existing Priority A group; require exact fixtures. |
| Japan — J1 League | observed_competition_055: J1 League; observed_competition_056: Japanese J.League | bzzoiro 49 (49::1518; 16 obs)<br>livescore_football 750 (750::2026; 3 obs) | 19 | Confirm same J1 competition and calendar season; compare exact team/fixture evidence. |
| Mexico — Liga MX | observed_competition_057: Liga MX Apertura; observed_competition_058: Mexican Liga BBVA MX | bzzoiro 19 (19::1309; 8 obs)<br>livescore_football 760 (760::2026; 3 obs) | 11 | Check whether the Bzzoiro Apertura phase is the same scope as the LiveScore full Liga MX record; do not merge until phase/season boundaries match. |
| Spain — LaLiga | observed_competition_078: La Liga; observed_competition_079: LaLiga EA Sports; observed_competition_081: Primera Division; observed_competition_085: Spanish LALIGA | bzzoiro 3 (3::1307; 7 obs)<br>openfootball es.1 (es.1::2026-27; 1140 obs)<br>openligadb 4936 (4936::2026; 1140 obs)<br>football_data_org 2014 (2014::2518; 1 obs)<br>livescore_football 740 (740::2026; 1 obs) | 2289 | Resolve provider naming and country context; compare official 2026/27 fixture schedule. |
| Spain — Segunda División / LaLiga 2 | observed_competition_082: Segunda División; observed_competition_086: Spanish LALIGA 2 | bzzoiro 38 (38::1356; 39 obs)<br>livescore_football 3921 (3921::2026; 1 obs) | 40 | Confirm second-tier competition and season; do not confuse with other lower Spanish divisions. |
| Spain — Copa del Rey | observed_competition_077: Copa del Rey; observed_competition_084: Spanish Copa del Rey | bzzoiro 41 (41::2052; 20 obs)<br>livescore_football 3951 (3951::2026; 5 obs) | 25 | Confirm same national cup and season; compare draw/round fixture lists. |
| Spain — Liga F | observed_competition_080: Liga F; observed_competition_087: Spanish Liga F | bzzoiro 36 (36::1308; 27 obs)<br>livescore_football 20956 (20956::2026; 9 obs) | 36 | Confirm women's top-tier identity and season; compare clubs and fixtures. |
| Europe — UEFA Nations League | observed_competition_035: Nations League A; observed_competition_037: UEFA Nations League | openligadb 5978 (5978::2026; 144 obs)<br>bzzoiro 64 (64::1430; 122 obs) | 266 | Do not merge until Nations League A is shown to be the same scope as the broader UEFA Nations League source. |

## Review priorities

1. First compare the single-provider aliases attached to existing Priority A groups: England Premier League, England Championship, France Ligue 1, Germany Bundesliga and Spain LaLiga. Those already have multi-provider external evidence; the new provider IDs still need their own exact fixture corroboration.
2. Next compare Brazil Série A, Argentina Liga Profesional, Belgium Pro League, England League One/Two/National League, Japan J1, Spain Segunda, Copa del Rey and Liga F.
3. Keep Mexico Liga MX and UEFA Nations League as special-scope checks. The Apertura phase may not equal a provider's whole-season league record, and Nations League A is a narrower competition scope than the general Nations League label.

## Evidence gates before any link

- Exact normalized home and away teams plus timezone-aware UTC kickoff overlap; record at least two independent fixture overlaps where possible.
- Official federation/league source confirms competition identity, country/region, gender/age group, tier, format and season.
- Full or representative participant lists match the official season; reserve teams and women's teams must not be conflated with senior men's sides.
- Season start/end boundaries and competition phase must match. Calendar-year seasons, 2026/27 seasons, Apertura/Clausura stages and cup rounds are not interchangeable.
- Any ambiguous, single-fixture-only or name-only match remains unlinked.
- Human approval is required before canonical/provider/season/team links or fixture ingestion are enabled.

## Exclusions and cautions

- Friendly collections, club friendlies, international friendlies and generic tournament buckets are not domestic league identities.
- A source called `Pro League`, `League One`, `Liga 1`, `Super League` or similar must retain its country and provider context; names are not globally unique.
- The Spanish and Mexican league labels require special care around gender, division and phase.
- The European Nations League A record must not be automatically equated with a broader Nations League record.

## Data-write outcome

This document is a review queue only. It does not modify `identity_review_queue.json`, canonical competitions, provider links, seasons, teams, fixtures, future-fixture routing or the prediction ledger.

**Current result:** 17 likely alias groups are identified from the 87 single-provider entries. The remaining Priority B entries stay individually held until reviewed. The next actual resolution step is to obtain full provider fixture/team observations for each group and run exact cross-provider comparisons.
