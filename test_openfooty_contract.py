import copy
import json
from pathlib import Path

import pytest

from openfooty_contract import OpenFootyContractError, validate_openfooty_response


ROOT = Path(__file__).resolve().parent
EXAMPLE = json.loads(
    (ROOT / "contracts" / "examples" / "prediction-data-response.v1.example.json")
    .read_text(encoding="utf-8")
)


def test_valid_golden_response_is_accepted_without_mutating_input():
    payload = copy.deepcopy(EXAMPLE)
    before = copy.deepcopy(payload)
    result = validate_openfooty_response(payload, expected_request_id="request-20261128-001")
    assert result == payload
    assert payload == before
    assert result is not payload


def test_request_correlation_mismatch_is_rejected():
    with pytest.raises(OpenFootyContractError, match="does not match"):
        validate_openfooty_response(EXAMPLE, expected_request_id="request-20261128-999")


def test_data_available_requires_fixture_and_both_matching_team_profiles():
    payload = copy.deepcopy(EXAMPLE)
    payload["team_profiles"]["away"]["team_id"] = "wrong-team"
    with pytest.raises(OpenFootyContractError, match="does not match"):
        validate_openfooty_response(payload, expected_request_id=EXAMPLE["request_id"])


def test_non_utc_kickoff_is_rejected():
    payload = copy.deepcopy(EXAMPLE)
    payload["fixture"]["kickoff_at_utc"] = "2026-11-29T15:00:00+03:00"
    with pytest.raises(OpenFootyContractError, match="ending in Z"):
        validate_openfooty_response(payload, expected_request_id=EXAMPLE["request_id"])


def test_invalid_provenance_digest_is_rejected():
    payload = copy.deepcopy(EXAMPLE)
    payload["fixture"]["source_provenance"][0]["payload_sha256"] = "not-a-hash"
    with pytest.raises(OpenFootyContractError, match="SHA-256"):
        validate_openfooty_response(payload, expected_request_id=EXAMPLE["request_id"])


def test_invalid_or_non_finite_numeric_observation_is_rejected():
    payload = copy.deepcopy(EXAMPLE)
    payload["team_profiles"]["home"]["recent_matches"][0]["goals_for"] = float("nan")
    with pytest.raises(OpenFootyContractError, match="finite"):
        validate_openfooty_response(payload, expected_request_id=EXAMPLE["request_id"])


def test_unsupported_contract_version_is_rejected():
    payload = copy.deepcopy(EXAMPLE)
    payload["contract_version"] = "openfooty-prediction-data-v2"
    with pytest.raises(OpenFootyContractError, match="version"):
        validate_openfooty_response(payload, expected_request_id=EXAMPLE["request_id"])
