"""Competition-season prediction readiness evaluation.

This is a pure, read-only evaluator over normalized evidence. It does not query
providers or write canonical identities, fixtures, predictions, or model state.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

DEFAULT_HISTORY_TARGET = 10
LIMITED_HISTORY_MINIMUM = 5
REQUIRED_TACTICAL_COMPONENTS = (
    "playing_style",
    "defensive_structure",
    "attacking_approach",
)


def _present(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _parse_utc(value: Any) -> datetime | None:
    if not _present(value):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def evaluate_competition_readiness(
    evidence: Mapping[str, Any],
    *,
    now: datetime | None = None,
    history_target: int = DEFAULT_HISTORY_TARGET,
    limited_history_minimum: int = LIMITED_HISTORY_MINIMUM,
) -> dict[str, Any]:
    """Evaluate one competition-season evidence record using fail-closed gates.

    Required input contract:
      competition: {name, country, type, identity_verified}
      season: {id, name, active, identity_verified}
      teams: {participating_count, approved_mapping_count, history_by_team,
              statistics_complete_by_team, tactical_components_by_team}
      fixture: {upcoming_valid, source_freshness}
      evidence_generated_at: ISO-8601 timestamp

    The function reports blockers and never infers a verified flag from names,
    provider counts, fixture volume, or overlapping season years.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if history_target < 1 or limited_history_minimum < 1 or limited_history_minimum > history_target:
        raise ValueError("history thresholds must be positive and minimum <= target")

    competition = evidence.get("competition") if isinstance(evidence.get("competition"), Mapping) else {}
    season = evidence.get("season") if isinstance(evidence.get("season"), Mapping) else {}
    teams = evidence.get("teams") if isinstance(evidence.get("teams"), Mapping) else {}
    fixture = evidence.get("fixture") if isinstance(evidence.get("fixture"), Mapping) else {}

    hard_blockers: list[str] = []
    improvement_blockers: list[str] = []

    if not all(_present(competition.get(key)) for key in ("name", "country", "type")):
        hard_blockers.append("competition_name_country_or_type_missing")
    if competition.get("identity_verified") is not True:
        hard_blockers.append("competition_identity_not_explicitly_verified")
    if not _present(season.get("id")) or not _present(season.get("name")):
        hard_blockers.append("season_identity_missing")
    if season.get("identity_verified") is not True:
        hard_blockers.append("season_identity_not_explicitly_verified")
    if season.get("active") is not True:
        hard_blockers.append("season_not_confirmed_active")

    try:
        participating = int(teams.get("participating_count", 0))
        mapped = int(teams.get("approved_mapping_count", 0))
    except (TypeError, ValueError):
        participating, mapped = 0, -1
    if participating < 2:
        hard_blockers.append("participating_team_count_invalid")
    if mapped != participating:
        hard_blockers.append("not_all_participating_teams_have_approved_mappings")

    if fixture.get("upcoming_valid") is not True:
        hard_blockers.append("no_verified_upcoming_fixture")
    if fixture.get("source_freshness") != "fresh":
        improvement_blockers.append("fixture_source_not_confirmed_fresh")

    history = teams.get("history_by_team") if isinstance(teams.get("history_by_team"), Mapping) else {}
    stats = teams.get("statistics_complete_by_team") if isinstance(teams.get("statistics_complete_by_team"), Mapping) else {}
    tactical = teams.get("tactical_components_by_team") if isinstance(teams.get("tactical_components_by_team"), Mapping) else {}

    history_counts: dict[str, int] = {}
    for team_id in sorted(str(key) for key in history):
        try:
            count = int(history.get(team_id, 0))
        except (TypeError, ValueError):
            count = 0
        history_counts[team_id] = max(0, count)
        if count < limited_history_minimum:
            improvement_blockers.append(f"insufficient_history:{team_id}")
        elif count < history_target:
            improvement_blockers.append(f"history_below_target:{team_id}")

    if len(history_counts) < participating:
        improvement_blockers.append("history_evidence_missing_for_participating_teams")

    stats_complete = True
    for team_id in sorted(str(key) for key in stats):
        if stats.get(team_id) is not True:
            stats_complete = False
            improvement_blockers.append(f"core_statistics_incomplete:{team_id}")
    if len(stats) < participating:
        stats_complete = False
        improvement_blockers.append("statistics_evidence_missing_for_participating_teams")

    tactical_complete = True
    for team_id in sorted(str(key) for key in tactical):
        components = tactical.get(team_id)
        if not isinstance(components, Mapping):
            components = {}
        missing = [name for name in REQUIRED_TACTICAL_COMPONENTS if not _present(components.get(name))]
        if missing:
            tactical_complete = False
            improvement_blockers.append(f"tactical_components_missing:{team_id}:{','.join(missing)}")
    if len(tactical) < participating:
        tactical_complete = False
        improvement_blockers.append("tactical_evidence_missing_for_participating_teams")

    generated_at = _parse_utc(evidence.get("evidence_generated_at"))
    if generated_at is None:
        improvement_blockers.append("evidence_timestamp_missing_or_invalid")
    elif generated_at > now.astimezone(timezone.utc):
        improvement_blockers.append("evidence_timestamp_in_future")

    if hard_blockers:
        status = "not_ready"
    elif improvement_blockers:
        status = "partially_ready"
    else:
        status = "prediction_ready"

    return {
        "competition_name": competition.get("name"),
        "country": competition.get("country"),
        "competition_type": competition.get("type"),
        "season_id": season.get("id"),
        "season_name": season.get("name"),
        "status": status,
        "prediction_ready": status == "prediction_ready",
        "hard_blockers": sorted(set(hard_blockers)),
        "improvement_blockers": sorted(set(improvement_blockers)),
        "history_by_team": history_counts,
        "history_target": history_target,
        "limited_history_minimum": limited_history_minimum,
        "statistics_complete": stats_complete,
        "tactical_components_complete": tactical_complete,
        "evidence_generated_at": generated_at.isoformat() if generated_at else None,
        "evaluated_at": now.astimezone(timezone.utc).isoformat(),
        "writes_performed": False,
    }


def build_competition_readiness_report(
    records: Iterable[Mapping[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate records and summarize statuses without promoting any entity."""
    evaluated = [
        evaluate_competition_readiness(row, now=now)
        for row in (records or [])
        if isinstance(row, Mapping)
    ]
    evaluated.sort(key=lambda row: (
        str(row.get("country") or "").casefold(),
        str(row.get("competition_name") or "").casefold(),
        str(row.get("season_name") or "").casefold(),
    ))
    counts = {
        status: sum(row["status"] == status for row in evaluated)
        for status in ("not_ready", "partially_ready", "prediction_ready")
    }
    return {
        "report_name": "competition_readiness",
        "generated_at_utc": (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        "summary": {"total_competition_seasons": len(evaluated), **counts},
        "competitions": evaluated,
        "policy": {
            "history_target_per_team": DEFAULT_HISTORY_TARGET,
            "limited_history_minimum_per_team": LIMITED_HISTORY_MINIMUM,
            "required_tactical_components": list(REQUIRED_TACTICAL_COMPONENTS),
            "missing_data_imputed": False,
            "canonical_identity_or_fixture_writes": False,
            "prediction_ledger_writes": False,
            "model_weights_changed": False,
        },
    }
