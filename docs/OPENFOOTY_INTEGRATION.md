# OpenFooty request client

The application now has a small client for dispatching a fixture preflight to
the dedicated OpenFooty workflow and retrieving its response artifact.

## Current state

This is a reusable integration client, not yet connected to the prediction
button. The engine's current response is BLOCKED_NOT_PREDICTION_READY. No
OpenFooty data is merged into prediction inputs, and no prediction weights,
provider priorities, or TVD logic are changed.

## Required secret when the UI integration is enabled

Add OPENFOOTY_GITHUB_TOKEN to Streamlit Community Cloud secrets only after
reviewing the token scope. It needs the minimum GitHub repository permissions
to dispatch a workflow and read its run/artifact. Do not reuse or expose
provider API keys. Never commit the token.

The client calls only the dedicated workflow:
jacksonader003-ship-it/OpenFooty-Data-Engine
.github/workflows/prediction-fixture-request.yml

It does not invoke the scheduled collector and does not call football
providers. It validates the six-field request, correlates the workflow run by
request ID, downloads the short-lived artifact, and checks the response ID.

## Activation requirements

Do not wire the client into automatic prediction execution until the engine
has a targeted collection handler and at least one current-season source has
passed rights, freshness, identity, and prediction-use qualification. The
prediction app must continue to reject unverified, stale, conflicting, or
held observations.
