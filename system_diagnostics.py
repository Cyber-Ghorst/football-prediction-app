"""Consolidated, read-only health diagnostics for the Streamlit prediction app."""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping


def _check(check_id: str, status: str, summary: str, recommendation: str | None = None) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": status,
        "summary": summary,
        "recommendation": recommendation,
    }


def _profile_integrity(profile: Mapping[str, Any]) -> dict[str, Any]:
    matches = profile.get("matches") or []
    fixture_ids = [
        str(row.get("fixture_id"))
        for row in matches
        if isinstance(row, Mapping) and row.get("fixture_id") is not None
    ]
    duplicate_ids = sorted({value for value in fixture_ids if fixture_ids.count(value) > 1})
    invalid_scores = []
    for row in matches:
        if not isinstance(row, Mapping):
            invalid_scores.append({"fixture_id": None, "reason": "match row is not an object"})
            continue
        for key in ("goals_for", "goals_against"):
            value = row.get(key)
            try:
                valid = value is not None and isfinite(float(value)) and float(value) >= 0
            except (TypeError, ValueError):
                valid = False
            if not valid:
                invalid_scores.append({
                    "fixture_id": row.get("fixture_id"),
                    "field": key,
                    "value": value,
                })
    return {
        "matches_checked": len(matches),
        "duplicate_fixture_ids": duplicate_ids,
        "invalid_or_missing_score_fields": invalid_scores,
    }


