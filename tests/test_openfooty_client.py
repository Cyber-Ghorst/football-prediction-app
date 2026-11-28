import io
import json
import unittest
import zipfile
from pathlib import Path

from openfooty_client import OpenFootyTriggerClient, OpenFootyTriggerError


def request():
    return {
        "request_id": "prediction-req-0001",
        "competition_id": "eng-pl",
        "season_id": "eng-pl:2026-27",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "kickoff_date": "2026-12-01",
    }


class OpenFootyClientTests(unittest.TestCase):
    def test_request_validation_rejects_extra_fields(self):
        payload = request()
        payload["source"] = "sportsapipro"
        with self.assertRaises(OpenFootyTriggerError):
            OpenFootyTriggerClient.validate_request(payload)

    def test_request_validation_rejects_same_team(self):
        payload = request()
        payload["away_team"] = "Arsenal"
        with self.assertRaises(OpenFootyTriggerError):
            OpenFootyTriggerClient.validate_request(payload)

    def test_request_validation_accepts_exact_current_season_contract(self):
        self.assertEqual(OpenFootyTriggerClient.validate_request(request()), request())

    def test_dispatch_sends_only_the_dedicated_preflight_workflow(self):
        class Response:
            status_code = 204

        class Session:
            def __init__(self):
                self.headers = {}
                self.calls = []

            def request(self, method, url, **kwargs):
                self.calls.append((method, url, kwargs))
                return Response()

            def close(self):
                pass

        session = Session()
        client = OpenFootyTriggerClient("test-token", session=session)
        client._wait_for_response = lambda request_id: {"request_id": request_id}
        result = client.request_preflight(request())
        self.assertEqual(result["request_id"], request()["request_id"])
        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertTrue(url.endswith("/actions/workflows/prediction-fixture-request.yml/dispatches"))
        self.assertEqual(kwargs["json"]["ref"], "main")
        inputs = kwargs["json"]["inputs"]
        self.assertEqual(inputs["request_id"], request()["request_id"])
        self.assertEqual(json.loads(inputs["request_json"]), request())
        self.assertNotIn("test-token", json.dumps(kwargs))

    def test_artifact_reader_verifies_request_id(self):
        payload = {
            "request_id": request()["request_id"],
            "request_status": "BLOCKED_NOT_PREDICTION_READY",
            "data_returned": False,
            "provider_requests_attempted": 0,
        }
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as bundle:
            bundle.writestr("prediction_request_response.json", json.dumps(payload))

        class Response:
            def __init__(self, status_code=200, body=None, content=b""):
                self.status_code = status_code
                self._body = body or {}
                self.content = content

            def json(self):
                return self._body

        class Session:
            def __init__(self):
                self.headers = {}

            def request(self, method, url, **kwargs):
                if url.endswith("/artifacts"):
                    return Response(body={"artifacts": [{
                        "name": "prediction-request-123",
                        "expired": False,
                        "archive_download_url": "https://api.github.com/repos/example/repo/actions/artifacts/123/zip",
                    }]})
                if url.endswith("/actions/artifacts/123/zip"):
                    return Response(content=stream.getvalue())
                raise AssertionError(url)

            def close(self):
                pass

        client = OpenFootyTriggerClient("test-token", session=Session())
        result = client._download_response(
            {"id": 123, "html_url": "https://github.com/run", "conclusion": "success"},
            request()["request_id"],
        )
        self.assertEqual(result["request_status"], "BLOCKED_NOT_PREDICTION_READY")
        self.assertEqual(result["workflow_run"]["id"], 123)



    def test_data_response_artifact_validates_contract_and_correlation(self):
        request_id = request()["request_id"]
        preflight = {
            "request_id": request_id,
            "request_status": "BLOCKED_NOT_PREDICTION_READY",
            "data_returned": False,
            "prediction_ready": False,
            "provider_requests_attempted": 0,
        }
        data_payload = json.loads(
            (Path(__file__).parent.parent / "contracts" / "examples" /
             "prediction-data-response.v1.example.json").read_text(encoding="utf-8")
        )
        data_payload["request_id"] = request_id
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as bundle:
            bundle.writestr("prediction_request_response.json", json.dumps(preflight))
            bundle.writestr("prediction_data_response.json", json.dumps(data_payload))

        class Response:
            def __init__(self, body=None, content=b""):
                self.status_code = 200
                self._body = body or {}
                self.content = content

            def json(self):
                return self._body

        class Session:
            def __init__(self):
                self.headers = {}

            def request(self, method, url, **kwargs):
                if url.endswith("/artifacts"):
                    return Response(body={"artifacts": [{
                        "name": "prediction-request-123",
                        "expired": False,
                        "archive_download_url": "https://api.github.com/repos/example/repo/actions/artifacts/123/zip",
                    }]})
                if url.endswith("/actions/artifacts/123/zip"):
                    return Response(content=stream.getvalue())
                raise AssertionError(url)

            def close(self):
                pass

        client = OpenFootyTriggerClient("test-token", session=Session())
        result = client._download_data_responses(
            {"id": 123, "html_url": "https://github.com/run", "conclusion": "success"},
            request_id,
        )
        self.assertEqual(result["data_response"]["contract_version"], "openfooty-prediction-data-v1")
        self.assertEqual(result["data_response"]["request_id"], request_id)
        self.assertFalse(result["preflight_response"]["prediction_ready"])
        self.assertEqual(result["workflow_run"]["id"], 123)

    def test_data_response_artifact_rejects_wrong_contract_version(self):
        request_id = request()["request_id"]
        preflight = {
            "request_id": request_id,
            "request_status": "BLOCKED_NOT_PREDICTION_READY",
            "data_returned": False,
            "prediction_ready": False,
            "provider_requests_attempted": 0,
        }
        data_payload = {
            "contract_version": "openfooty-prediction-data-v2",
            "request_id": request_id,
            "generated_at_utc": "2026-11-28T08:00:00Z",
            "response_status": "ERROR",
            "fixture": None,
            "team_profiles": {"home": None, "away": None},
            "diagnostics": {
                "missing_fields": [], "invalid_observations": [],
                "conflicts": [], "warnings": []
            },
        }
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as bundle:
            bundle.writestr("prediction_request_response.json", json.dumps(preflight))
            bundle.writestr("prediction_data_response.json", json.dumps(data_payload))

        class Response:
            status_code = 200

            def __init__(self, body=None, content=b""):
                self._body = body or {}
                self.content = content

            def json(self):
                return self._body

        class Session:
            headers = {}

            def request(self, method, url, **kwargs):
                if url.endswith("/artifacts"):
                    return Response(body={"artifacts": [{
                        "name": "prediction-request-123", "expired": False,
                        "archive_download_url": "https://api.github.com/repos/example/repo/actions/artifacts/123/zip",
                    }]})
                if url.endswith("/actions/artifacts/123/zip"):
                    return Response(content=stream.getvalue())
                raise AssertionError(url)

            def close(self):
                pass

        client = OpenFootyTriggerClient("test-token", session=Session())
        with self.assertRaisesRegex(OpenFootyTriggerError, "contract validation"):
            client._download_data_responses(
                {"id": 123, "conclusion": "success"}, request_id
            )


if __name__ == "__main__":
    unittest.main()
