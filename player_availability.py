"""Fail-closed, evidence-based player availability scoring.

A score is produced only from a complete squad roster where every player has
an evidenced importance weight and a known available/unavailable status.
Partial sidelined lists and unconfirmed lineups are never treated as complete.
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
    """Build complete, fixture-specific availability evidence from Sportmonks.

    Player importance is relative current-season minutes played (type_id 119).
    A sidelined record is considered unavailable only when its date range and
    completed flag establish that the absence overlaps the selected kickoff.
    Any incomplete or conflicting evidence leaves the component unknown.
    """
    base = {
        "source": "sportmonks",
        "fixture_id": fixture_id,
        "team_id": int(team_id),
        "season_id": int(season_id),
        "roster_complete": False,
        "sidelined_feed_available": bool(sidelined_feed_available),
        "squad_rows_received": len(squad_rows) if isinstance(squad_rows, list) else 0,
        "reported_sidelined_count": len(sidelined_rows) if isinstance(sidelined_rows, list) else None,
    }

    def unknown(reason: str, **extra: Any) -> dict[str, Any]:
        return {**base, "reason": reason, **extra}

    if not isinstance(squad_rows, list) or not squad_rows:
        return unknown("The season-specific squad endpoint returned no complete player list.")
    if not sidelined_feed_available:
        return unknown("The exact fixture response did not confirm that the sidelined feed was supplied.")
    if not isinstance(sidelined_rows, list):
        return unknown("The fixture sidelined response was not a verifiable list.")

    kickoff_date = _availability_date(kickoff)
    if kickoff_date is None:
        return unknown("The selected fixture kickoff date is missing or invalid.")

    squad: dict[str, dict[str, Any]] = {}
    for row in squad_rows:
        if not isinstance(row, dict):
            return unknown("The season squad contains a malformed player-statistic row.")
        try:
            row_team_id = int(row.get("team_id"))
            row_season_id = int(row.get("season_id"))
            player_id_value = row.get("player_id")
            player_id = str(int(player_id_value))
        except (TypeError, ValueError):
            return unknown("A squad row is missing a valid player, team or season ID.")
        if row_team_id != int(team_id) or row_season_id != int(season_id):
            return unknown("A squad row belongs to a different team or season.")
        if player_id in squad:
            return unknown("Duplicate player IDs make the season squad ambiguous.")

        if row.get("has_values") is False:
            return unknown("At least one registered player has no season-statistic values for an importance estimate.")
        details = row.get("details")
        if isinstance(details, dict):
            details = details.get("data")
        if not isinstance(details, list):
            return unknown("Season player-statistic details are missing.")
        minutes_detail = None
        for detail in details:
            if not isinstance(detail, dict):
                continue
            try:
                if int(detail.get("type_id")) == 119:
                    minutes_detail = detail
                    break
            except (TypeError, ValueError):
                continue
        if minutes_detail is None:
            return unknown("Minutes-played evidence (Sportmonks type 119) is missing for a squad player.")
        minutes = _minutes_value(minutes_detail.get("value"))
        if minutes is None:
            return unknown("A player's minutes-played value is invalid.")
        player = row.get("player") if isinstance(row.get("player"), dict) else {}
        if player.get("id") is not None and str(player.get("id")) != player_id:
            return unknown("The included player profile ID does not match its squad row.")
        squad[player_id] = {
            "player_id": int(player_id),
            "player_name": player.get("display_name") or player.get("name") or player.get("common_name"),
            "minutes_played": minutes,
        }

    max_minutes = max((row["minutes_played"] for row in squad.values()), default=0.0)
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
        if player_id not in squad:
            return unknown("A sidelined player is absent from the selected season squad.")
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
    for player_id, row in squad.items():
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
        "players_assessed": len(squad_players),
        "importance_method": "season_minutes_played_relative_to_squad_max",
        "reason": "Season squad, minutes-played statistics and exact-fixture sidelined feed passed identity and date checks.",
    }

