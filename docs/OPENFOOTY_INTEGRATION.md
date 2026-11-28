# OpenFooty request client

The application has a small client for dispatching a selected-fixture request to
the dedicated OpenFooty workflow and retrieving both its preflight and versioned
data-response artifact.

## Current state

This is a reusable integration client, not yet connected to the prediction
button. The preflight remains BLOCKED_NOT_PREDICTION_READY while model execution
is disabled. The workflow now separately returns an `openfooty-prediction-data-v1`
response from a recent canonical CSV artifact. The client validates the contract,
request correlation, provenance shape and UTC timestamps. No OpenFooty data is
yet merged into prediction inputs, and no prediction weights, provider priorities,
or TVD logic are changed.

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
request ID, downloads the short-lived artifact, verifies the preflight safety
flags, and validates the data response against the pinned v1 contract. The engine
selects only a successful canonical collection artifact no older than 36 hours;
missing or stale snapshots return a structured error. A `DATA_AVAILABLE` status
is not a model-readiness decision.

## Activation requirements

Do not wire the client into automatic prediction execution until the app-side
fixture catalogue/search path, freshness validation, cross-repository golden
tests, and strict component-readiness integration are complete. The prediction
app must continue to reject unverified, stale, conflicting, or held observations.
The current OpenFooty CSV fixture data may still lack verified timezone/kickoff
instants; such rows correctly return `DATA_INCOMPLETE` and must not be guessed.
