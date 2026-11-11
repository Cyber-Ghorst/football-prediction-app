"""Collect and archive free future-fixture observations without canonical writes."""
from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import quote
import time

from free_fixture_adapters import (
    BzzoiroAdapter,
    OpenFootballAdapter,
    OpenLigaDBAdapter,
    OpenMatchdayAdapter,
    TheSportsDBAdapter,
    normalize_thesportsdb_events,
)
from free_fixture_observation_store import archive_future_fixture_observations


def _close_owned(client: Any, owned: bool) -> None:
    if owned:
        close = getattr(client, "close", None)
        if callable(close):
            close()


def _archive(
    database_url: str,
    provider: str,
    request_params: Mapping[str, Any],
    observations: list[dict[str, Any]],
    errors: list[dict[str, str]],
    successful_scopes: int,
) -> dict[str, Any]:
    if successful_scopes == 0:
        return {
            "provider": provider, "archived": False,
            "observation_count": len(observations),
            "eligible_for_review_count": sum(
                row.get("eligible_for_review") is True for row in observations
            ),
            "errors": errors,
        }
    stored = archive_future_fixture_observations(
        database_url,
        provider=provider,
        request_params=request_params,
        observations=observations,
    )
    return {
        **stored, "archived": True,
        "observation_count": len(observations),
        "eligible_for_review_count": sum(
            row.get("eligible_for_review") is True for row in observations
        ),
        "successful_scopes": successful_scopes,
        "errors": errors,
    }


def collect_openligadb_observations(
    database_url: str,
    scopes: list[Mapping[str, Any]],
    *,
    client: OpenLigaDBAdapter | None = None,
    request_delay_seconds: float = 0.0,
) -> dict[str, Any]:
    """Collect configured OpenLigaDB league-shortcut/season pairs."""
    if not scopes:
        raise ValueError("At least one OpenLigaDB scope is required.")
    owned = client is None
    api = client or OpenLigaDBAdapter()
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    successful = 0
    try:
        for scope in scopes:
            shortcut = str(scope.get("league_shortcut") or "").strip()
            season = scope.get("season")
            try:
                if not shortcut or isinstance(season, bool) or not str(season).isdigit():
                    raise ValueError("Scope requires league_shortcut and numeric season.")
                rows.extend(api.matches(shortcut, int(season)))
                successful += 1
            except Exception as exc:
                errors.append({"scope": shortcut or "unknown", "error": str(exc)[:300]})
            if request_delay_seconds > 0:
                time.sleep(min(float(request_delay_seconds), 5.0))
    finally:
        _close_owned(api, owned)
    return _archive(
        database_url, "openligadb",
        {"scopes": [dict(scope) for scope in scopes]},
        rows, errors, successful,
    )


def collect_openfootball_observations(
    database_url: str,
    datasets: list[Mapping[str, Any]],
    *,
    client: OpenFootballAdapter | None = None,
) -> dict[str, Any]:
    """Collect configured football.json season files."""
    if not datasets:
        raise ValueError("At least one OpenFootball dataset is required.")
    owned = client is None
    api = client or OpenFootballAdapter()
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    successful = 0
    try:
        for dataset in datasets:
            filename = str(dataset.get("season_file") or "").strip()
            competition = str(dataset.get("competition") or "").strip()
            try:
                if not filename or not competition:
                    raise ValueError("Dataset requires season_file and competition.")
                rows.extend(api.season(filename, competition))
                successful += 1
            except Exception as exc:
                errors.append({"scope": filename or "unknown", "error": str(exc)[:300]})
    finally:
        _close_owned(api, owned)
    return _archive(
        database_url, "openfootball",
        {"datasets": [dict(dataset) for dataset in datasets]},
        rows, errors, successful,
    )


