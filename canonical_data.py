"""Provider-neutral match normalization and conservative cross-source matching.

Source IDs remain namespaced. A cross-provider match is only a candidate when
competition, season, both normalized team identities and kickoff all agree.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from provider_core import normalize_team_name


class MatchNormalizationError(ValueError):
    """Raised when a provider record lacks essential match identity fields."""


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str) and value.strip():
        result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        raise MatchNormalizationError("Match kickoff is missing.")
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _season_year(value: Any) -> int | None:
    if isinstance(value, Mapping):
        value = value.get("year") or value.get("start")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _status_from_livescore(event: Mapping[str, Any]) -> str:
    status = event.get("status") or {}
    kind = status.get("type") or {}
    state = str(kind.get("state") or "").casefold()
    completed = bool(kind.get("completed"))
    if completed or state in {"post", "finished", "final"}:
        return "finished"
    if state in {"in", "live"}:
        return "live"
    if state in {"pre", "scheduled"}:
        return "scheduled"
    return "unknown"


def _status_from_api_football(fixture: Mapping[str, Any]) -> str:
    short = str(((fixture.get("status") or {}).get("short")) or "").upper()
    if short in {"FT", "AET", "PEN"}:
        return "finished"
    if short in {"1H", "HT", "2H", "ET", "BT", "P", "LIVE"}:
        return "live"
    if short in {"NS", "TBD"}:
        return "scheduled"
    return "unknown"


def canonicalize_livescore_event(
    event: Mapping[str, Any], *, competition_key: str, season: int | str
) -> dict[str, Any]:
    competitions = event.get("competitions") or []
    competition = competitions[0] if competitions else {}
    competitors = competition.get("competitors") or []
    by_side = {str(row.get("homeAway", "")).casefold(): row for row in competitors}
    home_row, away_row = by_side.get("home"), by_side.get("away")
    if not home_row or not away_row:
        raise MatchNormalizationError("LiveScoreFootball event has no home/away competitors.")
    home = home_row.get("team") or {}
    away = away_row.get("team") or {}
    home_name, away_name = home.get("name") or home.get("displayName"), away.get("name") or away.get("displayName")
    if not home_name or not away_name:
        raise MatchNormalizationError("LiveScoreFootball event is missing team names.")
    kickoff = _parse_datetime(competition.get("date") or event.get("date"))
    return {
        "competition_key": str(competition_key).casefold().strip(),
        "season": _season_year(season),
        "kickoff_utc": kickoff.isoformat(),
        "home": {"name": str(home_name), "normalized_name": normalize_team_name(home_name),
                 "source_ids": {"livescore_football": str(home_row.get("id") or home.get("id") or "")}},
        "away": {"name": str(away_name), "normalized_name": normalize_team_name(away_name),
                 "source_ids": {"livescore_football": str(away_row.get("id") or away.get("id") or "")}},
        "status": _status_from_livescore(event),
        "home_score": _int_or_none(home_row.get("score")),
        "away_score": _int_or_none(away_row.get("score")),
        "source_ids": {"livescore_football": str(event.get("id") or "")},
        "source": "livescore_football",
        "raw_source_updated_at": event.get("updatedAt") or event.get("updated_at")
        or competition.get("updatedAt") or competition.get("updated_at"),
    }


def canonicalize_api_football_fixture(
    fixture: Mapping[str, Any], *, competition_key: str, season: int | str
) -> dict[str, Any]:
    info = fixture.get("fixture") or {}
    teams = fixture.get("teams") or {}
    goals = fixture.get("goals") or {}
    home, away = teams.get("home") or {}, teams.get("away") or {}
    if not home.get("name") or not away.get("name"):
        raise MatchNormalizationError("API-Football fixture is missing home/away team names.")
    kickoff = _parse_datetime(info.get("date"))
    return {
        "competition_key": str(competition_key).casefold().strip(),
        "season": _season_year(season),
        "kickoff_utc": kickoff.isoformat(),
        "home": {"name": str(home["name"]), "normalized_name": normalize_team_name(home["name"]),
                 "source_ids": {"api_football": str(home.get("id") or "")}},
        "away": {"name": str(away["name"]), "normalized_name": normalize_team_name(away["name"]),
                 "source_ids": {"api_football": str(away.get("id") or "")}},
        "status": _status_from_api_football(info),
        "home_score": _int_or_none(goals.get("home")),
        "away_score": _int_or_none(goals.get("away")),
        "source_ids": {"api_football": str(info.get("id") or "")},
        "source": "api_football",
        "raw_source_updated_at": fixture.get("updated_at") or info.get("updated_at"),
    }



def _status_from_api_ninjas(match: Mapping[str, Any]) -> str:
    status = str(match.get("status") or "").casefold().replace(" ", "_")
    if status == "final":
        return "finished"
    if status == "in_progress":
        return "live"
    if status == "scheduled":
        return "scheduled"
    return "unknown"


def _score_pair(value: Any) -> tuple[int | None, int | None]:
    """Parse a provider's displayed home-away score without guessing."""
    import re
    match = re.fullmatch(r"\s*(\d+)\s*[-:]\s*(\d+)\s*", value) if isinstance(value, str) else None
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def canonicalize_api_ninjas_match(
    match: Mapping[str, Any], *, competition_key: str, season: int | str | None = None
) -> dict[str, Any]:
    """Normalize API Ninjas match records into the canonical schema."""
    home, away = match.get("home_team") or {}, match.get("away_team") or {}
    home_name, away_name = home.get("name"), away.get("name")
    if not home_name or not away_name:
        raise MatchNormalizationError("API Ninjas match is missing home/away team names.")
    kickoff = _parse_datetime(match.get("start_time"))
    season_value = _season_year(season if season is not None else match.get("season"))
    return {
        "competition_key": str(competition_key).casefold().strip(),
        "season": season_value,
        "kickoff_utc": kickoff.isoformat(),
        "home": {"name": str(home_name), "normalized_name": normalize_team_name(home_name),
                 "source_ids": {"api_ninjas": str(home.get("team_id") or "")}},
        "away": {"name": str(away_name), "normalized_name": normalize_team_name(away_name),
                 "source_ids": {"api_ninjas": str(away.get("team_id") or "")}},
        "status": _status_from_api_ninjas(match),
        "home_score": _int_or_none(match.get("home_score")),
        "away_score": _int_or_none(match.get("away_score")),
        "source_ids": {"api_ninjas": str(match.get("game_id") or "")},
        "source": "api_ninjas",
        "raw_source_updated_at": match.get("updated_at"),
    }


