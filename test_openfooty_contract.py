import copy
import json
import unittest
from pathlib import Path

from openfooty_contract import OpenFootyContractError, validate_openfooty_response


ROOT = Path(__file__).resolve().parent
EXAMPLE = json.loads(
    (ROOT / "contracts" / "examples" / "prediction-data-response.v1.example.json")
    .read_text(encoding="utf-8")
)


class OpenFootyContractTests(unittest.TestCase):
    def test_valid_golden_response_is_accepted_without_mutating_input(self):
        payload = copy.deepcopy(EXAMPLE)
        before = copy.deepcopy(payload)
        result = validate_openfooty_response(
            payload, expected_request_id="request-20261128-001"
        )
        self.assertEqual(result, payload)
        self.assertEqual(payload, before)
        self.assertIsNot(result, payload)

    def test_request_correlation_mismatch_is_rejected(self):
        with self.assertRaisesRegex(OpenFootyContractError, "does not match"):
            validate_openfooty_response(
                EXAMPLE, expected_request_id="request-20261128-999"
            )

    def test_data_available_requires_matching_team_profiles(self):
        payload = copy.deepcopy(EXAMPLE)
        payload["team_profiles"]["away"]["team_id"] = "wrong-team"
        with self.assertRaisesRegex(OpenFootyContractError, "does not match"):
            validate_openfooty_response(
                payload, expected_request_id=EXAMPLE["request_id"]
            )

    def test_non_utc_kickoff_is_rejected(self):
        payload = copy.deepcopy(EXAMPLE)
        payload["fixture"]["kickoff_at_utc"] = "2026-11-29T15:00:00+03:00"
        with self.assertRaisesRegex(OpenFootyContractError, "ending in Z"):
            validate_openfooty_response(
                payload, expected_request_id=EXAMPLE["request_id"]
            )

    def test_invalid_provenance_digest_is_rejected(self):
        payload = copy.deepcopy(EXAMPLE)
        payload["fixture"]["source_provenance"][0]["payload_sha256"] = "not-a-hash"
        with self.assertRaisesRegex(OpenFootyContractError, "SHA-256"):
            validate_openfooty_response(
                payload, expected_request_id=EXAMPLE["request_id"]
            )

    def test_invalid_or_non_finite_numeric_observation_is_rejected(self):
        payload = copy.deepcopy(EXAMPLE)
        payload["team_profiles"]["home"]["recent_matches"][0]["goals_for"] = float("nan")
        with self.assertRaisesRegex(OpenFootyContractError, "finite"):
            validate_openfooty_response(
                payload, expected_request_id=EXAMPLE["request_id"]
            )

    def test_unsupported_contract_version_is_rejected(self):
        payload = copy.deepcopy(EXAMPLE)
        payload["contract_version"] = "openfooty-prediction-data-v2"
        with self.assertRaisesRegex(OpenFootyContractError, "version"):
            validate_openfooty_response(
                payload, expected_request_id=EXAMPLE["request_id"]
            )


if __name__ == "__main__":
    unittest.main()
