# API-Football 21 unmatched team records — 2026/27 scope review

**Review date:** 2026-11-16  
**Reference season requested by the source-stage code:** 2026 (2026/27)  
**Scope:** Read-only independent competition-membership review. No canonical IDs, provider links, or source-row updates are made.

## Finding

The 21 unmatched API-Football team rows are not age-group teams or unknown clubs. Independent official competition sources place all 21 in senior professional first-team competitions in 2026/27, but in lower divisions rather than the five top-flight competitions used by the current API Ninjas cross-provider comparison.

This explains why exact current top-flight catalogue corroboration is absent. It does **not** justify linking them to another club or approving them as current top-flight participants.

The API-Football source stage is configured with `CATALOGUE_REFERENCE_SEASON = 2026` and calls `/teams` with both `league` and `season`. API-Football documents that the season parameter filters team membership and that team IDs persist across seasons.

A fresh live audit on 2026-11-16 attempted all five `/teams?league=...&season=2026` requests. **All five were rejected** with the provider response: `Free plans do not have access to this season, try from 2022 to 2024.` The successful workflow report is [here](https://github.com/Cyber-Ghorst/football-prediction-app/actions/runs/43856310971). No live 2026/27 API-Football roster was returned, so the 21 persisted source rows cannot be treated as verified 2026/27 top-flight membership. The local `catalogue_reference_season=2026` marker is not sufficient evidence of the provider's actual response season.

The source-provenance audit subsequently confirmed that **all 98 stored API-Football team rows** carry `catalogue_reference_season=2024` (not just the 21 unmatched rows). The read-only report counts 98/98 under season 2024 and records `team_evidence_method=provider_league_season_team_catalogue`. This confirms that the entire stored API-Football team catalogue is a 2024 snapshot. The 21 unmatched rows are the subset that are no longer in the corresponding 2026/27 top-flight catalogues; the other 77 happen to have current API Ninjas name/competition corroboration.

The most likely explanation is that these team rows are legacy season memberships retained in the provider-source table because the current free plan cannot refresh the 2026 roster. The 21 records remain valid senior clubs, but the independent official 2026/27 sources place them outside the corresponding top-flight competitions. Do not delete the provider team entities; hold only their current top-flight membership and cross-provider association. The 2024 snapshot may still be retained as historical provider evidence, but it must never be presented as a 2026/27 roster.

## Record-by-record disposition

| API-Football ID | Team | Top-flight competition ID | Independently verified 2026/27 senior competition | Review status |
|---:|---|---:|---|---|
| 511 | Empoli | 135 (Serie A) | Serie BKT | Senior first team; not current Serie A |
| 504 | Hellas Verona | 135 (Serie A) | Serie BKT | Senior first team; not current Serie A |
| 547 | Girona | 140 (La Liga) | LaLiga Hypermotion | Senior first team; not current La Liga |
| 534 | Las Palmas | 140 (La Liga) | LaLiga Hypermotion | Senior first team; not current La Liga |
| 537 | Leganes | 140 (La Liga) | LaLiga Hypermotion | Senior first team; not current La Liga |
| 798 | Mallorca | 140 (La Liga) | LaLiga Hypermotion | Senior first team; not current La Liga |
| 720 | Valladolid | 140 (La Liga) | LaLiga Hypermotion | Senior first team; not current La Liga |
| 46 | Leicester | 39 (Premier League) | EFL League One | Senior first team; not current Premier League |
| 41 | Southampton | 39 (Premier League) | EFL Championship | Senior first team; not current Premier League |
| 48 | West Ham | 39 (Premier League) | EFL Championship | Senior first team; not current Premier League |
| 39 | Wolves | 39 (Premier League) | EFL Championship | Senior first team; not current Premier League |
| 112 | Metz | 61 (Ligue 1) | Ligue 2 BKT | Senior first team; not current Ligue 1 |
| 82 | Montpellier | 61 (Ligue 1) | Ligue 2 BKT | Senior first team; not current Ligue 1 |
| 83 | Nantes | 61 (Ligue 1) | Ligue 2 BKT | Senior first team; not current Ligue 1 |
| 93 | Reims | 61 (Ligue 1) | Ligue 2 BKT | Senior first team; not current Ligue 1 |
| 1063 | Saint Etienne | 61 (Ligue 1) | Ligue 2 BKT | Senior first team; not current Ligue 1 |
| 180 | 1. FC Heidenheim | 78 (Bundesliga) | 2. Bundesliga | Senior first team; not current Bundesliga |
| 186 | FC St. Pauli | 78 (Bundesliga) | 2. Bundesliga | Senior first team; not current Bundesliga |
| 191 | Holstein Kiel | 78 (Bundesliga) | 2. Bundesliga | Senior first team; not current Bundesliga |
| 176 | VfL Bochum | 78 (Bundesliga) | 2. Bundesliga | Senior first team; not current Bundesliga |
| 161 | VfL Wolfsburg | 78 (Bundesliga) | 2. Bundesliga | Senior first team; not current Bundesliga |

## Independent official evidence

- **Premier League / EFL:** The Premier League's official 2026/27 club list excludes Leicester, Southampton, West Ham and Wolves. The EFL's 2026/27 Championship listing includes Southampton, West Ham and Wolves; Leicester City's official 2026/27 fixtures identify League One.
  - https://www.premierleague.com/en/news/4365156/new-to-the-premier-league-heres-all-you-need-to-know
  - https://www.efl.com/competitions/efl-championship/
  - https://www.lcfc.com/fixtures-results/fixtures-list
- **Spain:** LALIGA's official 2026/27 Hypermotion club list includes Girona, Las Palmas, Leganes, Mallorca and Valladolid.
  - https://www.laliga.com/laliga-hypermotion/clubes
- **Italy:** Lega B's official 2026/27 Serie B standings include Hellas Verona; its official Empoli calendar identifies Empoli's 2026/27 Serie B fixtures.
  - https://www.legab.it/seriebkt/classifica
  - https://www.legab.it/seriebkt/calendario/2026-2027/stagione-regolare/empoli
- **France:** The LFP's official 2026/27 Ligue 2 calendar and club schedule material identify Metz, Montpellier, Nantes, Reims and Saint-Etienne as Ligue 2 participants.
  - https://ligue1.com/fr/articles/l1_article_5281-saison-26-27-le-calendrier-des-matchs-de-ligue-2-bkt
  - https://ligue1.com/fr/articles/l1_article_5343-les-dates-de-reprise-des-clubs-de-ligue-2-bkt
- **Germany:** The official Bundesliga 2 club list for 2026/27 includes Heidenheim, St. Pauli, Holstein Kiel, Bochum and Wolfsburg.
  - https://www.bundesliga.com/en/2bundesliga/clubs
- **API-Football season semantics:** Its documentation describes the `league` + `season` filters for `/teams` and notes that team IDs persist between seasons.
  - https://www.api-football.com/documentation-v3

## Safe disposition

1. Keep all 21 rows held from current top-flight cross-provider identity approval.
2. Classify their club nature as senior first-team clubs based on official professional-league participation; do not label them age-group or reserve teams.
3. Do not delete their provider team entities: the clubs are real and have valid persistent provider IDs.
4. Do not copy API Ninjas country/gender values to these rows without direct identity corroboration.
5. Do not retry the same 2026 requests on the current free plan. First determine whether API-Football access changes or whether another permitted source can verify current season membership. If access remains unavailable, preserve the 21 rows as historical provider entities and exclude them from current top-flight membership decisions.
6. Keep the 21 records held for cross-provider linking; their senior-club status is independently supported, but their API-Football current-season membership is not.

**Audit invariants:** 0 canonical IDs assigned; 0 provider links created; 0 source scope fields updated; prediction model and prediction ledger untouched.
