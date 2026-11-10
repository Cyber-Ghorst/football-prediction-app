"""Conservative Sportmonks fixture normalizer for cross-provider comparison."""
from __future__ import annotations

from typing import Any, Mapping

from canonical_data import MatchNormalizationError, _int_or_none, _parse_datetime
from provider_core import normalize_team_name


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict) and isinstance(value.get("data"), list):
        return [row for row in value["data"] if isinstance(row, dict)]
    return []


def _status(fixture: Mapping[str, Any]) -> str:
    try:
        state_id = int(fixture.get("state_id"))
        if state_id in {5, 7, 8}:
            return "finished"
        if state_id == 1:
            return "scheduled"
        # Keep all documented in-play phases out of the completed-result set.
        if state_id in {2, 3, 4, 6, 9, 21, 22, 25}:
            return "live"
    except (TypeError, ValueError):
        pass
    state = fixture.get("state") or {}
    label = str(state.get("short_name") or state.get("name") or "").casefold()
    if any(word in label for word in ("finished", "full time", "after extra time", "after penalties")):
        return "finished"
    if any(word in label for word in ("live", "in play", "half time", "1st half", "2nd half", "extra time", "penalty")):
        return "live"
    if any(word in label for word in ("not started", "scheduled", "to be played")):
        return "scheduled"
    return "unknown"


def _score_by_participant(fixture: Mapping[str, Any]) -> dict[str, int]:
    rows = _rows(fixture.get("scores"))
    current = [row for row in rows if str(row.get("description") or "").casefold() == "current"]
    result: dict[str, int] = {}
    # Only explicit CURRENT scores represent the full-time score. Never infer
    # a final score from period rows, and use the shared strict score parser.
    for row in current:
        participant_id = row.get("participant_id")
        score = row.get("score")
        goals = score.get("goals") if isinstance(score, dict) else None
        parsed_goals = _int_or_none(goals)
        if participant_id is None or parsed_goals is None:
            continue
        result[str(participant_id)] = parsed_goals
    return result


def canonicalize_sportmonks_fixture(
    fixture: Mapping[str, Any], *, competition_key: str, season: int | str
) -> dict[str, Any]:
    """Normalize one Sportmonks fixture; season is caller-verified calendar year."""
    participants = _rows(fixture.get("participants"))
    by_side = {
        str((row.get("meta") or {}).get("location") or "").casefold(): row
        for row in participants
    }
    home, away = by_side.get("home"), by_side.get("away")
    if not home or not away or not home.get("id") or not away.get("id"):
        raise MatchNormalizationError("Sportmonks fixture is missing identified home/away participants.")
    if not home.get("name") or not away.get("name"):
        raise MatchNormalizationError("Sportmonks fixture is missing home/away team names.")
    kickoff = _parse_datetime(fixture.get("starting_at"))
    scores = _score_by_participant(fixture)
    home_id, away_id = str(home["id"]), str(away["id"])
    return {
        "competition_key": str(competition_key).casefold().strip(),
        "season": int(season),
        "kickoff_utc": kickoff.isoformat(),
        "home": {
            "name": str(home["name"]),
            "normalized_name": normalize_team_name(home["name"]),
            "source_ids": {"sportmonks": home_id},
        },
        "away": {
            "name": str(away["name"]),
            "normalized_name": normalize_team_name(away["name"]),
            "source_ids": {"sportmonks": away_id},
        },
        "status": _status(fixture),
        "home_score": scores.get(home_id),
        "away_score": scores.get(away_id),
        "source_ids": {"sportmonks": str(fixture.get("id") or "")},
        "source": "sportmonks",
        "raw_source_updated_at": fixture.get("updated_at"),
    }