def build_system_diagnostics(
    *,
    season: int,
    competition: str,
    home_profile: Mapping[str, Any],
    away_profile: Mapping[str, Any],
    readiness: Mapping[str, Any],
    statistics_coverage: Mapping[str, Mapping[str, Any]],
    provider_configuration: list[Mapping[str, Any]],
    corroboration: Mapping[str, Any] | None = None,
    model_weights: Mapping[str, float] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a machine-readable diagnostic without changing model inputs.

    Provider connectivity is reported separately from credential configuration:
    this function does not make network requests or claim an API is reachable.
    """
    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    primary_id = "api_football" if int(season) <= 2024 else "sportmonks"
    providers = {
        str(row.get("provider_id")): dict(row)
        for row in provider_configuration
        if row.get("provider_id")
    }
    primary = providers.get(primary_id)
    checks: list[dict[str, Any]] = []
    if primary is None:
        checks.append(_check(
            "primary_provider_configuration", "unknown",
            f"Configuration details for the primary provider ({primary_id}) were not supplied.",
            "Check provider configuration before collecting data.",
        ))
    elif primary.get("credential_configured") is False:
        checks.append(_check(
            "primary_provider_configuration", "fail",
            f"The primary provider credential for {primary_id} is not configured.",
            f"Add the required {primary.get('credential_name') or 'provider credential'} in Streamlit Secrets.",
        ))
    else:
        checks.append(_check(
            "primary_provider_configuration", "pass",
            f"The selected season uses {primary_id}; its credential is configured. Connectivity is assessed separately.",
        ))

    fixture = dict(readiness.get("fixture") or {})
    if fixture.get("verified"):
        checks.append(_check(
            "fixture_identity", "pass",
            "The selected upcoming fixture passed exact season, home/away team and scheduled-kickoff checks.",
        ))
    else:
        checks.append(_check(
            "fixture_identity", "warning",
            str(fixture.get("reason") or "No exact upcoming fixture is verified."),
            "Refresh the selected competition schedule and confirm the exact home/away pairing. Do not substitute another fixture.",
        ))
    freshness = fixture.get("source_freshness", "unknown")
    if freshness == "fresh":
        checks.append(_check("fixture_freshness", "pass", "Detailed fixture retrieval is less than 24 hours old."))
    elif freshness == "stale":
        checks.append(_check(
            "fixture_freshness", "warning",
            "Detailed fixture retrieval is at least 24 hours old.",
            "Refresh the exact fixture before relying on its details.",
        ))
    else:
        checks.append(_check(
            "fixture_freshness", "info",
            "Fixture retrieval freshness is unknown because a valid retrieval timestamp is unavailable.",
            "A successful detailed-fixture retrieval is needed before age can be measured.",
        ))

    team_reports: dict[str, Any] = {}
    integrity: dict[str, Any] = {}
    for side, profile in (("home", home_profile), ("away", away_profile)):
        name = str(profile.get("name") or side.title())
        matches = profile.get("matches") or []
        quality = profile.get("data_quality") or {}
        count = int(quality.get("matches_returned", len(matches)) or 0)
        if count < 5:
            status = "fail"
            recommendation = "Collect more verified completed matches; prediction minimum remains five per team."
        elif count < 10:
            status = "warning"
            recommendation = "Keep readiness marked limited_history until Brighton's next result is completed and collected with valid scores. Do not add unplayed fixtures, use another season, or relax the ten-match target."
        else:
            status = "pass"
            recommendation = None
        checks.append(_check(
            f"{side}_history_depth", status,
            f"{name}: {count} completed score-valid matches available (minimum 5; target 10).",
            recommendation,
        ))
        team_reports[side] = {
            "team": name,
            "completed_matches_available": count,
            "history_minimum": 5,
            "history_target": 10,
            "history_collection_diagnostics": profile.get("history_collection_diagnostics"),
            "statistics_coverage": dict(statistics_coverage.get(name) or {}),
            "integrity": _profile_integrity(profile),
        }
        integrity[side] = team_reports[side]["integrity"]
        team_integrity = integrity[side]
        if team_integrity["duplicate_fixture_ids"] or team_integrity["invalid_or_missing_score_fields"]:
            checks.append(_check(
                f"{side}_history_integrity", "fail",
                f"{name}: duplicate fixture IDs or invalid/missing score fields were detected.",
                "Inspect the source fixture records. Invalid records must not enter prediction history.",
            ))
        else:
            checks.append(_check(
                f"{side}_history_integrity", "pass",
                f"{name}: no duplicate fixture IDs or invalid/missing score fields were found in the collected sample.",
            ))

        coverage = statistics_coverage.get(name) or {}
        any_data = int(coverage.get("core_metrics_with_any_data", 0) or 0)
        total = int(coverage.get("core_metrics_total", 8) or 8)
        if any_data == 0:
            checks.append(_check(
                f"{side}_statistics_coverage", "warning",
                f"{name}: none of the {total} core tactical statistics has usable values in the checked sample.",
                "Check whether match statistics were requested and supplied by the selected provider. Missing values remain unknown.",
            ))
        elif any_data < total:
            checks.append(_check(
                f"{side}_statistics_coverage", "warning",
                f"{name}: {any_data}/{total} core tactical statistics have at least one usable observation.",
                "Review the coverage table and unmapped raw statistic names; do not infer or impute missing values.",
            ))
        else:
            checks.append(_check(
                f"{side}_statistics_coverage", "pass",
                f"{name}: all {total} core tactical statistics have at least one usable observation.",
            ))

    corroboration_report = {}
    if corroboration:
        corroboration_report = {
            "errors": dict(corroboration.get("errors") or {}),
            "highlightly_diagnostics": dict(corroboration.get("highlightly_diagnostics") or {}),
            "team_history_coverage": dict(corroboration.get("team_history_coverage") or {}),
            "candidate_verification": list(corroboration.get("candidate_verification") or []),
            "providers_matched": list(corroboration.get("providers_matched") or []),
        }
        errors = corroboration_report["errors"]
        if errors:
            checks.append(_check(
                "independent_provider_corroboration", "warning",
                "One or more optional corroboration requests reported errors.",
                "Review the provider error details. Corroboration failures do not authorize automatic fallback.",
            ))
        else:
            checks.append(_check(
                "independent_provider_corroboration", "info",
                "No corroboration request errors were reported in the supplied diagnostic context. This does not imply that every provider agreed.",
            ))
        candidate_verification = corroboration_report["candidate_verification"]
        verification_by_id = {
            str((row.get("highlightly_candidate") or {}).get("highlightly_match_id")): row
            for row in candidate_verification
            if isinstance(row, Mapping)
            and (row.get("highlightly_candidate") or {}).get("highlightly_match_id") is not None
        }
        verified_candidates = []
        unresolved_candidates = []
        for team_row in corroboration_report["team_history_coverage"].values():
            if not isinstance(team_row, Mapping):
                continue
            for candidate in team_row.get("unmatched_completed_candidates") or []:
                if not isinstance(candidate, Mapping):
                    continue
                candidate_id = str(candidate.get("highlightly_match_id") or "")
                verification = verification_by_id.get(candidate_id)
                review = {
                    "highlightly_match_id": candidate_id or None,
                    "home": candidate.get("home"),
                    "away": candidate.get("away"),
                    "kickoff_utc": candidate.get("kickoff_utc"),
                    "score": candidate.get("score"),
                    "verification_status": (
                        verification.get("verification_status") if verification else "not_targeted_verified"
                    ),
                }
                if review["verification_status"] == "exact_fixture_and_score_agree":
                    verified_candidates.append(review)
                else:
                    unresolved_candidates.append(review)

        corroboration_report["candidate_review_summary"] = {
            "unmatched_candidates_seen": len(verified_candidates) + len(unresolved_candidates),
            "verified_exact_fixture_and_score": verified_candidates,
            "unresolved_candidates": unresolved_candidates,
            "verified_candidates_added_to_prediction_history": 0,
            "note": (
                "Targeted verification confirms identity and score only. Verified candidates are not imported "
                "or appended; primary Sportmonks season history remains the prediction source."
            ),
        }
        if unresolved_candidates:
            checks.append(_check(
                "unmatched_external_results", "warning",
                f"{len(unresolved_candidates)} unmatched Highlightly candidate(s) remain unresolved after targeted verification.",
                "Review unresolved candidates with targeted Sportmonks checks. Keep them out of prediction history unless exact fixture identity and score are independently verified.",
            ))
        elif verified_candidates:
            checks.append(_check(
                "unmatched_external_results", "info",
                f"{len(verified_candidates)} Highlightly candidate(s) were independently verified against exact Sportmonks fixtures and scores; none were imported.",
            ))
    else:
        checks.append(_check(
            "independent_provider_corroboration", "info",
            "Independent result corroboration was not run for this collection.",
            "Enable the optional cross-check if independent result comparison is needed.",
        ))

    weights = dict(model_weights or {})
    weights_total = sum(float(value) for value in weights.values()) if weights else None
    weights_valid = bool(weights) and all(
        isfinite(float(value)) and float(value) >= 0 for value in weights.values()
    ) and abs((weights_total or 0.0) - 1.0) <= 1e-9
    checks.append(_check(
        "model_weight_configuration",
        "pass" if weights_valid else "warning",
        "The supplied top-level model weights are non-negative and sum to 1.0."
        if weights_valid else "Model weights were not supplied or do not sum to 1.0.",
        None if weights_valid else "Review model configuration; this diagnostic does not modify weights.",
    ))

    readiness_status = str(readiness.get("overall_status") or "unknown")
    checks.append(_check(
        "prediction_readiness",
        "pass" if readiness_status == "ready" else "fail" if readiness_status == "insufficient_history" else "warning",
        f"Prediction readiness status: {readiness_status}.",
        None if readiness_status == "ready" else "Review fixture verification and history depth before relying on the forecast.",
    ))

    statuses = {row["status"] for row in checks}
    overall = "blocked" if "fail" in statuses else "attention_required" if "warning" in statuses or "unknown" in statuses else "healthy"
    recommended_actions = []
    seen_recommendations = set()
    for row in checks:
        recommendation = row.get("recommendation")
        if not recommendation or row.get("status") not in {"fail", "warning"}:
            continue
        if recommendation in seen_recommendations:
            continue
        seen_recommendations.add(recommendation)
        recommended_actions.append({
            "priority": "urgent" if row.get("status") == "fail" else "next",
            "check_id": row.get("id"),
            "issue": row.get("summary"),
            "action": recommendation,
        })

    # Keep the original check order within each priority group, but always
    # present failed checks before warnings in the user-facing action plan.
    recommended_actions.sort(key=lambda action: 0 if action["priority"] == "urgent" else 1)

    return {
        "diagnostic_version": 1,
        "generated_at": now.isoformat(),
        "overall_status": overall,
        "selected_context": {
            "season_start_year": int(season),
            "competition": competition,
            "primary_provider": primary_id,
        },
        "summary": {
            "checks_total": len(checks),
            "passed": sum(row["status"] == "pass" for row in checks),
            "warnings": sum(row["status"] == "warning" for row in checks),
            "failed": sum(row["status"] == "fail" for row in checks),
            "informational": sum(row["status"] == "info" for row in checks),
        },
        "checks": checks,
        "recommended_actions": recommended_actions,
        "providers": {
            key: {
                "provider": row.get("provider"),
                "role": row.get("role"),
                "credential_configured": row.get("credential_configured"),
                "credential_required": row.get("credential_required"),
                "adapter": row.get("adapter"),
                "app_integration": row.get("app_integration"),
                "limitation": row.get("limitation"),
            }
            for key, row in providers.items()
        },
        "fixture": fixture,
        "teams": team_reports,
        "corroboration": corroboration_report,
        "prediction_readiness": dict(readiness),
        "model_configuration": {
            "weights": weights,
            "weights_total": weights_total,
            "model_impact": "Diagnostics only; weights, recency weighting, prediction inputs and missing-data rules are not changed.",
        },
    }
