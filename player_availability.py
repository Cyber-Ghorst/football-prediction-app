"""Fail-closed, evidence-based player availability scoring.

A score is produced only from a complete squad roster where every player has
an evidenced importance weight and a known available/unavailable status.
Partial sidelined lists and unconfirmed lineups are never treated as complete.
"""
from __future__ import annotations

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
            "reason": "The provider has not confirmed a complete squad roster.",
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
