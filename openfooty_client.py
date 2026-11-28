"""Read-only GitHub Actions client for OpenFooty stored fixture data responses.

This client dispatches only the dedicated preflight workflow. It never calls
football providers, changes prediction inputs, or writes to either database.
"""
from __future__ import annotations

import io
import json
import re
import time
import zipfile
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests

from openfooty_contract import OpenFootyContractError, validate_openfooty_response


class OpenFootyTriggerError(RuntimeError):
    """Raised when an OpenFooty preflight request cannot be completed safely."""


class OpenFootyTriggerClient:
    API_ROOT = "https://api.github.com"
    REPOSITORY = "jacksonader003-ship-it/OpenFooty-Data-Engine"
    WORKFLOW = "prediction-fixture-request.yml"
    REQUEST_FIELDS = {
        "request_id", "competition_id", "season_id",
        "home_team", "away_team", "kickoff_date",
    }

    def __init__(
        self,
        token: str,
        *,
        session: requests.Session | None = None,
        timeout_seconds: int = 20,
        poll_interval_seconds: float = 3,
        max_wait_seconds: int = 120,
    ):
        if not isinstance(token, str) or not token.strip():
            raise OpenFootyTriggerError("OPENFOOTY_GITHUB_TOKEN is not configured.")
        self.token = token.strip()
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.max_wait_seconds = max_wait_seconds
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    @classmethod
    def validate_request(cls, request: dict[str, Any]) -> dict[str, str]:
        if not isinstance(request, dict) or set(request) != cls.REQUEST_FIELDS:
            raise OpenFootyTriggerError("Fixture request must contain exactly the six documented fields.")
        normalized: dict[str, str] = {}
        for field in cls.REQUEST_FIELDS:
            value = request[field]
            if not isinstance(value, str) or not value.strip():
                raise OpenFootyTriggerError(f"{field} must be a non-empty string.")
            normalized[field] = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,79}", normalized["request_id"]):
            raise OpenFootyTriggerError("request_id must be 8-80 safe identifier characters.")
        if len(normalized["home_team"]) > 100 or len(normalized["away_team"]) > 100:
            raise OpenFootyTriggerError("Team names must not exceed 100 characters.")
        if normalized["home_team"].casefold() == normalized["away_team"].casefold():
            raise OpenFootyTriggerError("Home and away teams must be different.")
        try:
            date.fromisoformat(normalized["kickoff_date"])
        except ValueError as error:
            raise OpenFootyTriggerError("kickoff_date must use YYYY-MM-DD.") from error
        return normalized

    def _url(self, path: str) -> str:
        return f"{self.API_ROOT}/repos/{self.REPOSITORY}/{path.lstrip('/')}"

    def _request(self, method: str, url: str, *, expected: tuple[int, ...], **kwargs):
        try:
            response = self.session.request(
                method, url, timeout=self.timeout_seconds, **kwargs
            )
        except requests.RequestException as error:
            raise OpenFootyTriggerError(
                f"OpenFooty GitHub request failed ({type(error).__name__})."
            ) from error
        if response.status_code not in expected:
            raise OpenFootyTriggerError(
                f"OpenFooty GitHub request returned HTTP {response.status_code}; "
                "check token permissions and repository access."
            )
        return response

    def request_preflight(self, fixture_request: dict[str, Any]) -> dict[str, Any]:
        request = self.validate_request(fixture_request)
        request_json = json.dumps(request, separators=(",", ":"), ensure_ascii=False)
        dispatch_url = self._url(f"actions/workflows/{self.WORKFLOW}/dispatches")
        self._request(
            "POST",
            dispatch_url,
            expected=(204,),
            json={
                "ref": "main",
                "inputs": {
                    "request_id": request["request_id"],
                    "request_json": request_json,
                },
            },
        )
        return self._wait_for_response(request["request_id"])

    def request_fixture_data(self, fixture_request: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a stored-data lookup and validate both returned response envelopes."""
        request = self.validate_request(fixture_request)
        request_json = json.dumps(request, separators=(",", ":"), ensure_ascii=False)
        dispatch_url = self._url(f"actions/workflows/{self.WORKFLOW}/dispatches")
        self._request(
            "POST",
            dispatch_url,
            expected=(204,),
            json={
                "ref": "main",
                "inputs": {
                    "request_id": request["request_id"],
                    "request_json": request_json,
                },
            },
        )
        return self._wait_for_data_response(request["request_id"])

    def _wait_for_data_response(self, request_id: str) -> dict[str, Any]:
        runs_url = self._url(
            f"actions/workflows/{self.WORKFLOW}/runs"
            "?event=workflow_dispatch&branch=main&per_page=30"
        )
        deadline = time.monotonic() + self.max_wait_seconds
        while time.monotonic() < deadline:
            response = self._request("GET", runs_url, expected=(200,))
            payload = response.json()
            matching = None
            for candidate in payload.get("workflow_runs", []):
                title = str(candidate.get("display_title") or candidate.get("name") or "")
                if request_id in title:
                    matching = candidate
                    break
            if matching and matching.get("status") == "completed":
                if matching.get("conclusion") != "success":
                    raise OpenFootyTriggerError(
                        "OpenFooty stored-data workflow did not complete successfully."
                    )
                return self._download_data_responses(matching, request_id)
            time.sleep(self.poll_interval_seconds)
        raise OpenFootyTriggerError(
            "Timed out waiting for the matching OpenFooty stored-data response."
        )

    def _download_data_responses(
        self, run: dict[str, Any], request_id: str
    ) -> dict[str, Any]:
        run_id = run.get("id")
        if not isinstance(run_id, int):
            raise OpenFootyTriggerError("OpenFooty returned a workflow run without a valid ID.")
        artifacts_url = self._url(f"actions/runs/{run_id}/artifacts")
        response = self._request("GET", artifacts_url, expected=(200,))
        artifact_name = f"prediction-request-{run_id}"
        artifacts = response.json().get("artifacts", [])
        artifact = next(
            (item for item in artifacts if item.get("name") == artifact_name and not item.get("expired")),
            None,
        )
        if not artifact or not artifact.get("archive_download_url"):
            raise OpenFootyTriggerError("OpenFooty stored-data response artifact is missing or expired.")
        archive_url = artifact["archive_download_url"]
        parsed_url = urlparse(archive_url)
        if parsed_url.scheme != "https" or parsed_url.hostname != "api.github.com":
            raise OpenFootyTriggerError("OpenFooty returned an unexpected artifact download host.")
        archive = self._request("GET", archive_url, expected=(200,))
        if len(archive.content) > 2_000_000:
            raise OpenFootyTriggerError("OpenFooty response ZIP exceeds the allowed download size.")
        try:
            with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
                def read_json_file(filename: str) -> dict[str, Any]:
                    matches = [name for name in bundle.namelist() if name.endswith(filename)]
                    if len(matches) != 1:
                        raise OpenFootyTriggerError(
                            f"Response artifact must contain exactly one {filename}."
                        )
                    if bundle.getinfo(matches[0]).file_size > 1_000_000:
                        raise OpenFootyTriggerError(
                            f"Response artifact file {filename} exceeds the allowed size."
                        )
                    value = json.loads(bundle.read(matches[0]).decode("utf-8"))
                    if not isinstance(value, dict):
                        raise OpenFootyTriggerError(
                            f"Response artifact file {filename} must contain a JSON object."
                        )
                    return value

                preflight = read_json_file("prediction_request_response.json")
                data_payload = read_json_file("prediction_data_response.json")
        except (zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise OpenFootyTriggerError(
                "OpenFooty response artifact is not valid JSON ZIP data."
            ) from error

        if preflight.get("request_id") != request_id:
            raise OpenFootyTriggerError("OpenFooty preflight request_id does not match this request.")
        if preflight.get("request_status") not in {
            "BLOCKED_NOT_PREDICTION_READY",
            "READY_FOR_STORED_DATA_PREDICTION",
            "REJECTED_INVALID_REQUEST",
        }:
            raise OpenFootyTriggerError("OpenFooty returned an unknown preflight status.")
        if (
            preflight.get("data_returned") is not False
            or preflight.get("prediction_ready") is not False
            or preflight.get("provider_requests_attempted") != 0
        ):
            raise OpenFootyTriggerError(
                "Preflight response indicates unexpected provider activity or prediction execution."
            )
        try:
            data_response = validate_openfooty_response(
                data_payload, expected_request_id=request_id
            )
        except OpenFootyContractError as error:
            raise OpenFootyTriggerError(
                f"OpenFooty data response failed contract validation: {error}"
            ) from error
        return {
            "preflight_response": preflight,
            "data_response": data_response,
            "workflow_run": {
                "id": run_id,
                "url": run.get("html_url"),
                "conclusion": run.get("conclusion"),
            },
        }

    def _wait_for_response(self, request_id: str) -> dict[str, Any]:
        runs_url = self._url(
            f"actions/workflows/{self.WORKFLOW}/runs"
            "?event=workflow_dispatch&branch=main&per_page=30"
        )
        deadline = time.monotonic() + self.max_wait_seconds
        run = None
        while time.monotonic() < deadline:
            response = self._request("GET", runs_url, expected=(200,))
            payload = response.json()
            for candidate in payload.get("workflow_runs", []):
                title = str(candidate.get("display_title") or candidate.get("name") or "")
                if request_id in title:
                    run = candidate
                    break
            if run and run.get("status") == "completed":
                return self._download_response(run, request_id)
            time.sleep(self.poll_interval_seconds)
        raise OpenFootyTriggerError(
            "Timed out waiting for the matching OpenFooty request run."
        )

    def _download_response(self, run: dict[str, Any], request_id: str) -> dict[str, Any]:
        run_id = run.get("id")
        if not isinstance(run_id, int):
            raise OpenFootyTriggerError("OpenFooty returned a workflow run without a valid ID.")
        artifacts_url = self._url(f"actions/runs/{run_id}/artifacts")
        response = self._request("GET", artifacts_url, expected=(200,))
        artifact_name = f"prediction-request-{run_id}"
        artifacts = response.json().get("artifacts", [])
        artifact = next(
            (item for item in artifacts if item.get("name") == artifact_name and not item.get("expired")),
            None,
        )
        if not artifact or not artifact.get("archive_download_url"):
            raise OpenFootyTriggerError("OpenFooty request response artifact is missing or expired.")
        archive_url = artifact["archive_download_url"]
        parsed_url = urlparse(archive_url)
        if parsed_url.scheme != "https" or parsed_url.hostname != "api.github.com":
            raise OpenFootyTriggerError("OpenFooty returned an unexpected artifact download host.")
        archive = self._request("GET", archive_url, expected=(200,))
        if len(archive.content) > 2_000_000:
            raise OpenFootyTriggerError("OpenFooty response ZIP exceeds the allowed download size.")
        try:
            with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
                matches = [
                    name for name in bundle.namelist()
                    if name.endswith("prediction_request_response.json")
                ]
                if len(matches) != 1:
                    raise OpenFootyTriggerError("Response artifact has an unexpected file layout.")
                if bundle.getinfo(matches[0]).file_size > 1_000_000:
                    raise OpenFootyTriggerError("Response artifact exceeds the allowed size.")
                result = json.loads(bundle.read(matches[0]).decode("utf-8"))
        except (zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise OpenFootyTriggerError("OpenFooty response artifact is not valid JSON ZIP data.") from error
        if result.get("request_id") != request_id:
            raise OpenFootyTriggerError("OpenFooty response request_id does not match this request.")
        if result.get("request_status") not in {
            "BLOCKED_NOT_PREDICTION_READY",
            "READY_FOR_QUALIFIED_COLLECTION",
            "REJECTED_INVALID_REQUEST",
        }:
            raise OpenFootyTriggerError("OpenFooty returned an unknown request status.")
        if result.get("data_returned") is not False or result.get("provider_requests_attempted") != 0:
            raise OpenFootyTriggerError("Preflight response unexpectedly contains data or provider activity.")
        result["workflow_run"] = {
            "id": run_id,
            "url": run.get("html_url"),
            "conclusion": run.get("conclusion"),
        }
        return result

    def close(self) -> None:
        self.session.close()
