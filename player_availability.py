"""Fail-closed, evidence-based player availability scoring.

Availability is scored only when the current squad, player importance and
fixture-specific sidelined feed are all evidenced. Partial feeds stay unknown.
"""
from __future__ import annotations

from datetime import datetime
import math
from typing import Any


def assess_player_availability(evidence: dict[str, Any] | None) -> dict[str, Any]:
    """Calculate importance-weighted availability (0-100), or preserve unknown.

    Expected evidence:
      roster_complete: bool explicitly asserted by the source
      squad_players: complete list of {player_id, status, importance}
      source: provenance label
      fixture_id: exact fixture identity
    """
    evidence = evidence if isinstance(evidence, dict) else {}
    players = evidence.get("squad_players")
    if evidence.get("roster_complete") is not True:
        return {
            "score": None,
            "status": "unknown",
            "reason": evidence.get("reason") or "The provider has not confirmed a complete squad roster.",
            "source": evidence.get("source"),
            "fixture_id": evidence.get("fixture_id"),
            "players_assessed": 0,
        }
    if not isinstance(players, list) or not players:
        return {
            "score": None,
            "status": "unknown",
            "reason": "A complete, non-empty player list was not supplied.",
            "source": evidence.get("source"),
            "fixture_id": evidence.get("fixture_id"),
            "players_assessed": 0,
        }

    seen: set[str] = set()
    weighted_available = 0.0
    total_importance = 0.0
    for player in players:
        if not isinstance(player, dict):
            return _unknown(evidence, "A player record is malformed.", len(seen))
        player_id = player.get("player_id")
        if player_id is None or str(player_id).strip() == "":
            return _unknown(evidence, "A player record has no stable player ID.", len(seen))
        player_id = str(player_id)
        if player_id in seen:
            return _unknown(evidence, "Duplicate player IDs make the roster ambiguous.", len(seen))
        seen.add(player_id)

        status = player.get("status")
        if status not in {"available", "unavailable"}:
            return _unknown(evidence, "At least one player's availability status is unknown.", len(seen))
        importance = player.get("importance")
        if isinstance(importance, bool) or not isinstance(importance, (int, float)):
            return _unknown(evidence, "At least one player lacks an evidenced importance weight.", len(seen))
        importance = float(importance)
        if not 0.0 <= importance <= 100.0:
            return _unknown(evidence, "Player importance weights must be between 0 and 100.", len(seen))
        total_importance += importance
        if status == "available":
            weighted_available += importance

    if total_importance <= 0:
        return _unknown(evidence, "Total player-importance weight must be greater than zero.", len(seen))

    return {
        "score": round(weighted_available / total_importance * 100.0, 1),
        "status": "scored",
        "reason": "Calculated from a complete roster, known player statuses and evidenced importance weights.",
        "source": evidence.get("source"),
        "fixture_id": evidence.get("fixture_id"),
        "players_assessed": len(seen),
        "importance_weight_total": round(total_importance, 2),
        "formula": "100 × available-player importance / total squad importance",
    }


def _unknown(evidence: dict[str, Any], reason: str, count: int) -> dict[str, Any]:
    return {
        "score": None,
        "status": "unknown",
        "reason": reason,
        "source": evidence.get("source"),
        "fixture_id": evidence.get("fixture_id"),
        "players_assessed": count,
    }


def _availability_date(value: Any):
    if value is None or str(value).strip() == "":
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        return None


def _minutes_value(value: Any) -> float | None:
    if isinstance(value, dict):
        for key in ("total", "minutes", "value"):
            if key in value:
                value = value[key]
                break
    if isinstance(value, bool):
        return None
    try:
        minutes = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(minutes) or minutes < 0:
        return None
    return minutes


