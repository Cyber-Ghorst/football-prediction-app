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
OpenFooty-Data-Engine/OpenFooty-Data-Engine
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


## Read-only catalogue panel

The app now exposes an optional **OpenFooty stored fixture search — read-only** panel. It calls the dedicated current-season catalogue workflow, displays source-calendar date candidates and allows the user to inspect one candidate's fixture-specific stored-data response.

The panel requires `OPENFOOTY_GITHUB_TOKEN` in Streamlit Secrets. It does not run automatically on page load, does not replace the existing provider-based fixture selector, does not merge OpenFooty data into prediction profiles, and does not create a forecast. It is a separate diagnostic/search path while the full fixture-selection and model integration is qualified.

Catalogue rows deliberately retain `lifecycle_status=unknown` and `prediction_ready=false`. Missing kickoff timezone is displayed as missing; the UI never converts source-local time to UTC by guessing. The fixture inspection action can return `DATA_INCOMPLETE`; even `DATA_AVAILABLE` remains subject to the existing strict component-readiness gate.