def collect_openmatchday_observations(
    database_url: str,
    datasets: list[Mapping[str, Any]],
    *,
    client: OpenMatchdayAdapter | None = None,
) -> dict[str, Any]:
    """Collect configured Open Matchday CSV files without timezone inference."""
    if not datasets:
        raise ValueError("At least one Open Matchday dataset is required.")
    owned = client is None
    api = client or OpenMatchdayAdapter()
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    successful = 0
    try:
        for dataset in datasets:
            url = str(dataset.get("url") or "").strip()
            competition = str(dataset.get("competition") or "").strip()
            season = str(dataset.get("season") or "").strip()
            try:
                if not url or not competition or not season:
                    raise ValueError("Dataset requires url, competition and season.")
                rows.extend(api.season_csv(url, competition=competition, season=season))
                successful += 1
            except Exception as exc:
                errors.append({"scope": url or "unknown", "error": str(exc)[:300]})
    finally:
        _close_owned(api, owned)
    return _archive(
        database_url, "open_matchday",
        {"datasets": [dict(dataset) for dataset in datasets]},
        rows, errors, successful,
    )


def collect_thesportsdb_observations(
    database_url: str,
    *,
    country: str,
    max_leagues: int = 10,
    terms_acknowledged: bool = False,
    client: TheSportsDBAdapter | None = None,
    request_delay_seconds: float = 2.2,
) -> dict[str, Any]:
    """Stage the next event from selected leagues using TheSportsDB's free v1 API."""
    if not terms_acknowledged:
        raise ValueError(
            "TheSportsDB free API is for development use; app-store publication requires a paid subscription."
        )
    country_value = str(country or "").strip()
    if not country_value:
        raise ValueError("A country is required for TheSportsDB league discovery.")
    if isinstance(max_leagues, bool) or not isinstance(max_leagues, int) or not 1 <= max_leagues <= 10:
        raise ValueError("TheSportsDB free-tier staging is limited to 1-10 leagues per country.")
    owned = client is None
    api = client or TheSportsDBAdapter()
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    successful = 0
    league_ids = []
    try:
        leagues = api.leagues_by_country(country_value, sport="Soccer")
        for league in leagues[:max_leagues]:
            league_id = league.get("idLeague") or league.get("id")
            if not league_id:
                errors.append({"scope": str(league.get("strLeague") or "unknown"), "error": "Missing provider league ID."})
                continue
            league_ids.append(str(league_id))
            try:
                events = api.events_next_league(league_id)
                rows.extend(normalize_thesportsdb_events(events, league=league))
                successful += 1
            except Exception as exc:
                errors.append({"scope": str(league_id), "error": str(exc)[:300]})
            if request_delay_seconds > 0:
                time.sleep(min(float(request_delay_seconds), 5.0))
    except Exception as exc:
        errors.append({"scope": country_value, "error": str(exc)[:300]})
    finally:
        _close_owned(api, owned)
    return _archive(
        database_url, "thesportsdb",
        {
            "country": country_value,
            "sport": "Soccer",
            "league_ids": league_ids,
            "max_leagues": max_leagues,
            "terms_acknowledged": True,
        },
        rows, errors, successful,
    )


def collect_bzzoiro_observations(
    database_url: str,
    *,
    params: Mapping[str, Any] | None = None,
    client: BzzoiroAdapter | None = None,
    max_pages: int = 20,
) -> dict[str, Any]:
    """Collect authenticated Bzzoiro v2 upcoming events."""
    owned = client is None
    api = client
    errors: list[dict[str, str]] = []
    rows: list[dict[str, Any]] = []
    successful = 0
    query = {**dict(params or {}), "status": "upcoming"}
    try:
        if api is None:
            api = BzzoiroAdapter()
        rows = api.upcoming(params=query, max_pages=max_pages)
        successful = 1
    except Exception as exc:
        errors.append({"scope": "upcoming", "error": str(exc)[:300]})
    finally:
        _close_owned(api, owned)
    return _archive(
        database_url, "bzzoiro", query,
        rows, errors, successful,
    )