def _status_from_highlightly(match: Mapping[str, Any]) -> str:
    description = str(((match.get("state") or {}).get("description")) or "").casefold()
    if description in {"finished", "finished after penalties", "finished after extra time", "awarded"}:
        return "finished"
    if description in {"first half", "second half", "half time", "extra time",
                       "break time", "penalties", "in progress"}:
        return "live"
    if description == "not started":
        return "scheduled"
    return "unknown"


def canonicalize_highlightly_match(
    match: Mapping[str, Any], *, competition_key: str, season: int | str | None = None
) -> dict[str, Any]:
    """Normalize Highlightly match-list/detail records."""
    home, away = match.get("homeTeam") or {}, match.get("awayTeam") or {}
    league = match.get("league") or {}
    home_name, away_name = home.get("name"), away.get("name")
    if not home_name or not away_name:
        raise MatchNormalizationError("Highlightly match is missing home/away team names.")
    kickoff = _parse_datetime(match.get("date"))
    season_value = _season_year(season if season is not None else league.get("season"))
    score = ((match.get("state") or {}).get("score") or {}).get("current")
    home_score, away_score = _score_pair(score)
    return {
        "competition_key": str(competition_key).casefold().strip(),
        "season": season_value,
        "kickoff_utc": kickoff.isoformat(),
        "home": {"name": str(home_name), "normalized_name": normalize_team_name(home_name),
                 "source_ids": {"highlightly": str(home.get("id") or "")}},
        "away": {"name": str(away_name), "normalized_name": normalize_team_name(away_name),
                 "source_ids": {"highlightly": str(away.get("id") or "")}},
        "status": _status_from_highlightly(match),
        "home_score": home_score,
        "away_score": away_score,
        "source_ids": {"highlightly": str(match.get("id") or "")},
        "source": "highlightly",
        "raw_source_updated_at": match.get("updatedAt") or match.get("updated_at"),
    }

