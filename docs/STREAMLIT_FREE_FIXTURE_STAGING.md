# Streamlit free-fixture observation staging

The Provider Readiness expander includes a manual staging control for the five
selected free fixture sources.

- Select the source outside the form so the relevant source fields rerender.
- OpenLigaDB requires a league shortcut and season.
- OpenFootball requires a football.json season file and display name.
- Open Matchday requires a CSV URL, competition/season labels and an explicit
  acknowledgement of its non-commercial-only licence.
- LiveScoreFootball requires a league slug and UTC date range.
- Bzzoiro requires BZZOIRO_API_TOKEN in Streamlit Secrets.

A successful run archives normalized observations in CockroachDB. The result
shows the observation count, the count eligible for crosswalk review and any
scope errors. Eligibility is not canonical acceptance: timezone, status,
identity, freshness, licence and crosswalk checks still apply.

The staging action does not update upcoming_fixture_staging, football_fixtures,
the prediction model or the Neon prediction ledger. It reports zero canonical
fixture writes and zero prediction-ledger writes.
