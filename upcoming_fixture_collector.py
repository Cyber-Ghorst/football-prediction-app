"""Discover and persist upcoming Sportmonks fixtures for the rolling seven-day window.

This collector is intentionally independent of the prediction engine. It only
stores provider-confirmed scheduled fixtures and never fabricates missing data.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from sportmonks import SportmonksClient


WINDOW_DAYS = 7
DAILY_FIXTURE_TARGET = 90
FIXTURE_INCLUDE = "league;season;participants;state;venue;scores"

# Explicit name-based tiers avoid reliance on provider-specific numeric league IDs.
MAJOR_COMPETITION_TIERS = {
    1: (
        "premier league", "english premier league", "epl", "la liga", "laliga",
        "serie a", "bundesliga", "ligue 1", "champions league",
        "uefa champions league", "europa league", "uefa europa league",
    ),
    2: (
        "championship", "english championship", "eredivisie", "primeira liga",
        "liga portugal", "scottish premiership", "mls", "major league soccer",
        "brasileirao", "serie a brazil", "copa libertadores",
        "africa cup of nations", "afcon", "caf champions league",
        "african champions league", "asian champions league",
        "afc champions league", "world cup", "fifa world cup",
        "uefa conference league", "conference league",
    ),
}
MAX_HIGHLIGHTED_FIXTURES = 50


def _competition_priority(fixture: Mapping[str, Any]) -> int:
    """Return a lower-is-better tier for recognized major competitions."""
    league = fixture.get("league") if isinstance(fixture.get("league"), dict) else {}
    name = str(league.get("name") or fixture.get("league_name") or "").strip().casefold()
    normalized = " ".join(name.replace("_", " ").replace("-", " ").split())
    for tier, aliases in MAJOR_COMPETITION_TIERS.items():
        if normalized in aliases:
            return tier
    return 3


def select_highlighted_fixtures(
    fixtures: list[dict[str, Any]],
    *,
    limit: int = MAX_HIGHLIGHTED_FIXTURES,
) -> list[dict[str, Any]]:
    """Select up to 50 major-competition fixtures without shrinking the catalogue."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer.")
    ranked = []
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue
        row = dict(fixture)
        row["highlight_priority"] = _competition_priority(row)
        row["is_highlighted"] = True
        ranked.append(row)
    ranked.sort(
        key=lambda row: (
            row["highlight_priority"],
            row.get("starting_at_timestamp", 0),
            int(row.get("id", 0)) if str(row.get("id", "")).isdigit() else 0,
        )
    )
    return ranked[:min(limit, MAX_HIGHLIGHTED_FIXTURES)]




def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        data = value.get("data")
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        if isinstance(data, dict):
            return [data]
    return []


def _positive_id(value: Any) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    text = str(value).strip()
    return text if text.isdigit() and int(text) > 0 else None


def _kickoff_timestamp(fixture: Mapping[str, Any]) -> int | None:
    raw_timestamp = fixture.get("starting_at_timestamp")
    if raw_timestamp is not None:
        try:
            value = float(raw_timestamp)
            if value > 100_000_000_000:
                value /= 1000
            if value > 0:
                return int(value)
        except (TypeError, ValueError, OverflowError):
            pass
    raw_date = fixture.get("starting_at")
    if not raw_date:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw_date).strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.astimezone(timezone.utc).timestamp())
    except (TypeError, ValueError, OverflowError):
        return None


def _scheduled(fixture: Mapping[str, Any]) -> bool:
    state_id = fixture.get("state_id")
    try:
        if int(state_id) == 1:
            return True
    except (TypeError, ValueError):
        pass
    state = fixture.get("state") or fixture.get("status") or {}
    if isinstance(state, dict):
        label = state.get("short_name") or state.get("name") or state.get("short") or ""
    else:
        label = state
    return str(label).strip().casefold() in {
        "ns", "not started", "scheduled", "to be played",
        "fixture not started", "not played", "tbd",
    }


