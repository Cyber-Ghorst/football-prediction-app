# Football Prediction Lab — Layer 2

This version adds automatic data collection from API-Football v3 while retaining the Layer 1 prediction model and `tvd.py` rules-based Tactical Vulnerability Detector.

## Files
- `app.py` — Streamlit interface and data workflow
- `engine.py` — weighted prediction engine with explicit missing-data handling
- `tvd.py` — keep the existing Layer 1 file unchanged
- `api_football.py` — API-Football v3 client
- `data_layer2.py` — fixture normalization and team profile collection
- `form_analyzer.py` — last-10 form, goals and venue performance
- `strength_analyzer.py` — opponent-strength values from competition standings
- `availability.py` — injury/lineup summaries; no invented availability score
- `tactical_indicators.py` — conservative indicators from available match statistics

## Install and configure
1. Copy the files into the repository root, replacing `app.py` and `engine.py` and adding the new modules. Keep the existing `tvd.py` and `sample_teams.json`.
2. Set Streamlit Community Cloud → App → Settings → Secrets:

```toml
API_FOOTBALL_KEY = "YOUR_API_FOOTBALL_KEY"
```

3. Ensure `requirements.txt` contains the supplied dependencies and redeploy/reboot the app.

## Important data notes
- API-Football plan coverage and request limits vary. Match statistics may require one API request per fixture; turn off the statistics option to reduce calls.
- A 2026/27 season is usually represented by season `2026`; select a season supported by the API plan.
- The provider may not return a full ten completed matches early in a season. The prediction is blocked below five matches.
- Injury reports are shown, but no availability rating is fabricated from raw injury counts.
- Tactical metrics are calculated only from statistics actually returned. TVD remains available for evidence-based manual ratings.
- Probabilities are model estimates, not guarantees. Backtest and calibrate before using for decisions.
