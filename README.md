# Football Prediction Lab — Layer 2

This version adds automatic data collection from API-Football v3 while retaining the Layer 1 prediction model and `tvd.py` rules-based Tactical Vulnerability Detector.

## Files
- `app.py` — Streamlit interface and data workflow
- `engine.py` — weighted prediction engine with explicit missing-data handling
- `tvd.py` — keep the existing Layer 1 file unchanged
- `api_football.py` — dedicated API-Football v3 client
- `api_ninjas.py` — separate API Ninjas client
- `highlightly.py` — separate Highlightly client
- `data_layer2.py` — fixture normalization and team profile collection
- `form_analyzer.py` — last-10 form, goals and venue performance
- `strength_analyzer.py` — opponent-strength values from competition standings
- `availability.py` — injury/lineup summaries; no invented availability score
- `tactical_indicators.py` — conservative indicators from available match statistics

## Install and configure
1. Copy the files into the repository root, replacing `app.py` and `engine.py` and adding the new modules. Keep the existing `tvd.py` and `sample_teams.json`.
2. Set Streamlit Community Cloud → App → Settings → Secrets:

```toml
APISPORTS_API_KEY = "YOUR_API_SPORTS_KEY"
```

3. Ensure `requirements.txt` contains the supplied dependencies and redeploy/reboot the app.

## Important data notes
- API-Football plan coverage and request limits vary. Match statistics may require one API request per fixture; turn off the statistics option to reduce calls.
- A 2026/27 season is usually represented by season `2026`; select a season supported by the API plan.
- The provider may not return a full ten completed matches early in a season. The prediction is blocked below five matches.
- Injury reports are shown, but no availability rating is fabricated from raw injury counts.
- Tactical metrics are calculated only from statistics actually returned. TVD remains available for evidence-based manual ratings.
- Probabilities are model estimates, not guarantees. Backtest and calibrate before using for decisions.


## Provider configuration status

The Streamlit prediction workflow currently runs through API-Football v3. Configure APISPORTS_API_KEY in Streamlit Secrets. Optional independent adapter credentials are API_NINJAS_API_KEY and HIGHLIGHTLY_API_KEY; they are not yet wired as automatic fallbacks in the app. Do not configure a LiveScoreFootball key until its exact official API product and documentation URL are verified. Never commit provider keys.

See MULTI_SOURCE_API_ARCHITECTURE.md for provider responsibilities, reconciliation rules and remaining integration work.


## LiveScoreFootball read-only source

The project includes a read-only adapter for the public [LiveScoreFootball API](https://github.com/rezarahiminia/livescoreFootball), hosted at https://worldcup26.ir. Its documented public endpoints currently require no API key. Set LIVESCORE_FOOTBALL_BASE_URL only when using a different compatible deployment. The API reads stored MongoDB snapshots fed by a separate listener, so it is not a guaranteed real-time feed. Current documented coverage focuses on verified England and Spain competitions. The adapter is implemented but is not yet enabled as an automatic Layer 2 fallback. See MULTI_SOURCE_API_ARCHITECTURE.md.
