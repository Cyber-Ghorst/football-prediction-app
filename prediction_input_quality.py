"""Hard quality gates for the exact team histories passed to prediction.

Optional evidence gaps remain warnings. Only malformed core match history,
duplicate fixture identities, wrong team identity, or insufficient verified
results block prediction. This module never repairs or imputes input data.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def _whole_nonnegative_score(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value >= 0
    if isinstance(value, str):
        return value.strip().isdigit()
    return False


def _utc_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _team_quality(
    profile: Mapping[str, Any],
    *,
    expected_team_id: int | str,
    minimum_matches: int,
    now: datetime,
    max_history_age_hours: float,
) -> dict[str, Any]:
    name = str(profile.get("name") or "Unknown team")
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    warnings: list[str] = []

    def add(check: str, status: str, detail: str) -> None:
        checks.append({"check": check, "status": status, "detail": detail})
        if status == "fail":
            failures.append(detail)
        elif status == "warning":
            warnings.append(detail)

    actual_id = profile.get("id")
    if actual_id is None or str(actual_id) != str(expected_team_id):
        add("team_identity", "fail", f"{name}: profile team ID does not match the selected team.")
    else:
        add("team_identity", "pass", f"{name}: selected team ID verified.")

    matches_value = profile.get("matches")
    matches = matches_value if isinstance(matches_value, list) else []
    if not isinstance(matches_value, list):
        add("history_shape", "fail", f"{name}: match history is not a list.")
    elif len(matches) < minimum_matches:
        add("history_depth", "fail", f"{name}: only {len(matches)} match rows; {minimum_matches} are required.")
    else:
        add("history_depth", "pass", f"{name}: {len(matches)} match rows meet the minimum.")

    fixture_ids: list[str] = []
    invalid_score_rows: list[Any] = []
    invalid_kickoff_rows: list[Any] = []
    future_kickoff_rows: list[Any] = []
    parsed_kickoffs: list[datetime] = []
    for index, match in enumerate(matches):
        if not isinstance(match, Mapping):
            invalid_score_rows.append(index)
            invalid_kickoff_rows.append(index)
            continue
        fixture_id = match.get("fixture_id")
        if fixture_id is None or not str(fixture_id).strip():
            add("fixture_identity", "fail", f"{name}: history row {index + 1} has no fixture ID.")
        else:
            fixture_ids.append(str(fixture_id))

        if not _whole_nonnegative_score(match.get("goals_for")) or not _whole_nonnegative_score(match.get("goals_against")):
            invalid_score_rows.append(fixture_id if fixture_id is not None else index)

        kickoff = _utc_datetime(match.get("date"))
        if kickoff is None:
            invalid_kickoff_rows.append(fixture_id if fixture_id is not None else index)
        else:
            parsed_kickoffs.append(kickoff)
            if kickoff > now:
                future_kickoff_rows.append(fixture_id if fixture_id is not None else index)

    duplicate_ids = sorted({value for value in fixture_ids if fixture_ids.count(value) > 1})
    if duplicate_ids:
        add("duplicate_fixtures", "fail", f"{name}: duplicate fixture IDs are present in prediction history.")
    else:
        add("duplicate_fixtures", "pass", f"{name}: no duplicate fixture IDs in prediction history.")

    if invalid_score_rows:
        add("score_integrity", "fail", f"{name}: missing, negative, fractional or non-numeric goals appear in prediction history.")
    else:
        add("score_integrity", "pass", f"{name}: every history row has a valid non-negative whole-number score pair.")

    if invalid_kickoff_rows:
        add("kickoff_integrity", "fail", f"{name}: one or more history rows have a missing or invalid kickoff timestamp.")
    else:
        add("kickoff_integrity", "pass", f"{name}: all history rows have valid kickoff timestamps.")

    if future_kickoff_rows:
        add("history_temporal_integrity", "fail", f"{name}: future-dated fixtures appear in completed-match history.")
    elif len(parsed_kickoffs) == len(matches) and any(
        parsed_kickoffs[index] < parsed_kickoffs[index + 1]
        for index in range(len(parsed_kickoffs) - 1)
    ):
        add("history_temporal_integrity", "fail", f"{name}: history is not ordered newest-first; recency weighting would be unreliable.")
    else:
        add("history_temporal_integrity", "pass", f"{name}: history is newest-first and contains no future-dated fixtures.")

    quality = profile.get("data_quality") if isinstance(profile.get("data_quality"), Mapping) else {}
    history_fetched_at = _utc_datetime(quality.get("history_collection_fetched_at"))
    if history_fetched_at is None:
        add(
            "history_evidence_freshness",
            "warning",
            f"{name}: history collection timestamp is missing or invalid; freshness cannot be confirmed.",
        )
    elif history_fetched_at > now:
        add(
            "history_evidence_freshness",
            "fail",
            f"{name}: history collection timestamp is in the future; evidence freshness is invalid.",
        )
    elif (now - history_fetched_at).total_seconds() > max_history_age_hours * 3600:
        add(
            "history_evidence_freshness",
            "fail",
            f"{name}: collected match-history evidence is older than {max_history_age_hours:g} hours.",
        )
    else:
        add(
            "history_evidence_freshness",
            "pass",
            f"{name}: match-history evidence was collected within the last {max_history_age_hours:g} hours.",
        )
    reported_count = quality.get("matches_returned")
    if reported_count is not None and str(reported_count) != str(len(matches)):
        add("reported_history_count", "fail", f"{name}: reported history count does not match the actual match rows.")
    else:
        add("reported_history_count", "pass", f"{name}: reported and actual history counts agree.")

    statistic_conflicts = [
        conflict
        for match in matches if isinstance(match, Mapping)
        for conflict in (match.get("statistics_conflicts") or [])
    ]
    invalid_statistics = [
        row
        for match in matches if isinstance(match, Mapping)
        for row in (match.get("statistics_invalid_rows") or [])
    ]
    if statistic_conflicts or invalid_statistics:
        add(
            "statistics_integrity",
            "warning",
            f"{name}: {len(statistic_conflicts)} conflicting and {len(invalid_statistics)} invalid supported statistic observation(s) were excluded or left unknown.",
        )
    else:
        add("statistics_integrity", "pass", f"{name}: no conflicting or invalid supported statistic observations were reported.")

    if quality.get("history_integrity_status") == "issues_detected":
        add(
            "collection_exclusions",
            "warning",
            f"{name}: the collection encountered and excluded duplicate or invalid upstream fixture rows; retained model inputs are checked independently.",
        )
    elif quality.get("history_integrity_status") == "ok":
        add("collection_exclusions", "pass", f"{name}: collector reports no upstream history-integrity issues.")

    if quality.get("season_id") is None:
        add("season_metadata", "warning", f"{name}: profile does not expose a provider season ID for an independent season check.")
    else:
        add("season_metadata", "info", f"{name}: provider season ID {quality.get('season_id')} is recorded.")

    return {
        "team": name,
        "prediction_allowed": not failures,
        "checks": checks,
        "failures": failures,
        "warnings": warnings,
        "matches_checked": len(matches),
        "duplicate_fixture_ids": duplicate_ids,
        "invalid_score_rows": invalid_score_rows,
        "invalid_kickoff_rows": invalid_kickoff_rows,
        "future_kickoff_rows": future_kickoff_rows,
    }


def build_prediction_input_quality_report(
    home_profile: Mapping[str, Any],
    away_profile: Mapping[str, Any],
    *,
    home_team_id: int | str,
    away_team_id: int | str,
    minimum_matches: int = 5,
    now: datetime | None = None,
    fixture_readiness: Mapping[str, Any] | None = None,
    max_history_age_hours: float = 24.0,
) -> dict[str, Any]:
    """Validate only core history fields used by prediction; optional data is not imputed."""
    if isinstance(minimum_matches, bool) or not isinstance(minimum_matches, int) or minimum_matches < 1:
        raise ValueError("minimum_matches must be a positive integer.")
    if (
        isinstance(max_history_age_hours, bool)
        or not isinstance(max_history_age_hours, (int, float))
        or max_history_age_hours <= 0
    ):
        raise ValueError("max_history_age_hours must be a positive number.")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)

    teams = {
        "home": _team_quality(
            home_profile, expected_team_id=home_team_id,
            minimum_matches=minimum_matches, now=current,
            max_history_age_hours=float(max_history_age_hours),
        ),
        "away": _team_quality(
            away_profile, expected_team_id=away_team_id,
            minimum_matches=minimum_matches, now=current,
            max_history_age_hours=float(max_history_age_hours),
        ),
    }
    fixture_checks: list[dict[str, str]] = []
    fixture_failures: list[str] = []
    fixture_warnings: list[str] = []
    if fixture_readiness is not None:
        verified = fixture_readiness.get("verified") is True
        freshness = str(fixture_readiness.get("source_freshness") or "unknown")
        if verified and freshness == "stale":
            detail = "The exact upcoming fixture was verified, but its source evidence is stale."
            fixture_checks.append({"check": "fixture_evidence_freshness", "status": "fail", "detail": detail})
            fixture_failures.append(detail)
        elif verified and freshness == "fresh":
            fixture_checks.append({
                "check": "fixture_evidence_freshness",
                "status": "pass",
                "detail": "The exact upcoming fixture is verified and its source evidence is fresh.",
            })
        else:
            detail = (
                "The exact upcoming fixture's source freshness is unknown."
                if verified
                else "No exact upcoming fixture is verified; matchup analysis may continue, but fixture-specific readiness is not established."
            )
            fixture_checks.append({"check": "fixture_evidence_freshness", "status": "warning", "detail": detail})
            fixture_warnings.append(detail)

    failures = fixture_failures + [
        failure for report in teams.values()
        for failure in report["failures"]
    ]
    warnings = fixture_warnings + [
        warning for report in teams.values()
        for warning in report["warnings"]
    ]
    return {
        "status": "blocked" if failures else "attention" if warnings else "passed",
        "prediction_allowed": not failures,
        "minimum_matches_per_team": minimum_matches,
        "max_history_age_hours": float(max_history_age_hours),
        "fixture_checks": fixture_checks,
        "teams": teams,
        "failures": failures,
        "warnings": warnings,
        "optional_evidence_policy": (
            "Missing statistics, injuries, player availability, lineups or opponent-strength "
            "observations are not treated as fabricated zeros and do not independently fail "
            "the core-history gate; their coverage remains visible in existing diagnostics."
        ),
        "prediction_inputs_modified": False,
        "note": "The gate validates the supplied history and never repairs, reorders or imputes it.",
    }
