"""Provider-neutral Layer 2 team-season profiles from canonical repository rows.

This module consumes canonical IDs and normalized repository data. It does not
infer provider IDs or crosswalks. Missing or conflicting evidence stays missing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from form_analyzer import analyze_form, venue_rating
from tactical_indicators import analyze_tactics
from tactical_evidence import build_league_reference_statistics, build_tactical_evidence_profile
from statistics_coverage import CORE_STATISTICS, build_provider_neutral_statistics_coverage


_COMPLETED = {"finished", "complete", "completed", "ft", "full time", "5"}


def _utc_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _non_negative_score(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if str(value).strip() not in {str(number), f"{number}.0"} or number < 0:
        return None
    return number


def _normalize_statistic_value(statistic_type: str, value: Any) -> float | None:
    """Accept finite non-negative numeric observations and valid percentages only."""
    import math

    if isinstance(value, bool) or value is None:
        return None
    text = str(value).strip().replace(",", "")
    had_percent_sign = text.endswith("%")
    if had_percent_sign:
        text = text[:-1].strip()
    try:
        number = float(text)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    if statistic_type in {"Ball Possession", "Passes %"}:
        if not had_percent_sign and 0 < number <= 1:
            number *= 100
        if number > 100:
            return None
    return round(number, 3)


def _same_statistic_value(left: Any, right: Any) -> bool:
    try:
        return float(str(left).replace("%", "").replace(",", "")) == float(
            str(right).replace("%", "").replace(",", "")
        )
    except (TypeError, ValueError):
        return left == right


def _canonical_standings_strength(fixtures: list[dict[str, Any]], season_id: str) -> dict[str, float]:
    """Derive rank-based strength from verified completed canonical season results."""
    now = datetime.now(timezone.utc)
    table: dict[str, dict[str, int]] = {}
    seen_ids: set[str] = set()
    seen_fingerprints: set[tuple[str, str, str, str]] = set()
    for fixture in fixtures or []:
        if str(fixture.get("season_id") or "").strip() != season_id:
            continue
        fixture_id = str(fixture.get("fixture_id") or "").strip()
        home_id = str(fixture.get("home_team_id") or "").strip()
        away_id = str(fixture.get("away_team_id") or "").strip()
        if not fixture_id or not home_id or not away_id or home_id == away_id or fixture_id in seen_ids:
            continue
        seen_ids.add(fixture_id)
        if str(fixture.get("status") or "").strip().casefold() not in _COMPLETED:
            continue
        kickoff = _utc_datetime(fixture.get("starting_at"))
        if kickoff is None or kickoff >= now:
            continue
        fingerprint = (season_id, kickoff.isoformat(), home_id, away_id)
        if fingerprint in seen_fingerprints:
            continue
        seen_fingerprints.add(fingerprint)
        hg = _non_negative_score(fixture.get("home_goals"))
        ag = _non_negative_score(fixture.get("away_goals"))
        if hg is None or ag is None:
            continue
        for team_id in (home_id, away_id):
            table.setdefault(team_id, {"points": 0, "gd": 0, "gf": 0, "wins": 0})
        home, away = table[home_id], table[away_id]
        home["gf"] += hg
        away["gf"] += ag
        home["gd"] += hg - ag
        away["gd"] += ag - hg
        if hg > ag:
            home["points"] += 3
            home["wins"] += 1
        elif ag > hg:
            away["points"] += 3
            away["wins"] += 1
        else:
            home["points"] += 1
            away["points"] += 1
    ordered = sorted(table, key=lambda team_id: (
        -table[team_id]["points"], -table[team_id]["gd"],
        -table[team_id]["gf"], -table[team_id]["wins"], team_id
    ))
    count = len(ordered)
    return {team_id: round((count - rank + 1) / count * 100, 3)
            for rank, team_id in enumerate(ordered, 1)} if count else {}


def build_provider_neutral_team_profile(
    team: dict[str, Any],
    fixtures: list[dict[str, Any]],
    *,
    season_id: str,
    statistics: list[dict[str, Any]] | None = None,
    opponent_strength: dict[str, float] | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Build the existing Layer 2 profile contract from canonical repository data."""
    team_id = str(team.get("team_id") or team.get("id") or "").strip()
    if not team_id:
        raise ValueError("A canonical team_id is required.")
    canonical_season_id = str(season_id or "").strip()
    if not canonical_season_id:
        raise ValueError("A canonical season_id is required.")
    safe_limit = max(1, min(int(limit), 10))
    derived_strength = _canonical_standings_strength(fixtures, canonical_season_id)
    effective_strength = opponent_strength if opponent_strength is not None else derived_strength

    # Resolve each fixture/team/metric independently so opponent statistics
    # can support tactical evidence. Conflicts are excluded, never averaged.
    aliases = {
        "ball possession": "Ball Possession", "ball possession %": "Ball Possession",
        "pass accuracy": "Passes %", "passes accuracy": "Passes %",
        "accurate passes percentage": "Passes %",
        "pass success percentage": "Passes %",
        "successful passes percentage": "Passes %",
        "passes %": "Passes %", "successful passes %": "Passes %",
        "shots on goal": "Shots on Goal", "shots on target": "Shots on Target",
        "total shots": "Total Shots", "shots total": "Total Shots",
        "goal attempts": "Total Shots", "shots off target": "Shots off Target",
        "tackles": "Tackles", "interceptions": "Interceptions",
        "blocked shots": "Blocked Shots", "shots blocked": "Blocked Shots",
        "corners": "Corner Kicks",
        "corner kicks": "Corner Kicks", "accurate crosses": "Accurate Crosses",
        "successful dribbles": "Successful Dribbles",
        "successful headers": "Successful Headers",
        "big chances created": "Big Chances Created", "key passes": "Key Passes",
        "shots insidebox": "Shots Insidebox", "shots inside box": "Shots Insidebox",
        "counter attacks": "Counter Attacks", "counter-attacks": "Counter Attacks",
    }
    candidates: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    invalid_statistics_by_fixture_team: dict[tuple[str, str], list[dict[str, Any]]] = {}
    unmapped_statistics_by_fixture_team: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in statistics or []:
        if not isinstance(row, dict):
            continue
        fixture_id = str(row.get("fixture_id") or "").strip()
        statistic_team_id = str(row.get("team_id") or "").strip()
        raw_type = str(row.get("statistic_type") or "").strip()
        value = row.get("statistic_value")
        statistic_type = aliases.get(raw_type.casefold(), raw_type)
        key = (fixture_id, statistic_team_id)
        if not fixture_id or not statistic_team_id or not raw_type:
            continue
        if statistic_type not in set(aliases.values()):
            unmapped_statistics_by_fixture_team.setdefault(key, []).append({
                "raw_type": raw_type, "raw_value": value,
                "provider": row.get("provider") or row.get("source_provider"),
                "status": "unmapped",
            })
            continue
        normalized_value = _normalize_statistic_value(statistic_type, value)
        if normalized_value is None:
            invalid_statistics_by_fixture_team.setdefault(key, []).append({
                "statistic_type": statistic_type, "raw_type": raw_type,
                "raw_value": value,
                "provider": row.get("provider") or row.get("source_provider"),
                "status": "invalid",
            })
            continue
        candidates.setdefault((fixture_id, statistic_team_id, statistic_type), []).append({
            **row, "_normalized_value": normalized_value,
        })

    stats_by_fixture_team: dict[tuple[str, str], dict[str, Any]] = {}
    provenance_by_fixture_team: dict[tuple[str, str], list[dict[str, Any]]] = {}
    conflicts_by_fixture_team: dict[tuple[str, str], list[str]] = {}
    league_reference_rows: list[dict[str, Any]] = []
    for (fixture_id, statistic_team_id, statistic_type), rows in candidates.items():
        values = [row.get("_normalized_value") for row in rows]
        if any(not _same_statistic_value(values[0], value) for value in values[1:]):
            conflicts_by_fixture_team.setdefault((fixture_id, statistic_team_id), []).append(statistic_type)
            continue
        # A metric with both valid and invalid observations is ambiguous; exclude it.
        if (fixture_id, statistic_team_id) in invalid_statistics_by_fixture_team and any(
            row.get("statistic_type") == statistic_type
            for row in invalid_statistics_by_fixture_team[(fixture_id, statistic_team_id)]
        ):
            conflicts_by_fixture_team.setdefault((fixture_id, statistic_team_id), []).append(statistic_type)
            continue
        key = (fixture_id, statistic_team_id)
        stats_by_fixture_team.setdefault(key, {})[statistic_type] = values[0]
        provenance_by_fixture_team.setdefault(key, []).extend({
            "provider": row.get("provider") or row.get("source_provider"),
            "provider_statistic_id": row.get("provider_statistic_id"),
            "statistic_type": statistic_type,
            "normalized_value": row.get("_normalized_value"),
        } for row in rows)
        league_reference_rows.append({statistic_type: values[0]})
    league_reference = build_league_reference_statistics(league_reference_rows)

    matches: list[dict[str, Any]] = []
    excluded = {"wrong_season": 0, "not_completed": 0, "invalid_identity": 0,
                "invalid_kickoff": 0, "invalid_score": 0}
    history = {
        "fixtures_scanned": len(fixtures or []), "same_season_fixtures": 0,
        "season_eligible_fixtures": 0, "fixtures_missing_season_id": 0,
        "team_fixtures": 0, "completed_fixtures": 0, "fixtures_with_valid_scores": 0,
        "duplicate_fixture_ids": [], "duplicate_fixture_fingerprints": [],
        "excluded_duplicate_fixture_id": 0, "excluded_duplicate_fingerprint": 0,
    }
    seen_fixture_ids: set[str] = set()
    seen_fingerprints: set[tuple[str, str, str, str]] = set()
    for fixture in fixtures or []:
        fixture_season_id = str(fixture.get("season_id") or "").strip()
        if fixture_season_id != canonical_season_id:
            excluded["wrong_season"] += 1
            continue
        history["same_season_fixtures"] += 1
        history["season_eligible_fixtures"] += 1
        fixture_id = str(fixture.get("fixture_id") or "").strip()
        home_id = str(fixture.get("home_team_id") or "").strip()
        away_id = str(fixture.get("away_team_id") or "").strip()
        if not fixture_id or not home_id or not away_id or home_id == away_id or team_id not in {home_id, away_id}:
            excluded["invalid_identity"] += 1
            continue
        if fixture_id in seen_fixture_ids:
            history["excluded_duplicate_fixture_id"] += 1
            history["duplicate_fixture_ids"].append(fixture_id)
            continue
        seen_fixture_ids.add(fixture_id)
        history["team_fixtures"] += 1
        status = str(fixture.get("status") or "").strip().casefold()
        if status not in _COMPLETED:
            excluded["not_completed"] += 1
            continue
        history["completed_fixtures"] += 1
        kickoff = _utc_datetime(fixture.get("starting_at"))
        if kickoff is None or kickoff >= datetime.now(timezone.utc):
            excluded["invalid_kickoff"] += 1
            continue
        fingerprint = (canonical_season_id, kickoff.isoformat(), home_id, away_id)
        if fingerprint in seen_fingerprints:
            history["excluded_duplicate_fingerprint"] += 1
            history["duplicate_fixture_fingerprints"].append({
                "season_id": canonical_season_id, "starting_at": kickoff.isoformat(),
                "home_team_id": home_id, "away_team_id": away_id,
            })
            continue
        seen_fingerprints.add(fingerprint)
        home_goals = _non_negative_score(fixture.get("home_goals"))
        away_goals = _non_negative_score(fixture.get("away_goals"))
        if home_goals is None or away_goals is None:
            excluded["invalid_score"] += 1
            continue
        history["fixtures_with_valid_scores"] += 1
        is_home = team_id == home_id
        opponent_id = away_id if is_home else home_id
        matches.append({
            "fixture_id": fixture_id,
            "date": kickoff.isoformat(),
            "venue": "home" if is_home else "away",
            "opponent_id": opponent_id,
            "opponent_name": fixture.get("away_team" if is_home else "home_team"),
            "goals_for": home_goals if is_home else away_goals,
            "goals_against": away_goals if is_home else home_goals,
            "opponent_strength": (effective_strength or {}).get(opponent_id),
            "statistics": stats_by_fixture_team.get((fixture_id, team_id), {}),
            "opponent_statistics": stats_by_fixture_team.get((fixture_id, opponent_id), {}),
            "statistics_provenance": provenance_by_fixture_team.get((fixture_id, team_id), []),
            "statistics_conflicts": conflicts_by_fixture_team.get((fixture_id, team_id), []),
            "opponent_statistics_conflicts": conflicts_by_fixture_team.get((fixture_id, opponent_id), []),
            "statistics_invalid_rows": invalid_statistics_by_fixture_team.get((fixture_id, team_id), []),
            "statistics_unmapped_rows": unmapped_statistics_by_fixture_team.get((fixture_id, team_id), []),
            "opponent_statistics_invalid_rows": invalid_statistics_by_fixture_team.get((fixture_id, opponent_id), []),
            "opponent_statistics_unmapped_rows": unmapped_statistics_by_fixture_team.get((fixture_id, opponent_id), []),
            "source_provider": fixture.get("source_provider"),
            "collection_fetched_at": fixture.get("collection_fetched_at"),
            "repository_collected_at": fixture.get("repository_collected_at"),
            "provider_updated_at": fixture.get("provider_updated_at"),
        })

    matches.sort(key=lambda row: row["date"], reverse=True)
    recent = matches[:safe_limit]
    form = analyze_form(recent)
    tactics = analyze_tactics(recent)
    tactical_evidence = build_tactical_evidence_profile(
        recent, league_reference, team.get("name") or f"Team {team_id}"
    )
    statistics_coverage = build_provider_neutral_statistics_coverage(recent)
    team_fixture_accounting_gap = (
        history["team_fixtures"] - history["completed_fixtures"] - excluded["not_completed"]
    )
    duplicate_issue = bool(
        history["duplicate_fixture_ids"] or history["duplicate_fixture_fingerprints"]
    )
    integrity_issue = bool(
        duplicate_issue or excluded["invalid_kickoff"] or excluded["invalid_score"]
        or team_fixture_accounting_gap
    )
    def latest_timestamp(field: str) -> str | None:
        values = [_utc_datetime(match.get(field)) for match in recent if match.get(field)]
        values = [value for value in values if value is not None]
        return max(values).isoformat() if values else None

    core_coverage = {
        row["statistic"]: row["fixtures_available"]
        for row in statistics_coverage["metrics"]
    }
    matches_with_any_statistics = sum(bool(match.get("statistics")) for match in recent)
    matches_with_complete_core_statistics = sum(
        all(
            any((match.get("statistics") or {}).get(name) is not None for name in aliases)
            for _label, _group, aliases in CORE_STATISTICS
        )
        for match in recent
    )
    core_observation_target = len(recent) * statistics_coverage["core_metrics_total"]
    core_observations = sum(core_coverage.values())
    core_completeness_pct = (
        round(core_observations / core_observation_target * 100, 1)
        if core_observation_target else 0.0
    )
    history_diagnostics = {
        **history,
        "excluded_wrong_season": excluded["wrong_season"],
        "excluded_not_completed": excluded["not_completed"],
        "excluded_invalid_identity": excluded["invalid_identity"],
        "excluded_invalid_kickoff": excluded["invalid_kickoff"],
        "excluded_invalid_scores": excluded["invalid_score"],
        "history_shortfall": max(0, 10 - len(recent)),
        "history_latest_match_at": recent[0]["date"] if recent else None,
        "history_oldest_match_at": recent[-1]["date"] if recent else None,
        "history_order": "newest_first_by_parsed_utc_kickoff",
        "duplicate_fixture_id_count": len(history["duplicate_fixture_ids"]),
        "duplicate_fixture_fingerprint_count": len(history["duplicate_fixture_fingerprints"]),
        "duplicate_fixture_ids_checked": True,
        "team_fixture_accounting_gap": team_fixture_accounting_gap,
        "team_fixture_accounting_status": "balanced" if team_fixture_accounting_gap == 0 else "unbalanced",
        "history_integrity_status": "issues_detected" if integrity_issue else "ok",
        "history_collection_fetched_at": latest_timestamp("collection_fetched_at"),
        "history_repository_collected_at": latest_timestamp("repository_collected_at"),
        "history_provider_updated_at": latest_timestamp("provider_updated_at"),
        "statistics_core_metrics": list(core_coverage),
        "statistics_coverage_by_metric": core_coverage,
        "matches_with_any_statistics": matches_with_any_statistics,
        "matches_with_complete_core_statistics": matches_with_complete_core_statistics,
        "core_statistics_completeness_pct": core_completeness_pct,
    }
    return {
        "id": team_id,
        "name": team.get("name") or f"Team {team_id}",
        "logo": team.get("logo_url") or team.get("logo"),
        "matches": recent,
        "home_rating": venue_rating(recent, "home"),
        "away_rating": venue_rating(recent, "away"),
        "player_availability": None,
        "playing_style": tactics.get("playing_style"),
        "defensive_structure": tactics.get("defensive_structure"),
        "attacking_approach": tactics.get("attacking_approach"),
        "tactical_compatibility": None,
        "form_summary": form,
        "tactical_summary": tactics,
        "tactical_evidence": tactical_evidence,
        "statistics_coverage": statistics_coverage,
        "history_collection_diagnostics": history_diagnostics,
        "availability": {
            "injury_data_available": False, "reported_injuries": None,
            "injuries": [], "player_availability": None,
            "note": "No verified availability feed supplied; player availability remains unknown.",
        },
        "lineups": {
            "lineups_available": False, "teams": [],
            "note": "No verified fixture-specific lineup supplied.",
        },
        "upcoming_fixture_id": None,
        "data_quality": {
            "provider": "canonical_repository",
            "season_id": canonical_season_id,
            "matches_scanned": len(fixtures or []),
            "fixtures_scanned": len(fixtures or []),
            "matches_returned": len(recent),
            "goals_complete": len(recent) >= 5,
            "opponent_strength_matches": sum(m.get("opponent_strength") is not None for m in recent),
            "opponent_strength_source": (
                "supplied_canonical_strength_map" if opponent_strength is not None
                else "derived_from_completed_canonical_season_fixtures"
            ),
            "opponent_strength_teams_in_standings": len(effective_strength or {}),
            "opponent_strength_method": "rank by points, goal difference, goals scored, wins; deterministic canonical team ID tiebreak",
            "statistics_matches": matches_with_any_statistics,
            "statistics_observations": sum(len(m.get("statistics_provenance") or []) for m in recent),
            "statistics_raw_observations": None,
            "statistics_raw_observations_available": False,
            "statistics_unmapped_observations": sum(len(m.get("statistics_unmapped_rows") or []) for m in recent),
            "statistics_conflicts": sum(len(m.get("statistics_conflicts") or []) for m in recent),
            "statistics_invalid_values": sum(len(m.get("statistics_invalid_rows") or []) for m in recent),
            "matches_with_complete_core_statistics": matches_with_complete_core_statistics,
            "core_statistics_completeness_pct": core_completeness_pct,
            "statistics_coverage_by_metric": core_coverage,
            "statistics_conflict_count": sum(len(m.get("statistics_conflicts") or []) for m in recent),
            "opponent_statistics_conflict_count": sum(len(m.get("opponent_statistics_conflicts") or []) for m in recent),
            "statistics_invalid_value_count": sum(len(m.get("statistics_invalid_rows") or []) for m in recent),
            "statistics_unmapped_observation_count": sum(len(m.get("statistics_unmapped_rows") or []) for m in recent),
            "opponent_statistics_invalid_value_count": sum(len(m.get("opponent_statistics_invalid_rows") or []) for m in recent),
            "history_shortfall": max(0, 10 - len(recent)),
            "history_integrity_status": history_diagnostics["history_integrity_status"],
            "history_duplicate_check_performed": True,
            "duplicate_fixture_id_count": history_diagnostics["duplicate_fixture_id_count"],
            "duplicate_fixture_fingerprint_count": history_diagnostics["duplicate_fixture_fingerprint_count"],
            "team_fixture_accounting_status": history_diagnostics["team_fixture_accounting_status"],
            "tactical_evidence_source": "canonical_repository_season_statistics",
            "tactical_evidence_dimensions_available": tactical_evidence.get("evidence_metadata", {}).get("available_dimensions", 0),
            "statistics_coverage_by_metric": {
                name: sum(name in (match.get("statistics") or {}) for match in recent)
                for name in tactics.get("available_metrics", {})
            },
            "excluded": excluded,
        },
    }


