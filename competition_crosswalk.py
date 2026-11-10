"""Verified, fail-closed competition identity mapping across providers.

Supports Sportmonks (current-season path) and API-Football (historical path).
A LiveScoreFootball mapping requires exact identity, season, active coverage,
and fresh per-competition sync metadata. It does not enable fallback.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any, Iterable, Mapping

from provider_health import assess_freshness


def normalize_competition_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_country(value: Any) -> str:
    if isinstance(value, Mapping):
        value = value.get("name") or value.get("displayName") or ""
    name = normalize_competition_name(value)
    aliases = {
        "england": "england", "united kingdom": "england",
        "spain": "spain", "espana": "spain",
        "germany": "germany", "deutschland": "germany",
        "italy": "italy", "italia": "italy",
        "france": "france", "netherlands": "netherlands",
        "holland": "netherlands", "scotland": "scotland",
        "portugal": "portugal", "belgium": "belgium",
        "austria": "austria", "turkey": "turkey",
        "turkiye": "turkey", "united states": "united states",
        "usa": "united states", "mexico": "mexico",
        "argentina": "argentina", "brazil": "brazil",
        "saudi arabia": "saudi arabia", "japan": "japan",
    }
    return aliases.get(name, name)


def _source_parts(row: Mapping[str, Any], source_provider: str) -> tuple[str, str, str]:
    if source_provider == "sportmonks":
        country = row.get("country") if isinstance(row.get("country"), Mapping) else {}
        return (
            str(row.get("name") or ""),
            str(country.get("name") or row.get("country_name") or ""),
            str(row.get("id") or ""),
        )
    league = row.get("league") if isinstance(row.get("league"), Mapping) else row
    country = row.get("country") if isinstance(row.get("country"), Mapping) else {}
    return (
        str(league.get("name") or ""),
        str(country.get("name") or row.get("country_name") or ""),
        str(league.get("id") or ""),
    )


def _live_parts(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("name") or row.get("displayName") or ""),
        normalize_country(row.get("country") or row.get("countryName") or ""),
        str(row.get("slug") or ""),
    )


def build_competition_crosswalk(
    source_competitions: Iterable[Mapping[str, Any]],
    livescore_competitions: Iterable[Mapping[str, Any]],
    *,
    requested_season: int | None = None,
    source_provider: str = "api_football",
    now: datetime | None = None,
    max_age_seconds: int = 24 * 60 * 60,
) -> list[dict[str, Any]]:
    """Match exact competition/country identities and require fresh coverage."""
    if source_provider not in {"api_football", "sportmonks"}:
        raise ValueError("source_provider must be api_football or sportmonks")
    live_rows = [row for row in livescore_competitions if isinstance(row, Mapping)]
    output: list[dict[str, Any]] = []
    for source_row in source_competitions:
        if not isinstance(source_row, Mapping):
            continue
        source_name, source_country, source_id = _source_parts(source_row, source_provider)
        if not source_name or not source_country or not source_id:
            continue
        key = (normalize_competition_name(source_name), normalize_country(source_country))
        candidates = []
        for live_row in live_rows:
            live_name, live_country, slug = _live_parts(live_row)
            if slug and live_name and live_country and (
                normalize_competition_name(live_name), normalize_country(live_country)
            ) == key:
                candidates.append(live_row)
        base = {
            "source_provider": source_provider,
            "source_competition_id": source_id,
            "api_football_id": source_id if source_provider == "api_football" else None,
            "sportmonks_id": source_id if source_provider == "sportmonks" else None,
            "name": source_name,
            "country": source_country,
        }
        if len(candidates) != 1:
            output.append({
                **base, "livescore_slug": None, "verified": False,
                "reason": "no exact provider-catalogue match" if not candidates
                          else "ambiguous duplicate LiveScoreFootball catalogue match",
            })
            continue
        live = candidates[0]
        season_info = live.get("season") if isinstance(live.get("season"), Mapping) else {}
        live_season = season_info.get("year")
        coverage = live.get("coverage") if isinstance(live.get("coverage"), Mapping) else {}
        active = live.get("active") is True
        has_data = coverage.get("hasData") is True
        season_ok = requested_season is None or (
            live_season is not None and str(live_season) == str(requested_season)
        )
        competition_last_synced_at = live.get("lastSyncedAt") or coverage.get("lastSyncedAt")
        freshness = assess_freshness(
            competition_last_synced_at, "fixtures", now=now,
            max_age_seconds=max_age_seconds,
        )
        verified = active and has_data and season_ok and freshness["fresh"]
        if not active:
            reason = "LiveScoreFootball competition is not active"
        elif not has_data:
            reason = "LiveScoreFootball competition currently reports no stored data"
        elif not season_ok:
            reason = "LiveScoreFootball season is missing or does not match requested season"
        elif not freshness["fresh"]:
            reason = "Per-competition sync timestamp is missing, invalid, or stale"
        else:
            reason = "exact name/country match; active, data-backed, season-verified and fresh"
        output.append({
            **base,
            "livescore_slug": live.get("slug") if verified else None,
            "livescore_name": live.get("name"),
            "livescore_season": live_season,
            "coverage": dict(coverage),
            "competition_last_synced_at": competition_last_synced_at,
            "coverage_freshness": freshness,
            "verified": verified,
            "reason": reason,
        })
    return output


def verified_livescore_slug(
    crosswalk: Iterable[Mapping[str, Any]],
    source_competition_id: int | str,
    *,
    source_provider: str | None = None,
) -> str | None:
    target = str(source_competition_id)
    matches = [
        row for row in crosswalk
        if str(row.get("source_competition_id", row.get("api_football_id"))) == target
        and row.get("verified") is True
        and (source_provider is None or row.get("source_provider") == source_provider)
    ]
    return str(matches[0]["livescore_slug"]) if len(matches) == 1 and matches[0].get("livescore_slug") else None
