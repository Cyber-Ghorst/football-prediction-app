"""Normalize OpenScores fixture payloads without merging provider identities.

The output is an observation. It is not a canonical fixture until every entity
has a verified provider_entity_links crosswalk and the fixture fingerprint is
uniquely reconciled against the canonical repository.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def _nonblank(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    return text or None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _kickoff(value: Any) -> datetime | None:
    text = _nonblank(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _score_value(score: Mapping[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = score.get(key)
        if isinstance(value, dict):
            value = value.get("value") if "value" in value else value.get("goals")
        if value is None:
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError, OverflowError):
            continue
        if parsed >= 0:
            return parsed
    return None


def normalize_openscores_fixtures(
    records: list[dict[str, Any]],
    *,
    league_id: Any,
    season_id: Any,
    retrieved_at_utc: str | None = None,
) -> dict[str, Any]:
    """Normalize a returned season fixture page and report every rejected row."""
    league_key = _nonblank(league_id)
    season_key = _nonblank(season_id)
    if not league_key or not season_key:
        raise ValueError("league_id and season_id context are required")
    if not isinstance(records, list):
        raise ValueError("records must be a list")

    accepted: dict[str, dict[str, Any]] = {}
    rejected = {
        "not_a_record": 0,
        "missing_fixture_id": 0,
        "missing_or_invalid_kickoff": 0,
        "missing_or_invalid_season": 0,
        "missing_home_team_identity": 0,
        "missing_away_team_identity": 0,
        "same_home_and_away_team": 0,
        "duplicate_fixture_id": 0,
    }

    for record in records:
        if not isinstance(record, dict):
            rejected["not_a_record"] += 1
            continue
        fixture_id = _nonblank(record.get("id") or record.get("fixture_id"))
        if not fixture_id:
            rejected["missing_fixture_id"] += 1
            continue

        kickoff = _kickoff(
            record.get("scheduled_kickoff_at")
            or record.get("starting_at")
            or record.get("kickoff_at")
        )
        if kickoff is None:
            rejected["missing_or_invalid_kickoff"] += 1
            continue

        record_season = _nonblank(record.get("season_id")) or season_key
        if record_season != season_key:
            rejected["missing_or_invalid_season"] += 1
            continue

        home = _as_dict(record.get("home_team"))
        away = _as_dict(record.get("away_team"))
        home_id, away_id = _nonblank(home.get("id")), _nonblank(away.get("id"))
        if not home_id or not _nonblank(home.get("name")):
            rejected["missing_home_team_identity"] += 1
            continue
        if not away_id or not _nonblank(away.get("name")):
            rejected["missing_away_team_identity"] += 1
            continue
        if home_id == away_id:
            rejected["same_home_and_away_team"] += 1
            continue
        if fixture_id in accepted:
            rejected["duplicate_fixture_id"] += 1
            continue

        score = _as_dict(record.get("score"))
        source_ids = record.get("source_ids")
        if not isinstance(source_ids, dict):
            source_ids = {}
        status = _nonblank(record.get("status")) or "unknown"
        accepted[fixture_id] = {
            "provider": "openscores",
            "provider_fixture_id": fixture_id,
            "provider_league_id": league_key,
            "provider_season_id": season_key,
            "provider_home_team_id": home_id,
            "provider_away_team_id": away_id,
            "home_team_name": str(home["name"]).strip(),
            "away_team_name": str(away["name"]).strip(),
            "kickoff_utc": kickoff,
            "status": status,
            "home_goals": _score_value(score, ("home_ft_score", "home_score", "home")),
            "away_goals": _score_value(score, ("away_ft_score", "away_score", "away")),
            "source_ids": source_ids,
            "retrieved_at_utc": retrieved_at_utc,
            "raw_payload": record,
            "reconciliation_status": "pending_entity_mapping",
            "canonical_fixture_id": None,
        }

    return {
        "provider": "openscores",
        "fixtures": list(accepted.values()),
        "fixtures_received": len(records),
        "fixtures_normalized": len(accepted),
        "fixtures_rejected": sum(rejected.values()),
        "rejected": rejected,
    }