def _participants(fixture: Mapping[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    home = away = None
    for participant in _rows(fixture.get("participants")):
        meta = participant.get("meta") if isinstance(participant.get("meta"), dict) else {}
        location = str(meta.get("location") or participant.get("location") or "").casefold()
        if location == "home":
            home = participant
        elif location == "away":
            away = participant
    return home, away


def normalize_upcoming_fixtures(
    fixtures: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    window_days: int = WINDOW_DAYS,
) -> dict[str, Any]:
    """Validate, deduplicate and sort provider fixtures inside a strict time window."""
    if isinstance(window_days, bool) or not isinstance(window_days, int) or not 1 <= window_days <= 7:
        raise ValueError("window_days must be an integer from 1 through 7.")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    start_ts = current.timestamp()
    end_ts = (current + timedelta(days=window_days)).timestamp()

    accepted: dict[str, dict[str, Any]] = {}
    excluded = {
        "missing_fixture_id": 0,
        "missing_or_invalid_kickoff": 0,
        "outside_window": 0,
        "not_scheduled": 0,
        "missing_competition_or_season": 0,
        "missing_home_or_away": 0,
        "duplicate_fixture_id": 0,
    }

    for source in fixtures:
        if not isinstance(source, dict):
            continue
        fixture = dict(source)
        fixture_id = _positive_id(fixture.get("id"))
        if fixture_id is None:
            excluded["missing_fixture_id"] += 1
            continue
        kickoff = _kickoff_timestamp(fixture)
        if kickoff is None:
            excluded["missing_or_invalid_kickoff"] += 1
            continue
        if not start_ts < kickoff <= end_ts:
            excluded["outside_window"] += 1
            continue
        if not _scheduled(fixture):
            excluded["not_scheduled"] += 1
            continue

        league = fixture.get("league") if isinstance(fixture.get("league"), dict) else {}
        season = fixture.get("season") if isinstance(fixture.get("season"), dict) else {}
        league_id = _positive_id(fixture.get("league_id") or league.get("id"))
        season_id = _positive_id(fixture.get("season_id") or season.get("id"))
        if league_id is None or season_id is None:
            excluded["missing_competition_or_season"] += 1
            continue

        home, away = _participants(fixture)
        if (
            not home or not away
            or _positive_id(home.get("id")) is None
            or _positive_id(away.get("id")) is None
            or not str(home.get("name") or "").strip()
            or not str(away.get("name") or "").strip()
            or str(home.get("id")) == str(away.get("id"))
        ):
            excluded["missing_home_or_away"] += 1
            continue

        if fixture_id in accepted:
            excluded["duplicate_fixture_id"] += 1
            continue

        fixture["id"] = fixture_id
        fixture["league_id"] = league_id
        fixture["season_id"] = season_id
        fixture["starting_at_timestamp"] = kickoff
        fixture["_collector_kickoff_utc"] = datetime.fromtimestamp(
            kickoff, timezone.utc
        ).isoformat()
        accepted[fixture_id] = fixture

    rows = sorted(
        accepted.values(),
        key=lambda row: (row["starting_at_timestamp"], int(row["id"])),
    )
    highlighted = select_highlighted_fixtures(rows)
    highlighted_ids = {row["id"] for row in highlighted}
    for row in rows:
        row["is_highlighted"] = row["id"] in highlighted_ids
        row["highlight_priority"] = _competition_priority(row)
    competition_keys = {
        (str(row["league_id"]), str(row["season_id"])) for row in rows
    }
    return {
        "fixtures": rows,
        "highlighted_fixtures": highlighted,
        "highlight_limit": MAX_HIGHLIGHTED_FIXTURES,
        "highlighted_count": len(highlighted),
        "major_competition_fixture_count": sum(
            1 for row in rows if row["highlight_priority"] < 3
        ),
        "fixtures_found": len(rows),
        "competitions_found": len(competition_keys),
        "window_start_utc": current.isoformat(),
        "window_end_utc": (current + timedelta(days=window_days)).isoformat(),
        "window_days": window_days,
        "daily_target": DAILY_FIXTURE_TARGET,
        "target_met": len(rows) >= DAILY_FIXTURE_TARGET,
        "target_shortfall": max(0, DAILY_FIXTURE_TARGET - len(rows)),
        "excluded": excluded,
    }


def collect_upcoming_fixtures(
    *,
    client: Any | None = None,
    now: datetime | None = None,
    window_days: int = WINDOW_DAYS,
    database_url: str | None = None,
) -> dict[str, Any]:
    """Fetch the rolling seven-day fixture window and optionally persist it."""
    if isinstance(window_days, bool) or not isinstance(window_days, int) or not 1 <= window_days <= 7:
        raise ValueError("window_days must be an integer from 1 through 7.")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    end = current + timedelta(days=window_days)
    owns_client = client is None
    api = client or SportmonksClient()
    try:
        raw = api.fixtures_between_all_pages(
            current.date().isoformat(),
            end.date().isoformat(),
            include=FIXTURE_INCLUDE,
        )
    finally:
        if owns_client:
            close = getattr(api, "close", None)
            if callable(close):
                close()

    result = normalize_upcoming_fixtures(raw, now=current, window_days=window_days)
    result["provider"] = "sportmonks"
    result["provider_request"] = {
        "start_date": current.date().isoformat(),
        "end_date": end.date().isoformat(),
        "include": FIXTURE_INCLUDE,
    }
    result["persisted"] = False
    result["fixtures_upserted"] = 0

    if database_url:
        from football_repository import upsert_discovered_fixtures

        saved = upsert_discovered_fixtures(database_url, result["fixtures"])
        result["persisted"] = True
        result["fixtures_upserted"] = saved.get("fixtures_upserted", 0)
        result["competitions_upserted"] = saved.get("competitions_upserted", 0)
        result["teams_upserted"] = saved.get("teams_upserted", 0)
    return result


def main() -> int:
    database_url = os.getenv("PROVIDER_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("PROVIDER_DATABASE_URL is not configured.")
    result = collect_upcoming_fixtures(database_url=database_url)
    safe_report = {key: value for key, value in result.items() if key != "fixtures"}
    print(json.dumps(safe_report, default=str, sort_keys=True))
    if not result["target_met"]:
        print(
            f"WARNING: only {result['fixtures_found']} valid upcoming fixtures were found; "
            f"{result['target_shortfall']} more are needed to reach the daily target of "
            f"{DAILY_FIXTURE_TARGET}. No fixtures were fabricated and the seven-day window "
            "was not extended.",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
