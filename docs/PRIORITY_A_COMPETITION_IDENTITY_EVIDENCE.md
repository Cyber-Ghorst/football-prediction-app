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
