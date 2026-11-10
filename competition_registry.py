"""Competition and season discovery registry with conservative identity rules.

Provider IDs are namespaced and never inferred to be equivalent across vendors.
Discovery/registration is not proof of prediction readiness.
"""
from __future__ import annotations

import re
from typing import Any, Mapping


def _positive_id(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text or not re.fullmatch(r"[A-Za-z0-9_.:-]+", text):
        return None
    return text


def _name(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _country(row: Mapping[str, Any]) -> str:
    value = row.get("country")
    if isinstance(value, Mapping):
        return _name(value.get("name"))
    return _name(value)


def build_discovered_competition_registry(
    leagues: list[Mapping[str, Any]] | None,
    seasons: list[Mapping[str, Any]] | None,
    *,
    provider: str,
) -> list[dict[str, Any]]:
    """Pair only exact provider league_id references; reject ambiguous identities."""
    provider_name = str(provider or "").strip().casefold()
    if not provider_name:
        raise ValueError("provider is required.")
    league_index: dict[str, Mapping[str, Any]] = {}
    ambiguous_ids: set[str] = set()
    for league in leagues or []:
        if not isinstance(league, Mapping):
            continue
        league_id = _positive_id(league.get("id"))
        name = _name(league.get("name"))
        if not league_id or not name:
            continue
        if league_id in league_index:
            previous = league_index[league_id]
            if (_name(previous.get("name")), _country(previous)) != (name, _country(league)):
                ambiguous_ids.add(league_id)
                league_index.pop(league_id, None)
            continue
        league_index[league_id] = league

    records: list[dict[str, Any]] = []
    seen_seasons: set[tuple[str, str]] = set()
    for season in seasons or []:
        if not isinstance(season, Mapping):
            continue
        league_id = _positive_id(season.get("league_id"))
        season_id = _positive_id(season.get("id"))
        if not league_id or not season_id or league_id in ambiguous_ids:
            continue
        league = league_index.get(league_id)
        if not league:
            continue
        if _positive_id(season.get("league_id")) != _positive_id(league.get("id")):
            continue
        key = (league_id, season_id)
        if key in seen_seasons:
            continue
        seen_seasons.add(key)
        league_name = _name(league.get("name"))
        country = _country(league)
        season_name = _name(season.get("name") or season.get("starting_at"))
        records.append({
            "provider": provider_name,
            "provider_competition_id": league_id,
            "provider_season_id": season_id,
            "competition_name": league_name,
            "country": country,
            "season_name": season_name,
            "season_start": season.get("starting_at"),
            "season_end": season.get("ending_at"),
            "is_current": bool(season.get("is_current")) if season.get("is_current") is not None else None,
            "identity_key": "|".join((provider_name, league_id, season_id)),
            "discovery_status": "discovered",
            "registration_status": "registered",
            "crosswalk_status": "unmapped",
            "canonical_competition_id": None,
            "prediction_ready": False,
            "readiness_reason": "Discovery confirms only this provider's competition-season relationship; independent identity and data-quality validation are still required.",
            "raw_competition": dict(league),
            "raw_season": dict(season),
        })
    return sorted(records, key=lambda row: (
        row["country"].casefold(), row["competition_name"].casefold(),
        row["season_name"].casefold(), row["provider_competition_id"],
    ))


def validate_explicit_competition_crosswalk(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> dict[str, Any]:
    """Return a candidate comparison; never auto-link on a name-only match."""
    left_name, right_name = _name(left.get("competition_name")), _name(right.get("competition_name"))
    left_country, right_country = _name(left.get("country")), _name(right.get("country"))
    same_name = bool(left_name) and left_name.casefold() == right_name.casefold()
    same_country = bool(left_country) and left_country.casefold() == right_country.casefold()
    same_season = (
        _name(left.get("season_name")).casefold()
        == _name(right.get("season_name")).casefold()
        and bool(_name(left.get("season_name")))
    )
    return {
        "candidate": bool(same_name and same_country and same_season),
        "verified": False,
        "status": "candidate_requires_explicit_verification" if same_name and same_country and same_season else "identity_mismatch",
        "reason": (
            "Name, country and season labels match, but provider IDs remain namespaced; explicit crosswalk verification is required."
            if same_name and same_country and same_season
            else "Competition name, country or season label differs; no cross-provider link is proposed."
        ),
        "left_provider": left.get("provider"),
        "left_competition_id": left.get("provider_competition_id"),
        "left_season_id": left.get("provider_season_id"),
        "right_provider": right.get("provider"),
        "right_competition_id": right.get("provider_competition_id"),
        "right_season_id": right.get("provider_season_id"),
    }
