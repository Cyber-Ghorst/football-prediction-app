"""Fail-closed, read-only readiness assessment for OpenFooty v1 responses.

This module deliberately does not construct prediction scores or invoke the model.
The v1 contract currently carries evidence, not every approved app-side score.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Mapping

from openfooty_contract import (
    OpenFootyContractError,
    validate_openfooty_response,
)

TOP_LEVEL = (
    "recent_form",
    "goals_scored",
    "goals_conceded",
    "home_away",
    "strength_of_schedule",
    "player_availability",
    "tactical",
)
TACTICAL = (
    "playing_style",
    "defensive_structure",
    "attacking_approach",
    "tactical_compatibility",
)


def _parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be ISO-8601 UTC ending in Z")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("timestamp must be UTC")
    return parsed


def _usable_provenance(rows: Any) -> bool:
    return (
        isinstance(rows, list)
        and bool(rows)
        and all(
            isinstance(row, Mapping)
            and row.get("validation_status") in {"verified", "accepted"}
            for row in rows
        )
    )


def _freshness_blockers(
    rows: Any,
    *,
    now: datetime,
    max_age_hours: float | None,
    field: str,
) -> list[str]:
    if max_age_hours is None:
        return [f"{field}:freshness_policy_not_supplied"]
    if not isinstance(rows, list) or not rows:
        return [f"{field}:source_provenance_missing"]
    blockers: list[str] = []
    for index, row in enumerate(rows):
        try:
            retrieved = _parse_utc(row["retrieved_at_utc"])
        except (KeyError, TypeError, ValueError):
            blockers.append(f"{field}:invalid_retrieval_timestamp[{index}]")
            continue
        age = (now - retrieved).total_seconds() / 3600
        if age < 0:
            blockers.append(f"{field}:future_retrieval_timestamp[{index}]")
        elif age > max_age_hours:
            blockers.append(f"{field}:stale_evidence[{index}]")
    return blockers


def assess_openfooty_readiness(
    payload: Mapping[str, Any],
    *,
    expected_request_id: str,
    now_utc: str | None = None,
    freshness_limits_hours: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Validate and report readiness without imputing or calculating model scores.

    freshness_limits_hours may define separate `fixture`, `availability` and
    `history` limits. Missing limits fail closed rather than silently assuming freshness.
    """
    response = validate_openfooty_response(
        payload, expected_request_id=expected_request_id
    )
    now = _parse_utc(now_utc) if now_utc else datetime.now(timezone.utc)
    limits = dict(freshness_limits_hours or {})
    for key, value in limits.items():
        if key not in {"fixture", "availability", "history"}:
            raise ValueError(f"unsupported freshness policy key: {key}")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"freshness limit for {key} must be a finite positive number")
    blockers: list[str] = []
    fixture = response.get("fixture")
    if response["response_status"] != "DATA_AVAILABLE" or not isinstance(fixture, Mapping):
        blockers.append(f"engine_response:{response['response_status']}")
    elif fixture.get("status") != "scheduled":
        blockers.append(f"fixture:lifecycle_not_scheduled:{fixture.get('status')}")

    diagnostics = response["diagnostics"]
    for field in ("missing_fields", "invalid_observations", "conflicts"):
        if diagnostics[field]:
            blockers.append(f"engine_diagnostics:{field}")

    if isinstance(fixture, Mapping):
        if not _usable_provenance(fixture.get("source_provenance")):
            blockers.append("fixture:provenance_not_eligible")
        blockers.extend(_freshness_blockers(
            fixture.get("source_provenance"),
            now=now,
            max_age_hours=limits.get("fixture"),
            field="fixture",
        ))

    teams: dict[str, Any] = {}
    kickoff = _parse_utc(fixture["kickoff_at_utc"]) if isinstance(fixture, Mapping) else None
    for side in ("home", "away"):
        profile = response["team_profiles"][side]
        matches = profile.get("recent_matches", [])
        valid_matches = []
        chronology_ok = True
        previous: datetime | None = None
        if "history" not in limits:
            blockers.append(f"{side}:recent_history:freshness_policy_not_supplied")
        for index, match in enumerate(matches):
            if "history" in limits:
                blockers.extend(_freshness_blockers(
                    match.get("source_provenance"),
                    now=now,
                    max_age_hours=limits["history"],
                    field=f"{side}:recent_match[{index}]",
                ))
            try:
                timestamp = _parse_utc(match["kickoff_at_utc"])
            except (KeyError, TypeError, ValueError):
                chronology_ok = False
                blockers.append(f"{side}:recent_match_invalid_utc[{index}]")
                continue
            if kickoff is not None and timestamp >= kickoff:
                chronology_ok = False
                blockers.append(f"{side}:recent_match_not_pre_kickoff[{index}]")
            if previous is not None and timestamp > previous:
                chronology_ok = False
                blockers.append(f"{side}:recent_matches_not_newest_first")
            previous = timestamp
            if not _usable_provenance(match.get("source_provenance")):
                blockers.append(f"{side}:recent_match_provenance_not_eligible[{index}]")
            if match.get("goals_for") is not None and match.get("goals_against") is not None:
                valid_matches.append(match)

        five_valid = len(valid_matches) >= 5 and chronology_ok
        schedule_count = sum(
            match.get("opponent_strength") is not None for match in valid_matches[:10]
        )
        stats_count = sum(
            bool(match.get("statistics")) for match in valid_matches[:10]
        )
        availability = profile.get("availability", {})
        availability_verified = (
            isinstance(availability, Mapping)
            and availability.get("status") == "verified"
            and bool(availability.get("players"))
            and _usable_provenance(availability.get("source_provenance"))
        )
        availability_freshness = _freshness_blockers(
            availability.get("source_provenance") if isinstance(availability, Mapping) else None,
            now=now,
            max_age_hours=limits.get("availability"),
            field=f"{side}:availability",
        )
        blockers.extend(availability_freshness)

        tactical_status = {name: False for name in TACTICAL}
        component_status = {
            "recent_form": five_valid,
            "goals_scored": five_valid,
            "goals_conceded": five_valid,
            # The v1 response has venue observations, not the approved venue rating.
            "home_away": False,
            "strength_of_schedule": schedule_count >= 5,
            # Verified availability evidence is not itself an approved impact score.
            "player_availability": False,
            "tactical": False,
        }
        team_blockers = []
        if not five_valid:
            team_blockers.append("at_least_five_valid_pre_kickoff_matches_required")
        if schedule_count < 5:
            team_blockers.append("opponent_strength_evidence_insufficient")
        if stats_count == 0:
            team_blockers.append("recent_match_statistics_missing")
        if not availability_verified:
            team_blockers.append("player_availability_not_verified")
        else:
            team_blockers.append("availability_impact_score_not_defined_in_v1")
        team_blockers.extend([
            "home_away_rating_not_supplied_by_v1",
            "playing_style_evidence_not_supplied_by_v1",
            "defensive_structure_evidence_not_supplied_by_v1",
            "attacking_approach_evidence_not_supplied_by_v1",
            "fixture_specific_tactical_compatibility_not_supplied",
        ])
        for name, ready in component_status.items():
            if not ready:
                blockers.append(f"{side}:component_missing:{name}")
        teams[side] = {
            "team_id": profile.get("team_id"),
            "team_name": profile.get("team_name"),
            "valid_pre_kickoff_match_count": len(valid_matches),
            "opponent_strength_observation_count": schedule_count,
            "matches_with_statistics_count": stats_count,
            "availability_evidence_verified": availability_verified,
            "top_level_components": component_status,
            "tactical_subcomponents": tactical_status,
            "missing_components": [key for key, ready in component_status.items() if not ready],
            "missing_tactical_subcomponents": list(TACTICAL),
            "blockers": team_blockers,
        }

    return {
        "readiness_policy_version": "openfooty-v1-strict-readiness-1",
        "contract_version": response["contract_version"],
        "request_id": response["request_id"],
        "response_status": response["response_status"],
        "fixture": dict(fixture) if isinstance(fixture, Mapping) else None,
        "status": "eligible" if not blockers else "blocked",
        "prediction_enabled": False,
        "prediction_executed": False,
        "ledger_write_performed": False,
        "weights_redistributed": False,
        "missing_data_imputed": False,
        "required_top_level_components": list(TOP_LEVEL),
        "required_tactical_subcomponents": list(TACTICAL),
        "teams": teams,
        "blockers": sorted(set(blockers)),
        "diagnostics": response["diagnostics"],
        "freshness_limits_hours": dict(limits),
        "freshness_policy_complete": {"fixture", "availability", "history"}.issubset(limits),
    }
