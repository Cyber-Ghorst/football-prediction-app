"""Provider-neutral source selection and field-level reconciliation.

This module deliberately contains no network clients. Provider adapters normalize
their payloads into observations, then this module selects validated values
without averaging conflicting source data.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable


# LiveScoreFootball is deliberately absent from the default order. Its public
# catalogue is only eligible for a competition after exact name/country,
# active-state, stored-data and season checks have passed. Sportmonks is the
# intended current-season primary source once that exact league is enabled in
# the account and match-level coverage has been validated. API-Football remains
# a historical/secondary source within the seasons allowed by its subscription.
PROVIDER_ORDER = {
    "fixtures": ("sportmonks", "highlightly", "api_ninjas", "api_football"),
    "results": ("sportmonks", "highlightly", "api_ninjas", "api_football"),
    "standings": ("sportmonks", "highlightly", "api_ninjas", "api_football"),
    "statistics": ("sportmonks", "highlightly", "api_football"),
    "injuries": ("sportmonks", "highlightly", "api_football"),
    "lineups": ("sportmonks", "highlightly", "api_football"),
    "players": ("sportmonks", "highlightly", "api_football", "api_ninjas"),
    "squads": ("sportmonks", "highlightly", "api_ninjas", "api_football"),
}


@dataclass(frozen=True)
class Observation:
    provider: str
    value: Any
    fetched_at: datetime
    source_id: str | None = None
    updated_at: datetime | None = None
    valid: bool = True
    validation_message: str | None = None


@dataclass(frozen=True)
class ResolvedField:
    value: Any
    provider: str | None
    source_id: str | None
    status: str
    corroborating_providers: tuple[str, ...]
    conflicting_providers: tuple[str, ...]
    fetched_at: datetime | None
    message: str


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _equivalent(left: Any, right: Any, *, domain: str) -> bool:
    """Compare values conservatively, normalizing ISO kickoffs for fixtures."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return float(left) == float(right)
    if domain == "fixtures" and isinstance(left, str) and isinstance(right, str):
        def parse_kickoff(value: str) -> datetime | None:
            try:
                parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            except ValueError:
                return None
            return _utc(parsed)
        left_time = parse_kickoff(left)
        right_time = parse_kickoff(right)
        if left_time is not None and right_time is not None:
            return left_time == right_time
    return left == right


def resolve_field(
    domain: str,
    observations: Iterable[Observation],
    *,
    now: datetime | None = None,
    max_age_seconds: int | None = None,
    livescore_verified: bool = False,
) -> ResolvedField:
    """Choose a source by domain priority and expose agreement/conflicts.

    LiveScoreFootball is considered only when the caller has independently
    verified coverage for the exact competition and season. Invalid, null and
    stale observations are excluded. Conflicts are never averaged.
    """
    base_priority = PROVIDER_ORDER.get(domain)
    if base_priority is None:
        raise ValueError(f"Unknown data domain: {domain}")
    priority = (
        ("livescore_football", *base_priority)
        if livescore_verified and domain in {"fixtures", "results", "standings"}
        else base_priority
    )

    current = _utc(now or datetime.now(timezone.utc))
    eligible: list[Observation] = []
    for item in observations:
        if item.provider not in priority or not item.valid or item.value is None:
            continue
        fetched = _utc(item.fetched_at)
        if max_age_seconds is not None:
            age = (current - fetched).total_seconds()
            if age < 0 or age > max_age_seconds:
                continue
        eligible.append(item)

    if not eligible:
        return ResolvedField(
            value=None, provider=None, source_id=None, status="unknown",
            corroborating_providers=(), conflicting_providers=(),
            fetched_at=None, message="No valid, fresh observation is available.",
        )

    rank = {provider: index for index, provider in enumerate(priority)}
    eligible.sort(
        key=lambda item: (
            rank[item.provider],
            -_utc(item.updated_at or item.fetched_at).timestamp(),
            -_utc(item.fetched_at).timestamp(),
        )
    )
    selected = eligible[0]
    corroborating = tuple(sorted({
        item.provider for item in eligible
        if item.provider != selected.provider and _equivalent(item.value, selected.value, domain=domain)
    }))
    conflicting = tuple(sorted({
        item.provider for item in eligible
        if item.provider != selected.provider and not _equivalent(item.value, selected.value, domain=domain)
    }))

    if conflicting:
        status = "conflict"
        message = (
            f"Selected {selected.provider} by configured {domain} priority; "
            "other valid sources disagree. No values were averaged."
        )
    elif corroborating:
        status = "corroborated"
        message = f"{selected.provider} is corroborated by independent source data."
    else:
        status = "single_source"
        message = f"Only {selected.provider} supplied an eligible value."

    return ResolvedField(
        value=selected.value,
        provider=selected.provider,
        source_id=selected.source_id,
        status=status,
        corroborating_providers=corroborating,
        conflicting_providers=conflicting,
        fetched_at=selected.fetched_at,
        message=message,
    )


def normalize_team_name(name: str) -> str:
    """Conservative display-name normalization for candidate matching only."""
    import re
    normalized = re.sub(r"[^a-z0-9]+", " ", str(name).casefold()).strip()
    return re.sub(r"\s+", " ", normalized)


def match_identity_key(
    competition: str,
    season: int | str,
    kickoff_iso: str,
    home_team: str,
    away_team: str,
) -> tuple[str, str, str, str, str]:
    """Build a candidate identity key; callers must still verify kickoff/team IDs."""
    kickoff = datetime.fromisoformat(kickoff_iso.replace("Z", "+00:00"))
    kickoff_utc = _utc(kickoff).replace(second=0, microsecond=0).isoformat()
    return (
        str(competition).casefold().strip(),
        str(season),
        kickoff_utc,
        normalize_team_name(home_team),
        normalize_team_name(away_team),
    )