def build_sportmonks_availability_evidence(
    *,
    squad_rows: Any,
    sidelined_rows: Any,
    sidelined_feed_available: bool,
    team_id: int,
    season_id: int,
    fixture_id: int | str,
    kickoff: Any,
) -> dict[str, Any]:
    """Build evidence from the current extended squad and season player statistics.

    The extended squad endpoint supplies an explicit in_squad flag. Its nested
    season statistics provide minutes played (type_id 119), used as the
    importance proxy. Fixture-specific sidelined records determine status.
    Incomplete, conflicting or out-of-season data remains unknown.
    """
    base = {
        "source": "sportmonks",
        "fixture_id": fixture_id,
        "team_id": int(team_id),
        "season_id": int(season_id),
        "roster_complete": False,
        "sidelined_feed_available": bool(sidelined_feed_available),
        "injury_data_available": bool(sidelined_feed_available),
        "reported_sidelined": list(sidelined_rows) if sidelined_feed_available and isinstance(sidelined_rows, list) else None,
        "reported_unavailable_count": len(sidelined_rows) if sidelined_feed_available and isinstance(sidelined_rows, list) else None,
        "squad_rows_received": len(squad_rows) if isinstance(squad_rows, list) else 0,
        "reported_sidelined_count": len(sidelined_rows) if sidelined_feed_available and isinstance(sidelined_rows, list) else None,
    }

    diagnostics: dict[str, Any] = {
        "current_squad_rows_seen": 0,
        "matching_team_season_statistics_rows": 0,
        "players_with_minutes_detail": 0,
        "players_missing_minutes_detail": [],
        "minutes_type_ids_seen": [],
        "sample_detail_shapes": [],
    }

    def unknown(reason: str, **extra: Any) -> dict[str, Any]:
        return {**base, **diagnostics, "reason": reason, **extra}

    if not isinstance(squad_rows, list) or not squad_rows:
        return unknown("The extended squad endpoint returned no player list.")
    if not sidelined_feed_available:
        return unknown("The exact fixture response did not confirm that the sidelined feed was supplied.")
    if not isinstance(sidelined_rows, list):
        return unknown("The fixture sidelined response was not a verifiable list.")

    kickoff_date = _availability_date(kickoff)
    if kickoff_date is None:
        return unknown("The selected fixture kickoff date is missing or invalid.")

    current_players: dict[str, dict[str, Any]] = {}
    for row in squad_rows:
        if not isinstance(row, dict) or not isinstance(row.get("in_squad"), bool):
            return unknown("An extended squad row is missing its explicit in_squad status.")
        if row["in_squad"] is False:
            continue
        diagnostics["current_squad_rows_seen"] += 1
        try:
            player_id = str(int(row.get("id")))
        except (TypeError, ValueError):
            return unknown("A current-squad player has no valid player ID.")
        if player_id in current_players:
            return unknown("Duplicate player IDs make the current squad ambiguous.")

        statistics = row.get("statistics")
        if isinstance(statistics, dict):
            statistics = statistics.get("data")
        if not isinstance(statistics, list):
            return unknown("Season player statistics are missing for a current-squad player.")
        matching_statistics = []
        for statistic in statistics:
            if not isinstance(statistic, dict):
                continue
            try:
                statistic_team_id = int(statistic.get("team_id"))
                statistic_season_id = int(statistic.get("season_id"))
            except (TypeError, ValueError):
                continue
            if statistic_team_id == int(team_id) and statistic_season_id == int(season_id):
                matching_statistics.append(statistic)
        diagnostics["matching_team_season_statistics_rows"] += len(matching_statistics)
        if len(matching_statistics) != 1:
            return unknown("A current-squad player does not have exactly one matching team-season statistic row.")
        statistic = matching_statistics[0]
        if statistic.get("player_id") is None:
            return unknown("A team-season statistic row has no player ID.")
        try:
            if int(statistic["player_id"]) != int(player_id):
                return unknown("A player-statistic row belongs to a different player.")
        except (TypeError, ValueError):
            return unknown("A player-statistic row has an invalid player ID.")
        if statistic.get("has_values") is False:
            return unknown("A current-squad player has no season-statistic values for an importance estimate.")

        details = statistic.get("details")
        if isinstance(details, dict):
            details = details.get("data")
        if not isinstance(details, list):
            return unknown("Season player-statistic details are missing.")
        minutes_detail = None
        player_type_ids = []
        for detail in details:
            if not isinstance(detail, dict):
                continue
            detail_type_id = detail.get("type_id")
            if detail_type_id is None and isinstance(detail.get("type"), dict):
                detail_type_id = detail["type"].get("id")
            if len(diagnostics["sample_detail_shapes"]) < 5:
                diagnostics["sample_detail_shapes"].append({
                    "keys": sorted(detail.keys()),
                    "type_id": detail_type_id,
                    "value_type": type(detail.get("value")).__name__,
                })
            try:
                parsed_type_id = int(detail_type_id)
                if parsed_type_id not in diagnostics["minutes_type_ids_seen"]:
                    diagnostics["minutes_type_ids_seen"].append(parsed_type_id)
                player_type_ids.append(parsed_type_id)
                if parsed_type_id == 119:
                    minutes_detail = detail
            except (TypeError, ValueError):
                continue
        if minutes_detail is None:
            diagnostics["players_missing_minutes_detail"].append({
                "player_id": int(player_id),
                "player_name": row.get("display_name") or row.get("name") or row.get("common_name"),
                "detail_type_ids": player_type_ids[:20],
            })
            return unknown("Minutes-played evidence (Sportmonks type 119) is missing for a current-squad player.")
        diagnostics["players_with_minutes_detail"] += 1
        minutes = _minutes_value(minutes_detail.get("value"))
        if minutes is None:
            return unknown("A player's minutes-played value is invalid.")
        current_players[player_id] = {
            "player_id": int(player_id),
            "player_name": row.get("display_name") or row.get("name") or row.get("common_name"),
            "minutes_played": minutes,
        }

    if not current_players:
        return unknown("The extended squad response contains no players marked in_squad.")

    max_minutes = max((row["minutes_played"] for row in current_players.values()), default=0.0)
    if max_minutes <= 0:
        return unknown("No positive season minutes are available to establish player importance.")

    unavailable_ids: set[str] = set()
    for row in sidelined_rows:
        if not isinstance(row, dict):
            return unknown("A sidelined record is malformed.")
        player_id_value = row.get("player_id")
        if player_id_value is None:
            return unknown("A sidelined record has no stable player ID.")
        try:
            player_id = str(int(player_id_value))
        except (TypeError, ValueError):
            return unknown("A sidelined record has an invalid player ID.")
        if player_id not in current_players:
            return unknown("A sidelined player is absent from the current squad.")
        row_fixture_id = row.get("fixture_id")
        if row_fixture_id is not None and str(row_fixture_id) != str(fixture_id):
            return unknown("A sidelined record belongs to a different fixture.")
        row_season_id = row.get("season_id")
        if row_season_id is not None:
            try:
                if int(row_season_id) != int(season_id):
                    return unknown("A sidelined record belongs to a different season.")
            except (TypeError, ValueError):
                return unknown("A sidelined record has an invalid season ID.")
        row_team = row.get("team_id")
        if row_team is not None:
            try:
                if int(row_team) != int(team_id):
                    return unknown("A sidelined record belongs to a different team.")
            except (TypeError, ValueError):
                return unknown("A sidelined record has an invalid team ID.")

        start_date = _availability_date(row.get("start_date"))
        if start_date is None:
            return unknown("A sidelined record has no valid absence start date.")
        if start_date > kickoff_date:
            continue

        completed_value = row.get("completed")
        if isinstance(completed_value, bool):
            completed = completed_value
        elif str(completed_value).strip().casefold() in {"true", "1", "yes"}:
            completed = True
        elif str(completed_value).strip().casefold() in {"false", "0", "no"}:
            completed = False
        else:
            return unknown("A sidelined record has no verifiable completed status.")

        end_raw = row.get("end_date")
        end_date = _availability_date(end_raw) if end_raw not in (None, "") else None
        if end_raw not in (None, "") and end_date is None:
            return unknown("A sidelined record has an invalid absence end date.")

        if completed:
            if end_date is None:
                return unknown("A completed sidelined record is missing its return date.")
            if end_date >= kickoff_date:
                unavailable_ids.add(player_id)
        else:
            if end_date is not None and end_date < kickoff_date:
                return unknown("A pending absence has an expected end date before kickoff; return status is uncertain.")
            unavailable_ids.add(player_id)

    squad_players = []
    for player_id, row in current_players.items():
        minutes = row["minutes_played"]
        if player_id in unavailable_ids and minutes <= 0:
            return unknown("An unavailable player has no season minutes from which to evidence importance.")
        squad_players.append({
            "player_id": row["player_id"],
            "player_name": row["player_name"],
            "status": "unavailable" if player_id in unavailable_ids else "available",
            "importance": round(minutes / max_minutes * 100.0, 2),
            "minutes_played": minutes,
        })

    return {
        **base,
        "roster_complete": True,
        "squad_players": squad_players,
        **diagnostics,
        "players_assessed": len(squad_players),
        "current_squad_players": len(current_players),
        "importance_method": "current_squad_season_minutes_played_relative_to_squad_max",
        "reason": "Current extended squad, matching team-season minutes and exact-fixture sidelined feed passed identity and date checks.",
    }
