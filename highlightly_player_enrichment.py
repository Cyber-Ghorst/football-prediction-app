"""Highlightly player and team-season performance diagnostics.

Uses only player IDs from an exact, provider-reported Highlightly lineup.
Competition and season rows are selected by exact normalized identity. This
module is diagnostic-only: it never changes Layer 2 profiles or predictions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from competition_crosswalk import normalize_competition_name
from provider_core import normalize_team_name

_PLAYER_FIELDS = (
    "gamesPlayed", "minutesPlayed", "goals", "assists", "penaltiesScored",
    "ownGoals", "yellowCards", "secondYellowCards", "redCards",
    "cleanSheets", "goalsConceded", "substitutedIn", "substitutedOut",
)


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        data = value.get("data")
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        if isinstance(data, dict):
            return [data]
        # Player statistics may be returned as one object.
        if "perCompetition" in value or "perClub" in value:
            return [value]
    return []


def _season(value: Any) -> int | None:
    try:
        return int(str(value).strip()) if value is not None else None
    except (TypeError, ValueError):
        return None


def _exact_competition_rows(rows: list[dict[str, Any]], competition: str, season: int,
                            club: str | None = None) -> list[dict[str, Any]]:
    wanted_league = normalize_competition_name(competition)
    wanted_club = normalize_team_name(club) if club else None
    result = []
    for row in rows:
        if normalize_competition_name(str(row.get("leagueName") or row.get("league") or "")) != wanted_league:
            continue
        if _season(row.get("season")) != int(season):
            continue
        if wanted_club and normalize_team_name(str(row.get("club") or "")) != wanted_club:
            continue
        result.append(row)
    return result


def collect_highlightly_player_enrichment(
    *,
    client: Any,
    lineups: Mapping[str, Any] | None,
    competition: str,
    season: int,
    home_team_name: str,
    away_team_name: str,
    from_date: str | None = None,
    timezone_name: str = "Africa/Nairobi",
    max_players: int = 22,
    require_quota_metadata: bool = False,
) -> dict[str, Any]:
    """Collect exact competition-season stats for lineup starters and both teams.

    Requests at most two team-stat endpoints and max_players player-stat
    endpoints. Substitutes are intentionally excluded to bound quota usage.
    """
    started_at = datetime.now(timezone.utc).isoformat()
    report: dict[str, Any] = {
        "provider": "highlightly",
        "competition": competition,
        "season": int(season),
        "started_at": started_at,
        "fetched_at": "",
        "diagnostic_only": True,
        "player_requests": 0,
        "team_requests": 0,
        "player_statistics_status": "unknown",
        "team_statistics_status": "unknown",
        "players": [],
        "teams": {},
        "errors": {},
        "unknown_players": [],
    }
    if not lineups:
        report["fetched_at"] = datetime.now(timezone.utc).isoformat()
        report["availability"] = "unknown_no_exact_provider_lineup"
        return report

    start_date = from_date or f"{int(season)}-01-01"
    player_jobs: list[tuple[str, dict[str, Any]]] = []
    for side, expected_name in (("home", home_team_name), ("away", away_team_name)):
        team = lineups.get(side) or {}
        actual_name = team.get("team_name")
        if not actual_name or normalize_team_name(actual_name) != normalize_team_name(expected_name):
            report["errors"][f"identity:{side}"] = "Lineup team identity does not match the selected fixture."
            continue
        report["teams"][side] = {
            "team_id": team.get("team_id"),
            "team_name": actual_name,
            "season_statistics": [],
            "source": "highlightly",
        }
        for player in team.get("starting_players") or []:
            if isinstance(player, dict):
                player_jobs.append((side, player))

    # De-duplicate only by provider player ID; never join by a name alone.
    unique_jobs: list[tuple[str, dict[str, Any]]] = []
    seen_ids: set[str] = set()
    for side, player in player_jobs:
        player_id = player.get("player_id")
        if player_id is None:
            report["unknown_players"].append({
                "team": side, "name": player.get("name"),
                "reason": "Provider player ID missing; no name-only lookup attempted.",
            })
            continue
        key = str(player_id)
        if key in seen_ids:
            continue
        seen_ids.add(key)
        unique_jobs.append((side, player))
    unique_jobs = unique_jobs[:max(0, int(max_players))]

    def remaining_quota() -> int | None:
        metadata = getattr(client, "last_metadata", {}) or {}
        raw = metadata.get("requests_remaining")
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    team_jobs = [
        (side, team) for side, team in report["teams"].items()
        if team.get("team_id") is not None
    ]
    planned_requests = len(team_jobs) + len(unique_jobs)
    if require_quota_metadata:
        remaining = remaining_quota()
        report["quota"] = {
            "status": "verified" if remaining is not None else "unknown",
            "requests_remaining_before_enrichment": remaining,
            "planned_requests": planned_requests,
            "guard_enabled": True,
        }
        if remaining is None:
            report["quota"]["status"] = "blocked_unknown_quota"
            report["availability"] = "unknown_quota_metadata"
            report["fetched_at"] = datetime.now(timezone.utc).isoformat()
            return report
        if remaining < planned_requests:
            report["quota"]["status"] = "blocked_insufficient_quota"
            report["availability"] = "unknown_insufficient_quota"
            report["fetched_at"] = datetime.now(timezone.utc).isoformat()
            return report

    for team_index, (side, team) in enumerate(list(report["teams"].items())):
        team_id = team.get("team_id")
        if team_id is None:
            report["errors"][f"team_stats:{side}"] = "Highlightly team ID missing."
            continue
        try:
            if require_quota_metadata:
                required_now = (len(team_jobs) - team_index) + len(unique_jobs)
                available_now = remaining_quota()
                if available_now is None or available_now < required_now:
                    report["errors"]["quota_guard"] = "Stopped before a request because remaining quota could not safely cover the planned calls."
                    break
            report["team_requests"] += 1
            raw = client.team_statistics(team_id, fromDate=start_date, timezone=timezone_name)
            matches = _exact_competition_rows(_rows(raw), competition, int(season))
            team["season_statistics"] = matches
            team["status"] = "matched" if matches else "unknown_no_exact_competition_season_row"
        except Exception as exc:
            report["errors"][f"team_stats:{side}"] = str(exc)

    for player_index, (side, player) in enumerate(unique_jobs):
        player_id = player["player_id"]
        try:
            if require_quota_metadata:
                required_now = len(unique_jobs) - player_index
                available_now = remaining_quota()
                if available_now is None or available_now < required_now:
                    report["errors"]["quota_guard"] = "Stopped before a player request because remaining quota could not safely cover the planned calls."
                    break
            report["player_requests"] += 1
            raw = client.player_statistics(player_id)
            payload_rows = _rows(raw)
            stats_rows = []
            for payload in payload_rows:
                stats_rows.extend(_exact_competition_rows(
                    payload.get("perCompetition") or [], competition, int(season),
                    club=(report["teams"].get(side) or {}).get("team_name"),
                ))
            if not stats_rows:
                report["unknown_players"].append({
                    "team": side, "player_id": str(player_id), "name": player.get("name"),
                    "reason": "No exact club, competition and season statistics row returned.",
                })
                continue
            for stats in stats_rows:
                report["players"].append({
                    "team": side,
                    "player_id": str(player_id),
                    "name": player.get("name"),
                    "position": player.get("position"),
                    "statistics": {field: stats.get(field) for field in _PLAYER_FIELDS},
                    "competition": stats.get("league"),
                    "season": stats.get("season"),
                    "club": stats.get("club"),
                    "source": "highlightly",
                    "source_status": "provider_reported",
                })
        except Exception as exc:
            report["errors"][f"player_stats:{player_id}"] = str(exc)

    if require_quota_metadata:
        report["quota"]["requests_remaining_after_enrichment"] = remaining_quota()
        if report["errors"].get("quota_guard"):
            report["quota"]["status"] = "stopped_by_quota_guard"
        else:
            report["quota"]["status"] = "completed_within_quota"
    report["fetched_at"] = datetime.now(timezone.utc).isoformat()
    report["player_statistics_status"] = (
        "collected" if report["players"] else "unknown_no_matching_player_statistics"
    )
    matched_team_count = sum(
        1 for team in report["teams"].values()
        if team.get("season_statistics")
    )
    report["team_statistics_status"] = (
        "collected" if matched_team_count else "unknown_no_matching_team_statistics"
    )
    # Overall availability must not imply player-level records exist when
    # only team-season rows were returned.
    report["availability"] = report["player_statistics_status"]
    return report