def build_repository_team_profiles(
    snapshot: dict[str, Any],
    team_ids: list[str] | tuple[str, ...],
    season_id: str,
    *,
    opponent_strength: dict[str, float] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build profiles for selected canonical teams from one repository snapshot."""
    canonical_season_id = str(season_id)
    if str(snapshot.get("season_id") or "") != canonical_season_id:
        raise ValueError("Repository snapshot season does not match the requested canonical season.")
    requested_ids = list(dict.fromkeys(str(value) for value in team_ids))
    team_rows = {
        str(row.get("team_id")): row
        for row in snapshot.get("teams", [])
        if str(row.get("team_id")) in requested_ids
    }
    missing = [team_id for team_id in requested_ids if team_id not in team_rows]
    if missing:
        raise ValueError("Canonical team(s) missing from season snapshot: " + ", ".join(missing))
    fixtures = snapshot.get("fixtures") or []
    statistics = snapshot.get("statistics") or []
    return {
        team_id: build_provider_neutral_team_profile(
            team_rows[team_id], fixtures, season_id=canonical_season_id,
            statistics=statistics, opponent_strength=opponent_strength,
        )
        for team_id in requested_ids
    }


def load_repository_team_profiles(
    database_url: str,
    team_ids: list[str] | tuple[str, ...],
    season_id: str,
    *,
    snapshot: dict[str, Any] | None = None,
    opponent_strength: dict[str, float] | None = None,
) -> dict[str, dict[str, Any]]:
    """Load one CockroachDB season snapshot and build selected team profiles."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    if snapshot is None:
        from football_repository import get_repository_season_snapshot
        snapshot = get_repository_season_snapshot(
            database_url, str(season_id), fixture_limit=2000
        )
        snapshot = {**snapshot, "season_id": str(season_id)}
    return build_repository_team_profiles(
        snapshot, team_ids, str(season_id), opponent_strength=opponent_strength
    )
