"""Collect and archive free future-fixture observations without canonical writes."""
from __future__ import annotations

from datetime import date
import re
from typing import Any, Mapping
from urllib.parse import quote
import time

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


def collect_livescore_observations(
    database_url: str,
    league_slugs: list[str],
    *,
    date_from: str,
    date_to: str,
    client: LiveScoreFootballClient | None = None,
    request_delay_seconds: float = 0.0,
    league_sync_times: Mapping[str, Any] | None = None,
    league_metadata: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Collect scheduled LiveScoreFootball events for explicitly supplied leagues."""
    if not league_slugs or not date_from or not date_to:
        raise ValueError("League slugs and an explicit date range are required.")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date_from)) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", str(date_to)
    ):
        raise ValueError("LiveScoreFootball dates must use YYYY-MM-DD.")
    try:
        start_date = date.fromisoformat(str(date_from))
        end_date = date.fromisoformat(str(date_to))
    except (TypeError, ValueError) as exc:
        raise ValueError("LiveScoreFootball dates must use valid calendar dates.") from exc
    if end_date < start_date:
        raise ValueError("LiveScoreFootball end date must not precede start date.")
    # The documented endpoint requires YYYYMMDD; accept ISO dates at this layer.
    api_date_from = start_date.strftime("%Y%m%d")
    api_date_to = end_date.strftime("%Y%m%d")
    owned = client is None
    api = client or LiveScoreFootballClient()
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    successful = 0
    sync_times = {str(key): value for key, value in (league_sync_times or {}).items()}
    metadata_by_slug = {
        str(key): dict(value)
        for key, value in (league_metadata or {}).items()
        if isinstance(value, Mapping)
    }
    try:
        if league_metadata is None or league_sync_times is None:
            try:
                catalogue = api.leagues(kind="all", available=True)
                if isinstance(catalogue, list):
                    for row in catalogue:
                        if not isinstance(row, Mapping):
                            continue
                        slug_key = (
                            row.get("slug") or row.get("league_slug") or row.get("leagueSlug")
                        )
                        if not slug_key:
                            continue
                        slug_key = str(slug_key)
                        if league_metadata is None:
                            metadata_by_slug[slug_key] = dict(row)
                        if league_sync_times is None:
                            sync_times[slug_key] = row.get("lastSyncedAt")
            except Exception:
                # Archive observations for diagnostics; promotion will block
                # them until the source provides an upstream sync timestamp.
                if league_sync_times is None:
                    sync_times = {}
                if league_metadata is None:
                    metadata_by_slug = {}
        for slug in league_slugs:
            try:
                events = api.fixtures(
                    slug, status="scheduled", date_from=api_date_from, date_to=api_date_to
                )
                source_url = (
                    f"{api.base_url}/get/soccer/{quote(str(slug), safe='')}/fixtures"
                )
                normalized = normalize_livescore_football_events(
                    events, league_key=str(slug), source_url=source_url,
                    league_metadata=metadata_by_slug.get(str(slug)),
                )
                for observation in normalized:
                    observation["source_sync_at"] = sync_times.get(str(slug))
                rows.extend(normalized)
                successful += 1
            except Exception as exc:
                errors.append({"scope": str(slug), "error": str(exc)[:300]})
            if request_delay_seconds > 0:
                time.sleep(min(float(request_delay_seconds), 5.0))
    finally:
        _close_owned(api, owned)
    return _archive(
        database_url, "livescore_football",
        {"league_slugs": list(league_slugs), "date_from": date_from,
         "date_to": date_to, "api_date_from": api_date_from,
         "api_date_to": api_date_to, "status": "scheduled",
         "league_sync_times": sync_times},
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
