"""Collect and archive free future-fixture observations without canonical writes."""
from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import quote

from free_fixture_adapters import (
    BzzoiroAdapter,
    OpenFootballAdapter,
    OpenLigaDBAdapter,
    OpenMatchdayAdapter,
    normalize_livescore_football_events,
)
from free_fixture_observation_store import archive_future_fixture_observations
from livescore_football import LiveScoreFootballClient


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
        "successful_scopes": successful_scopes,
        "errors": errors,
    }


def collect_openligadb_observations(
    database_url: str,
    scopes: list[Mapping[str, Any]],
    *,
    client: OpenLigaDBAdapter | None = None,
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


def collect_livescore_observations(
    database_url: str,
    league_slugs: list[str],
    *,
    date_from: str,
    date_to: str,
    client: LiveScoreFootballClient | None = None,
) -> dict[str, Any]:
    """Collect scheduled LiveScoreFootball events for explicitly supplied leagues."""
    if not league_slugs or not date_from or not date_to:
        raise ValueError("League slugs and an explicit date range are required.")
    owned = client is None
    api = client or LiveScoreFootballClient()
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    successful = 0
    try:
        for slug in league_slugs:
            try:
                events = api.fixtures(
                    slug, status="scheduled", date_from=date_from, date_to=date_to
                )
                source_url = (
                    f"{api.base_url}/get/soccer/{quote(str(slug), safe='')}/fixtures"
                )
                rows.extend(normalize_livescore_football_events(
                    events, league_key=str(slug), source_url=source_url
                ))
                successful += 1
            except Exception as exc:
                errors.append({"scope": str(slug), "error": str(exc)[:300]})
    finally:
        _close_owned(api, owned)
    return _archive(
        database_url, "livescore_football",
        {"league_slugs": list(league_slugs), "date_from": date_from,
         "date_to": date_to, "status": "scheduled"},
        rows, errors, successful,
    )


def collect_bzzoiro_observations(
    database_url: str,
    *,
    params: Mapping[str, Any] | None = None,
    client: BzzoiroAdapter | None = None,
) -> dict[str, Any]:
    """Collect authenticated Bzzoiro v2 upcoming events."""
    owned = client is None
    api = client or BzzoiroAdapter()
    errors: list[dict[str, str]] = []
    rows: list[dict[str, Any]] = []
    successful = 0
    try:
        rows = api.upcoming(params=dict(params or {}))
        successful = 1
    except Exception as exc:
        errors.append({"scope": "upcoming", "error": str(exc)[:300]})
    finally:
        _close_owned(api, owned)
    return _archive(
        database_url, "bzzoiro", {"status": "upcoming", **dict(params or {})},
        rows, errors, successful,
    )
