"""Strict, fail-closed extraction of final 90-minute Sportmonks scores."""
from __future__ import annotations

import re
from typing import Any, Mapping


COMPLETED_STATE_IDS = {5, 7, 8}


def _normalise_name(value: Any) -> str:
    return "".join(character for character in str(value or "").casefold() if character.isalnum())


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        if isinstance(value.get("data"), list):
            return [item for item in value["data"] if isinstance(item, dict)]
        if isinstance(value.get("data"), dict):
            return [value["data"]]
    return []


def _season_year(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("starting_at") or value.get("name") or value.get("year")
    match = re.search(r"\b(20\d{2})\b", str(value or ""))
    return match.group(1) if match else ""


def _participant_sides(fixture: Mapping[str, Any]) -> dict[str, str]:
    sides: dict[str, str] = {}
    for participant in _rows(fixture.get("participants")):
        location = str((participant.get("meta") or {}).get("location") or "").casefold()
        if location in {"home", "away"}:
            sides[location] = _normalise_name(participant.get("name"))
    return sides


def _score_pairs(fixture: Mapping[str, Any], descriptions: set[str]) -> dict[str, int] | None:
    pairs: dict[str, int] = {}
    for row in _rows(fixture.get("scores")):
        description = str(row.get("description") or "").upper()
        if description not in descriptions:
            continue
        score = row.get("score") or {}
        side = str(score.get("participant") or row.get("participant") or "").casefold()
        goals = score.get("goals")
        if side not in {"home", "away"} or goals is None:
            continue
        try:
            numeric = float(goals)
        except (TypeError, ValueError):
            continue
        if not numeric.is_integer() or numeric < 0:
            continue
        pairs[side] = int(numeric)
    return pairs if set(pairs) == {"home", "away"} else None


def group_completed_fixture_candidates(
    records: list[Mapping[str, Any]], now: Any
) -> list[list[Mapping[str, Any]]]:
    """Group blank-score, already-kicked-off Sportmonks records by fixture ID.

    A fixture is returned once even when the ledger contains repeated forecasts.
    Rows with any existing score value are excluded so manual results are preserved.
    """
    from datetime import datetime, timezone

    if not isinstance(now, datetime):
        raise TypeError("now must be a datetime")
    current = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for record in records:
        if str(record.get("fixture_provider") or "").strip().casefold() != "sportmonks":
            continue
        fixture_id = str(record.get("fixture_id") or "").strip()
        if not fixture_id:
            continue
        if record.get("actual_home_goals") not in (None, "") or record.get("actual_away_goals") not in (None, ""):
            continue
        try:
            kickoff = datetime.fromisoformat(
                str(record.get("kickoff_at") or "").replace("Z", "+00:00")
            )
        except (TypeError, ValueError):
            continue
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        if kickoff.astimezone(timezone.utc) > current:
            continue
        key = ("sportmonks", fixture_id)
        grouped.setdefault(key, []).append(record)
    return list(grouped.values())


def verified_final_score(record: Mapping[str, Any], fixture: Mapping[str, Any]) -> tuple[int, int] | None:
    """Return a verified 90-minute score, otherwise None.

    Requires exact provider fixture ID, exact home/away team names, competition,
    season year, a completed Sportmonks state, and an unambiguous 90-minute score.
    For AET/penalty matches, CURRENT may include extra time/shootout, so only the
    explicit 2ND_HALF score is accepted.
    """
    try:
        if str(fixture.get("id")) != str(record.get("fixture_id")):
            return None
        state_id = int(fixture.get("state_id") or (fixture.get("state") or {}).get("id") or 0)
    except (TypeError, ValueError):
        return None
    if state_id not in COMPLETED_STATE_IDS:
        return None

    sides = _participant_sides(fixture)
    if sides.get("home") != _normalise_name(record.get("home_team")):
        return None
    if sides.get("away") != _normalise_name(record.get("away_team")):
        return None

    league = fixture.get("league") or {}
    if _normalise_name(league.get("name")) != _normalise_name(record.get("competition")):
        return None
    season_year = _season_year(fixture.get("season"))
    if not season_year or season_year != str(record.get("season") or "")[:4]:
        return None

    score = _score_pairs(fixture, {"2ND_HALF"})
    if score is None and state_id == 5:
        score = _score_pairs(fixture, {"CURRENT"})
    if score is None:
        return None
    return score["home"], score["away"]
