import io
import json
import zipfile

import pytest

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


def test_request_validation_rejects_extra_fields():
    payload = request()
    payload["source"] = "sportsapipro"
    with pytest.raises(OpenFootyTriggerError):
        OpenFootyTriggerClient.validate_request(payload)


def test_request_validation_rejects_same_team():
    payload = request()
    payload["away_team"] = "Arsenal"
    with pytest.raises(OpenFootyTriggerError):
        OpenFootyTriggerClient.validate_request(payload)


def test_request_validation_accepts_exact_current_season_contract():
    assert OpenFootyTriggerClient.validate_request(request()) == request()


def test_dispatch_sends_only_the_dedicated_preflight_workflow():
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
    assert result["request_id"] == request()["request_id"]
    method, url, kwargs = session.calls[0]
    assert method == "POST"
    assert url.endswith("/actions/workflows/prediction-fixture-request.yml/dispatches")
    assert kwargs["json"]["ref"] == "main"
    inputs = kwargs["json"]["inputs"]
    assert inputs["request_id"] == request()["request_id"]
    assert json.loads(inputs["request_json"]) == request()
    assert "test-token" not in json.dumps(kwargs)


def test_artifact_reader_verifies_request_id():
    payload = {"request_id": request()["request_id"], "request_status": "BLOCKED_NOT_PREDICTION_READY"}
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
            self.calls = 0

        def request(self, method, url, **kwargs):
            self.calls += 1
            if url.endswith("/artifacts"):
                return Response(body={"artifacts": [{
                    "name": "prediction-request-123",
                    "expired": False,
                    "archive_download_url": "https://artifact.example/download",
                }]})
            if url == "https://artifact.example/download":
                return Response(content=stream.getvalue())
            raise AssertionError(url)

        def close(self):
            pass

    client = OpenFootyTriggerClient("test-token", session=Session())
    result = client._download_response(
        {"id": 123, "html_url": "https://github.com/run", "conclusion": "success"},
        request()["request_id"],
    )
    assert result["request_status"] == "BLOCKED_NOT_PREDICTION_READY"
    assert result["workflow_run"]["id"] == 123
