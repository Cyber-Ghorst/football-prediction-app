"""Read-only comparison of both Layer 2 profile builders over one CockroachDB snapshot."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from football_repository import get_repository_seasons, get_repository_season_snapshot
from provider_neutral_profiles import build_repository_team_profiles
from sportmonks_layer2 import collect_repository_team_profiles


def _id(value: Any) -> str:
    text = str(value or "").strip()
    return text.split(":", 1)[-1]


def _date(value: Any) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        return str(value)


def _same_number(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is right
    try:
        return abs(float(left) - float(right)) <= 1e-9
    except (TypeError, ValueError):
        return left == right


def _match_index(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for match in profile.get("matches") or []:
        key = _id(match.get("fixture_id"))
        if key:
            result[key] = match
    return result


def _compare_team(team_id: str, team_name: str, sport: dict, neutral: dict) -> dict:
    sport_matches = _match_index(sport)
    neutral_matches = _match_index(neutral)
    sport_ids, neutral_ids = set(sport_matches), set(neutral_matches)
    common = sorted(sport_ids & neutral_ids)
    field_checks = {
        "kickoff": lambda a, b: _date(a.get("date")) == _date(b.get("date")),
        "venue": lambda a, b: a.get("venue") == b.get("venue"),
        "opponent": lambda a, b: _id(a.get("opponent_id")) == _id(b.get("opponent_id")),
        "goals_for": lambda a, b: _same_number(a.get("goals_for"), b.get("goals_for")),
        "goals_against": lambda a, b: _same_number(a.get("goals_against"), b.get("goals_against")),
    }
    checks = {name: {"compared": 0, "matched": 0, "mismatched_fixture_ids": []} for name in field_checks}
    statistic_checks = {"compared": 0, "matched": 0, "mismatched": []}
    for fixture_id in common:
        left, right = sport_matches[fixture_id], neutral_matches[fixture_id]
        for name, compare in field_checks.items():
            checks[name]["compared"] += 1
            if compare(left, right):
                checks[name]["matched"] += 1
            else:
                checks[name]["mismatched_fixture_ids"].append(fixture_id)
        left_stats = left.get("statistics") or {}
        right_stats = right.get("statistics") or {}
        for metric in sorted(set(left_stats) & set(right_stats)):
            statistic_checks["compared"] += 1
            if _same_number(left_stats[metric], right_stats[metric]):
                statistic_checks["matched"] += 1
            else:
                statistic_checks["mismatched"].append({
                    "fixture_id": fixture_id, "metric": metric,
                    "sportmonks_value": left_stats[metric],
                    "canonical_value": right_stats[metric],
                })
    return {
        "team_id": team_id,
        "team": team_name,
        "sportmonks_history_count": len(sport_matches),
        "canonical_history_count": len(neutral_matches),
        "common_fixture_count": len(common),
        "sportmonks_only_fixture_ids": sorted(sport_ids - neutral_ids),
        "canonical_only_fixture_ids": sorted(neutral_ids - sport_ids),
        "common_fixture_ids": common,
        "shared_match_fields": checks,
        "shared_statistics": statistic_checks,
        "sportmonks_history_diagnostics": sport.get("data_quality", {}),
        "canonical_history_diagnostics": neutral.get("data_quality", {}),
        "sportmonks_tactical_summary": sport.get("tactical_summary", {}),
        "canonical_tactical_summary": neutral.get("tactical_summary", {}),
        "sportmonks_tactical_evidence": sport.get("tactical_evidence", {}),
        "canonical_tactical_evidence": neutral.get("tactical_evidence", {}),
        "lineups_available_sportmonks": (sport.get("lineups") or {}).get("available"),
        "lineups_available_canonical": (neutral.get("lineups") or {}).get("available"),
    }


def main() -> int:
    database_url = os.getenv("PROVIDER_DATABASE_URL", "")
    if not database_url:
        raise SystemExit("PROVIDER_DATABASE_URL secret is missing.")
    seasons = get_repository_seasons(database_url)
    seasons.sort(
        key=lambda row: (
            bool(row.get("is_current")),
            str(row.get("start_date") or ""),
            str(row.get("season_id") or ""),
        ),
        reverse=True,
    )
    selected = None
    snapshot = None
    selection_errors = []
    for season in seasons:
        season_id = str(season.get("season_id") or "")
        if not season_id:
            continue
        try:
            candidate = get_repository_season_snapshot(database_url, season_id, fixture_limit=2000)
            if candidate.get("teams") and candidate.get("fixtures"):
                selected, snapshot = season, candidate
                break
        except Exception as exc:  # retain only safe exception type, never connection details
            selection_errors.append({"season_id": season_id, "error_type": type(exc).__name__})
    if selected is None or snapshot is None:
        raise SystemExit("No readable season snapshot with teams and fixtures was found.")

    team_rows = {str(row.get("team_id")): row for row in snapshot.get("teams", [])}
    team_ids = sorted(team_rows)
    if not team_ids:
        raise SystemExit("The selected season snapshot contains no teams.")
    sport_profiles = collect_repository_team_profiles(
        database_url, team_ids, str(selected["season_id"]), season_snapshot={
            "season_id": str(selected["season_id"]),
            "teams": snapshot.get("teams") or [],
            "fixtures": snapshot.get("fixtures") or [],
            "statistics": snapshot.get("statistics") or [],
        },
    )
    neutral_profiles = build_repository_team_profiles(
        {
            "season_id": str(selected["season_id"]),
            "teams": snapshot.get("teams") or [],
            "fixtures": snapshot.get("fixtures") or [],
            "statistics": snapshot.get("statistics") or [],
        },
        team_ids,
        str(selected["season_id"]),
    )
    teams = [
        _compare_team(team_id, team_rows[team_id].get("name") or team_id,
                      sport_profiles[team_id], neutral_profiles[team_id])
        for team_id in team_ids
    ]
    totals = {
        "teams_compared": len(teams),
        "teams_with_ten_common_fixtures": sum(row["common_fixture_count"] >= 10 for row in teams),
        "common_fixtures": sum(row["common_fixture_count"] for row in teams),
        "shared_match_fields_compared": sum(
            item["compared"] for row in teams for item in row["shared_match_fields"].values()
        ),
        "shared_match_field_matches": sum(
            item["matched"] for row in teams for item in row["shared_match_fields"].values()
        ),
        "shared_statistic_values_compared": sum(row["shared_statistics"]["compared"] for row in teams),
        "shared_statistic_values_matched": sum(row["shared_statistics"]["matched"] for row in teams),
        "teams_with_fixture_set_differences": sum(
            bool(row["sportmonks_only_fixture_ids"] or row["canonical_only_fixture_ids"]) for row in teams
        ),
        "teams_with_shared_field_mismatches": sum(
            any(item["mismatched_fixture_ids"] for item in row["shared_match_fields"].values())
            for row in teams
        ),
    }
    report = {
        "report_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audit_mode": "read_only",
        "database_writes": False,
        "prediction_engine_modified": False,
        "live_prediction_route_modified": False,
        "season": {
            "season_id": str(selected.get("season_id")),
            "season_name": selected.get("name"),
            "league_id": selected.get("league_id"),
            "team_rows": len(snapshot.get("teams") or []),
            "fixture_rows": len(snapshot.get("fixtures") or []),
            "statistics_rows": len(snapshot.get("statistics") or []),
            "fixtures_with_archived_raw_payload": sum(
                isinstance(row.get("raw_payload"), dict) for row in snapshot.get("fixtures") or []
            ),
        },
        "selection_errors": selection_errors,
        "totals": totals,
        "interpretation": (
            "Compare exact common fixture identities and shared values. Provider-specific "
            "coverage, provenance, tactical calculations and missing fields are reported, "
            "not forced equal or imputed. This audit does not authorize live-route promotion."
        ),
        "teams": teams,
    }
    output = Path("reports/layer2_real_history_parity")
    output.mkdir(parents=True, exist_ok=True)
    (output / "latest.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "audit_status": "completed",
        "season_id": report["season"]["season_id"],
        "totals": totals,
        "report_path": str(output / "latest.json"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
