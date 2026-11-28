"""Read-only validation for the pinned OpenFooty prediction-data response contract.

This module validates a response artifact only. It performs no network access,
provider collection, database writes, fixture mutation, or model calculation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import re
from typing import Any, Mapping

CONTRACT_VERSION = "openfooty-prediction-data-v1"
RESPONSE_STATUSES = {
    "DATA_AVAILABLE", "FIXTURE_NOT_FOUND", "FIXTURE_AMBIGUOUS",
    "DATA_INCOMPLETE", "ERROR",
}
PROVENANCE_STATUSES = {"verified", "accepted", "quarantined", "invalid", "conflict"}
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,79}$")
SHA256_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")


class OpenFootyContractError(ValueError):
    """Response does not conform to the supported OpenFooty contract."""


def _utc_timestamp(value: Any, field: str, *, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    if not isinstance(value, str) or not value.endswith("Z"):
        raise OpenFootyContractError(f"{field} must be an ISO-8601 UTC timestamp ending in Z.")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise OpenFootyContractError(f"{field} is not a valid ISO-8601 timestamp.") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise OpenFootyContractError(f"{field} must use UTC.")


def _number(value: Any, field: str, *, minimum: float | None = None,
            maximum: float | None = None, nullable: bool = True) -> None:
    if value is None and nullable:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OpenFootyContractError(f"{field} must be numeric" + (" or null." if nullable else "."))
    number = float(value)
    if not math.isfinite(number):
        raise OpenFootyContractError(f"{field} must be finite.")
    if minimum is not None and number < minimum:
        raise OpenFootyContractError(f"{field} is below its minimum {minimum}.")
    if maximum is not None and number > maximum:
        raise OpenFootyContractError(f"{field} is above its maximum {maximum}.")


def _provenance(rows: Any, field: str) -> None:
    if not isinstance(rows, list):
        raise OpenFootyContractError(f"{field} must be an array.")
    for index, item in enumerate(rows):
        path = f"{field}[{index}]"
        if not isinstance(item, Mapping):
            raise OpenFootyContractError(f"{path} must be an object.")
        if not isinstance(item.get("source_id"), str) or not item["source_id"].strip():
            raise OpenFootyContractError(f"{path}.source_id is required.")
        _utc_timestamp(item.get("retrieved_at_utc"), f"{path}.retrieved_at_utc")
        _utc_timestamp(item.get("source_updated_at_utc"), f"{path}.source_updated_at_utc", nullable=True)
        if item.get("validation_status") not in PROVENANCE_STATUSES:
            raise OpenFootyContractError(f"{path}.validation_status is unsupported.")
        digest = item.get("payload_sha256")
        if digest is not None and (not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest)):
            raise OpenFootyContractError(f"{path}.payload_sha256 must be a SHA-256 hex digest or null.")


def _team_profile(profile: Any, side: str, expected_team_id: str) -> None:
    field = f"team_profiles.{side}"
    if not isinstance(profile, Mapping):
        raise OpenFootyContractError(f"{field} must be an object for DATA_AVAILABLE.")
    for key in ("team_id", "team_name", "recent_matches", "availability", "source_provenance"):
        if key not in profile:
            raise OpenFootyContractError(f"{field}.{key} is required.")
    if str(profile["team_id"]) != str(expected_team_id):
        raise OpenFootyContractError(f"{field}.team_id does not match the selected fixture.")
    if not isinstance(profile["team_name"], str) or not profile["team_name"].strip():
        raise OpenFootyContractError(f"{field}.team_name must be non-empty.")
    if not isinstance(profile["recent_matches"], list):
        raise OpenFootyContractError(f"{field}.recent_matches must be an array.")
    _provenance(profile["source_provenance"], f"{field}.source_provenance")
    availability = profile["availability"]
    if not isinstance(availability, Mapping):
        raise OpenFootyContractError(f"{field}.availability must be an object.")
    if availability.get("status") not in {"verified", "partial", "unknown", "conflict", "invalid"}:
        raise OpenFootyContractError(f"{field}.availability.status is unsupported.")
    if not isinstance(availability.get("players"), list):
        raise OpenFootyContractError(f"{field}.availability.players must be an array.")
    _provenance(availability.get("source_provenance"), f"{field}.availability.source_provenance")
    for index, match in enumerate(profile["recent_matches"]):
        path = f"{field}.recent_matches[{index}]"
        if not isinstance(match, Mapping):
            raise OpenFootyContractError(f"{path} must be an object.")
        for key in ("fixture_id", "kickoff_at_utc", "venue", "goals_for",
                    "goals_against", "opponent_strength", "statistics", "source_provenance"):
            if key not in match:
                raise OpenFootyContractError(f"{path}.{key} is required.")
        if not isinstance(match["fixture_id"], str) or not match["fixture_id"].strip():
            raise OpenFootyContractError(f"{path}.fixture_id must be non-empty.")
        _utc_timestamp(match["kickoff_at_utc"], f"{path}.kickoff_at_utc")
        if match["venue"] not in {"home", "away", "neutral", "unknown"}:
            raise OpenFootyContractError(f"{path}.venue is unsupported.")
        _number(match["goals_for"], f"{path}.goals_for", minimum=0)
        _number(match["goals_against"], f"{path}.goals_against", minimum=0)
        _number(match["opponent_strength"], f"{path}.opponent_strength", minimum=0, maximum=100)
        if not isinstance(match["statistics"], Mapping):
            raise OpenFootyContractError(f"{path}.statistics must be an object.")
        for metric, value in match["statistics"].items():
            _number(value, f"{path}.statistics.{metric}", minimum=0)
        _provenance(match["source_provenance"], f"{path}.source_provenance")


def validate_openfooty_response(
    payload: Mapping[str, Any],
    *,
    expected_request_id: str,
) -> dict[str, Any]:
    """Validate a contract response and return a detached JSON-safe copy."""
    if not isinstance(payload, Mapping):
        raise OpenFootyContractError("Response must be a JSON object.")
    allowed = {
        "contract_version", "request_id", "generated_at_utc", "response_status",
        "fixture", "team_profiles", "diagnostics", "error",
    }
    required = {
        "contract_version", "request_id", "generated_at_utc", "response_status",
        "fixture", "team_profiles", "diagnostics",
    }
    missing = sorted(required - set(payload))
    extra = sorted(set(payload) - allowed)
    if missing:
        raise OpenFootyContractError("Response is missing required fields: " + ", ".join(missing))
    if extra:
        raise OpenFootyContractError("Response contains unsupported fields: " + ", ".join(extra))
    if payload.get("contract_version") != CONTRACT_VERSION:
        raise OpenFootyContractError("Unsupported OpenFooty contract version.")
    request_id = payload.get("request_id")
    if not isinstance(request_id, str) or not REQUEST_ID_PATTERN.fullmatch(request_id):
        raise OpenFootyContractError("request_id is invalid.")
    if request_id != expected_request_id:
        raise OpenFootyContractError("Response request_id does not match the originating request.")
    _utc_timestamp(payload.get("generated_at_utc"), "generated_at_utc")
    status = payload.get("response_status")
    if status not in RESPONSE_STATUSES:
        raise OpenFootyContractError("response_status is unsupported.")

    fixture = payload.get("fixture")
    profiles = payload.get("team_profiles")
    if not isinstance(profiles, Mapping) or set(profiles) != {"home", "away"}:
        raise OpenFootyContractError("team_profiles must contain exactly home and away.")
    if status == "DATA_AVAILABLE" and not isinstance(fixture, Mapping):
        raise OpenFootyContractError("DATA_AVAILABLE requires one identified fixture.")
    if fixture is not None:
        if not isinstance(fixture, Mapping):
            raise OpenFootyContractError("fixture must be an object or null.")
        fixture_fields = (
            "fixture_id", "competition_id", "season_id", "home_team_id",
            "away_team_id", "home_team", "away_team", "kickoff_at_utc",
            "status", "source_provenance",
        )
        for key in fixture_fields:
            if key not in fixture:
                raise OpenFootyContractError(f"fixture.{key} is required.")
        for key in ("fixture_id", "competition_id", "season_id", "home_team_id",
                    "away_team_id", "home_team", "away_team"):
            if not isinstance(fixture[key], str) or not fixture[key].strip():
                raise OpenFootyContractError(f"fixture.{key} must be non-empty.")
        if fixture["home_team_id"] == fixture["away_team_id"]:
            raise OpenFootyContractError("Fixture home and away team IDs must differ.")
        _utc_timestamp(fixture["kickoff_at_utc"], "fixture.kickoff_at_utc")
        if fixture["status"] not in {"scheduled", "postponed", "cancelled", "live", "completed", "unknown"}:
            raise OpenFootyContractError("fixture.status is unsupported.")
        _provenance(fixture["source_provenance"], "fixture.source_provenance")
        if status == "DATA_AVAILABLE":
            _team_profile(profiles.get("home"), "home", fixture["home_team_id"])
            _team_profile(profiles.get("away"), "away", fixture["away_team_id"])
    elif status == "DATA_AVAILABLE":
        raise OpenFootyContractError("DATA_AVAILABLE cannot have a null fixture.")

    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, Mapping):
        raise OpenFootyContractError("diagnostics must be an object.")
    for key in ("missing_fields", "invalid_observations", "conflicts", "warnings"):
        if not isinstance(diagnostics.get(key), list):
            raise OpenFootyContractError(f"diagnostics.{key} must be an array.")

    if "error" in payload and payload["error"] is not None:
        error = payload["error"]
        if not isinstance(error, Mapping) or not isinstance(error.get("code"), str) or not isinstance(error.get("message"), str):
            raise OpenFootyContractError("error must contain string code and message.")
    try:
        import json
        return json.loads(json.dumps(dict(payload), ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError):
        raise OpenFootyContractError("Response must contain only finite JSON values.") from None
