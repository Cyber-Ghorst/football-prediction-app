"""Verified, fail-closed competition identity mapping across providers.

Crosswalks are built from live provider catalogues, not guessed numeric IDs or
fuzzy competition-name similarity. A LiveScoreFootball mapping is usable only
when the league is active, has data, and exposes a matching season.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable, Mapping


def normalize_competition_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_country(value: Any) -> str:
    name = normalize_competition_name(value)
    aliases = {
        "england": "england", "united kingdom": "england",
        "spain": "spain", "españa": "spain",
        "germany": "germany", "deutschland": "germany",
        "italy": "italy", "italia": "italy",
        "france": "france", "netherlands": "netherlands",
        "holland": "netherlands", "scotland": "scotland",
        "portugal": "portugal", "belgium": "belgium",
        "austria": "austria", "turkey": "turkey",
        "türkiye": "turkey", "united states": "united states",
        "usa": "united states", "mexico": "mexico",
        "argentina": "argentina", "brazil": "brazil",
        "saudi arabia": "saudi arabia", "japan": "japan",
    }
    return aliases.get(name, name)


def _api_parts(row: Mapping[str, Any]) -> tuple[str, str, str]:
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
        str(row.get("country") or ""),
        str(row.get("slug") or ""),
    )


def build_competition_crosswalk(
    api_football_competitions: Iterable[Mapping[str, Any]],
    livescore_competitions: Iterable[Mapping[str, Any]],
    *,
    requested_season: int | None = None,
) -> list[dict[str, Any]]:
    """Match API-Football catalogue entries to LiveScore slugs conservatively."""
    live_rows = [row for row in livescore_competitions if isinstance(row, Mapping)]
    output: list[dict[str, Any]] = []
    for api_row in api_football_competitions:
        if not isinstance(api_row, Mapping):
            continue
        api_name, api_country, api_id = _api_parts(api_row)
        if not api_name or not api_country or not api_id:
            continue
        key = (normalize_competition_name(api_name), normalize_country(api_country))
        candidates = []
        for live_row in live_rows:
            live_name, live_country, slug = _live_parts(live_row)
            if not slug or not live_name or not live_country:
                continue
            if (normalize_competition_name(live_name), normalize_country(live_country)) == key:
                candidates.append(live_row)
        # Ambiguous duplicate catalogue entries are not mapped.
        if len(candidates) != 1:
            output.append({
                "api_football_id": api_id, "name": api_name,
                "country": api_country, "livescore_slug": None,
                "verified": False,
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
        verified = active and has_data and season_ok
        if not active:
            reason = "LiveScoreFootball competition is not active"
        elif not has_data:
            reason = "LiveScoreFootball competition currently reports no stored data"
        elif not season_ok:
            reason = "LiveScoreFootball season is missing or does not match requested season"
        else:
            reason = "exact name/country match; active, data-backed and season-verified"
        output.append({
            "api_football_id": api_id,
            "name": api_name,
            "country": api_country,
            "livescore_slug": live.get("slug") if verified else None,
            "livescore_name": live.get("name"),
            "livescore_season": live_season,
            "coverage": dict(coverage),
            "verified": verified,
            "reason": reason,
        })
    return output


def verified_livescore_slug(crosswalk: Iterable[Mapping[str, Any]], api_football_id: int | str) -> str | None:
    target = str(api_football_id)
    matches = [row for row in crosswalk if str(row.get("api_football_id")) == target and row.get("verified") is True]
    return str(matches[0]["livescore_slug"]) if len(matches) == 1 and matches[0].get("livescore_slug") else None