def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def match_identity(
    left: Mapping[str, Any], right: Mapping[str, Any], *,
    team_aliases: Mapping[str, str] | None = None,
    kickoff_tolerance_seconds: int = 300,
) -> bool:
    """Return True only for an unambiguous identity candidate; IDs are not compared."""
    if not left.get("competition_key") or left.get("competition_key") != right.get("competition_key"):
        return False
    if left.get("season") is None or left.get("season") != right.get("season"):
        return False
    aliases = {normalize_team_name(k): normalize_team_name(v)
               for k, v in (team_aliases or {}).items()}

    def canonical_team(team: Mapping[str, Any]) -> str:
        name = team.get("normalized_name") or normalize_team_name(team.get("name", ""))
        return aliases.get(name, name)

    if not left.get("home") or not left.get("away") or not right.get("home") or not right.get("away"):
        return False
    if canonical_team(left["home"]) != canonical_team(right["home"]):
        return False
    if canonical_team(left["away"]) != canonical_team(right["away"]):
        return False
    try:
        delta = abs((_parse_datetime(left["kickoff_utc"]) - _parse_datetime(right["kickoff_utc"])).total_seconds())
    except (KeyError, MatchNormalizationError, TypeError, ValueError):
        return False
    return delta <= max(0, int(kickoff_tolerance_seconds))


def merge_source_ids(*matches: Mapping[str, Any]) -> dict[str, str]:
    """Combine only source-namespaced IDs; never flatten IDs into one shared key."""
    merged: dict[str, str] = {}
    for match in matches:
        for provider, source_id in (match.get("source_ids") or {}).items():
            if source_id:
                merged[str(provider)] = str(source_id)
        for side in ("home", "away"):
            for provider, source_id in (match.get(side) or {}).get("source_ids", {}).items():
                if source_id:
                    merged[f"{side}.{provider}"] = str(source_id)
    return merged


def reconcile_match_pair(
    left: Mapping[str, Any], right: Mapping[str, Any], *,
    fetched_at: Mapping[str, datetime] | None = None,
    now: datetime | None = None,
    max_age_seconds: int | None = 86400,
    team_aliases: Mapping[str, str] | None = None,
    livescore_verified: bool = False,
) -> dict[str, Any] | None:
    """Reconcile two normalized records only after a strict identity match.

    Field values are selected by provider priority through provider_core.
    Conflicts are retained in diagnostics and never averaged. If the records
    cannot be safely matched, return None rather than risk a false join.
    """
    from provider_core import Observation, resolve_field

    if not match_identity(left, right, team_aliases=team_aliases):
        return None
    sources = (left, right)
    fetched_at = fetched_at or {}
    primary_provider = str(left.get("source") or "")
    result = dict(left)
    result["source_ids"] = dict(left.get("source_ids") or {})
    result["home"] = dict(left["home"])
    result["away"] = dict(left["away"])
    result["home"]["source_ids"] = dict(left["home"].get("source_ids") or {})
    result["away"]["source_ids"] = dict(left["away"].get("source_ids") or {})
    result["reconciliation"] = {}

    for record in sources[1:]:
        result["source_ids"].update(record.get("source_ids") or {})
        for side in ("home", "away"):
            result[side]["source_ids"].update(record.get(side, {}).get("source_ids") or {})

    for field, domain in (
        ("status", "results"), ("home_score", "results"),
        ("away_score", "results"), ("kickoff_utc", "fixtures"),
    ):
        observations = []
        for record in sources:
            provider = str(record.get("source") or "")
            value = record.get(field)
            if not provider or value is None:
                continue
            observations.append(Observation(
                provider=provider,
                value=value,
                fetched_at=fetched_at.get(provider) or now or datetime.now(timezone.utc),
                source_id=(record.get("source_ids") or {}).get(provider),
            ))
        resolved = resolve_field(
            domain, observations, now=now, max_age_seconds=max_age_seconds,
            livescore_verified=livescore_verified,
        )
        result[field] = resolved.value
        result["reconciliation"][field] = {
            "provider": resolved.provider,
            "status": resolved.status,
            "corroborating_providers": list(resolved.corroborating_providers),
            "conflicting_providers": list(resolved.conflicting_providers),
            "message": resolved.message,
        }
    result["source"] = primary_provider
    return result
