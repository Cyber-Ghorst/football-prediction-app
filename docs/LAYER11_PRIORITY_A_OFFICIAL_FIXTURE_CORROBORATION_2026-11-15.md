# Layer 11 — Priority A official fixture corroboration review

**Source:** `priority_a_provider_observation_audit/latest.json` generated 2026-11-15 16:33 UTC  
**Exact provider overlaps:** 20 across five Priority A competition groups  
**Official pair/date/kickoff corroboration:** 15  
**Official pair/date corroboration with kickoff timezone unresolved:** 5  
**Identity approvals / provider links created:** 0

## Summary

The read-only provider observation audit found 20 exact cross-provider overlaps based on the same home team, away team and normalized UTC kickoff. These are strong fixture-level observations, but competition and season identity remain separate questions.

Official competition schedules independently corroborate:

- Premier League: **2** fixtures.
- Bundesliga: **8** fixtures.
- Scottish Premiership: **4** fixtures.
- Saudi Pro League: **1** fixture.
- 2. Bundesliga: **5** pairings and dates, but the official page does not label its kickoff timezone.

## Officially confirmed pair, date and kickoff

| Competition | Fixture | UTC kickoff | Provider pair |
|---|---|---|---|
| Premier League | Aston Villa – Sunderland | 21 Nov, 15:00Z | Bzzoiro / OpenLigaDB |
| Premier League | Hull City – Brighton & Hove Albion | 22 Nov, 14:00Z | Bzzoiro / OpenLigaDB |
| Bundesliga | Bayern München – 1. FC Köln | 20 Nov, 19:30Z | Bzzoiro / OpenLigaDB |
| Bundesliga | Union Berlin – RB Leipzig | 21 Nov, 14:30Z | Bzzoiro / OpenLigaDB |
| Bundesliga | Bayer Leverkusen – SC Paderborn | 21 Nov, 14:30Z | Bzzoiro / OpenLigaDB |
| Bundesliga | Eintracht Frankfurt – TSG Hoffenheim | 21 Nov, 14:30Z | Bzzoiro / OpenLigaDB |
| Bundesliga | SV Elversberg – SC Freiburg | 21 Nov, 14:30Z | Bzzoiro / OpenLigaDB |
| Bundesliga | Schalke 04 – VfB Stuttgart | 21 Nov, 17:30Z | Bzzoiro / OpenLigaDB |
| Bundesliga | FC Augsburg – Mainz 05 | 22 Nov, 14:30Z | Bzzoiro / OpenLigaDB |
| Bundesliga | Werder Bremen – Hamburger SV | 22 Nov, 16:30Z | Bzzoiro / OpenLigaDB |
| Scottish Premiership | Celtic – St. Mirren | 21 Nov, 15:00Z | Bzzoiro / LiveScoreFootball |
| Scottish Premiership | Hibernian – Dundee United | 21 Nov, 15:00Z | Bzzoiro / LiveScoreFootball |
| Scottish Premiership | Kilmarnock – Aberdeen | 21 Nov, 15:00Z | Bzzoiro / LiveScoreFootball |
| Scottish Premiership | Motherwell – Rangers | 21 Nov, 20:00Z | Bzzoiro / LiveScoreFootball |
| Saudi Pro League | Al Ahli – Al Nassr | 20 Nov, 17:30Z | Bzzoiro / LiveScoreFootball |

### Official sources

- Premier League full 2026/27 fixture list: https://www.premierleague.com/en/news/4675097/all-380-fixtures-for-season-2026-27
- Premier League November amendments clarify GMT and default 15:00 kickoffs: https://www.premierleague.com/en/news/4725574/fixture-amendments-for-premier-league-matches-in-november
- DFL official Bundesliga fixture table provides explicit UTC kickoff columns: https://products.bundesliga.com/fixtures
- SPFL official Premiership fixture list: https://spfl.co.uk/league/premiership/fixtures
- Saudi Pro League revised calendar: https://www.spl.com.sa/en/news/rsl-schedule-2026-27
- Saudi Pro League official schedule PDF gives Al Ahli–Al Nassr at 20:30 Saudi time, equivalent to 17:30 UTC: https://images.spl.com.sa/image/private/fl_attachment/prd/m54jmnwpd2embhoz8bvb.pdf

## 2. Bundesliga — pairings confirmed, UTC basis held

The DFL's official Matchday 12 page confirms all five home/away pairings and their dates:

- https://www.bundesliga.com/en/2bundesliga/matchday

However, the page displays kickoff times without an explicit timezone label. The provider parity audit records 12:00Z for the three Saturday fixtures and 12:30Z for the two Sunday fixtures. German local time in November is CET (UTC+1), so a possible one-hour local/UTC discrepancy remains. The official page confirms the fixture pairing and date, but it does not close the kickoff-time basis question. Keep these five out of the count of 15 fully UTC-confirmed overlaps.

## Identity decision

The 20 overlaps support the claim that these provider observations refer to the same individual fixture events, subject to the 2. Bundesliga timezone caveat. They do **not** independently prove that every provider competition ID or season ID has identical scope across the whole season.

- Competition identity approvals: **none**.
- Season identity approvals: **none**.
- Provider links created: **none**.
- Fixture or prediction writes: **none**.

Next step: keep the competition and season decisions separate, resolve the 2. Bundesliga timezone basis, and require a reviewed approval record before any cross-provider link is enabled.