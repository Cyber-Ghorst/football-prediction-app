# Football Prediction Lab — Layer 1

A working Streamlit web prototype for the agreed weighted football prediction model.

## Run it

Requires Python 3.10+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Streamlit prints a local URL (usually http://localhost:8501). On Android, the app can be run on a cloud host such as Streamlit Community Cloud after uploading this project to a Git repository.

## Included
- Tactical Vulnerability Detector (TVD) v1, evaluated in both directions
- Seven defensive-weakness versus attacking-weapon matchups
- Evidence-confidence weighting and explicit missing-data handling
- TVD compatibility scores feed the existing tactical compatibility subcomponent (10% of the overall model)
- 1X2 probabilities (home/draw/away)
- Expected goals for each team
- Over 1.5, Over 2.5 and BTTS probabilities
- Five most likely correct scores
- Transparent component ratings and model weights
- Four demo teams and ten-match histories

## Model weights
| Component | Weight |
|---|---:|
| Recent form | 20% |
| Goals scored | 10% |
| Goals conceded | 10% |
| Home/away | 10% |
| Strength of schedule | 15% |
| Player availability | 5% |
| Tactical analysis | 30% |

Tactical analysis: playing style 6%, defensive structure 7%, attacking approach 7%, tactical compatibility 10%.

The latest five of the last ten matches receive 1.5x the weight of matches 6–10.

## Data format
Edit `sample_teams.json`. Each team needs:
- `name`
- `home_rating`, `away_rating`, `player_availability` (0–100)
- `playing_style`, `defensive_structure`, `attacking_approach`, `tactical_compatibility` (0–100)
- `matches`: at least five entries, newest first; ten recommended. Each entry has `goals_for`, `goals_against`, and optional `opponent_strength` (0–100).

`home_rating` and `away_rating` should be based on the team's home and away performance respectively. `tactical_compatibility` is a matchup-specific estimate; in Layer 2 we will calculate it from tactical and player data rather than asking for manual entry.

## Tactical Vulnerability Detector (TVD)

Enable TVD in the app to enter optional 0-100 ratings for each team's defensive vulnerabilities and attacking weapons. Vulnerability scores increase with defensive weakness; weapon scores increase with attacking capability. Blank values remain unknown and are excluded from the calculation. A team-level evidence-confidence slider is applied to the ratings entered for that team.

The detector evaluates both directions: home attack versus away defence, and away attack versus home defence. Each pairing score is `vulnerability × opponent weapon / 100`; the seven pairings are weighted 16%, 14%, 12%, 16%, 14%, 14%, and 14%. The weighted result is used as that team's tactical compatibility score (the existing 10% subcomponent). If a direction has insufficient TVD data, its existing manual tactical-compatibility slider is used as a fallback.

TVD ratings are diagnostic matchup scores, not probabilities of winning. This v1 is a rules-based engine: it does not independently watch video or fetch tactical statistics. Ratings must be based on evidence entered by the user or supplied by a future data provider. Confidence and coverage are shown so incomplete evidence is visible.

## Layer boundary
This is Layer 1: the prediction engine and interface. It does **not** yet fetch fixtures, results, injuries, lineups or tactical metrics automatically. Layer 2 will connect a football data provider, normalize team/competition identifiers, fetch recent match data and populate these profiles. Provider coverage and API limits will need to be checked before choosing the integration.

## Important limitations
- Demo data is illustrative, not current verified team data.
- The Poisson model assumes independent team goal counts and does not yet account for low-score correlation, red cards, game state or league-specific calibration.
- Probabilities are estimates, not guarantees or betting advice.
- Backtest on historical seasons and calibrate probability quality before real-world use.
