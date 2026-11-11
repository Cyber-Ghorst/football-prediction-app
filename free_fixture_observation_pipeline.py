"""Collect and archive free future-fixture observations without canonical writes."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
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
    normalize_highlightly_matches,
    normalize_api_ninjas_matches,
    API_NINJAS_FREE_LEAGUES,
    API_NINJAS_LEAGUE_NAMES,
)
from free_fixture_observation_store import archive_future_fixture_observations
from livescore_football import LiveScoreFootballClient


def _close_owned(client: Any, owned: bool) -> None:
    if owned:
        close = getattr(client, "close", None)
        if callable(close):
            close()
        else:
            session = getattr(client, "session", None)
            session_close = getattr(session, "close", None)
            if callable(session_close):
                session_close()


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


def collect_highlightly_observations(
    database_url: str,
    *,
    date_from: str,
    days: int = 7,
    client: Any | None = None,
    page_size: int = 100,
    max_pages: int = 10,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Collect Highlightly scheduled matches by UTC day, paging each date."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date_from)):
        raise ValueError("Highlightly date_from must use YYYY-MM-DD.")
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 7:
        raise ValueError("Highlightly days must be an integer from 1 through 7.")
    if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 100:
        raise ValueError("Highlightly page_size must be between 1 and 100.")
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or not 1 <= max_pages <= 20:
        raise ValueError("Highlightly max_pages must be between 1 and 20.")
    try:
        start = date.fromisoformat(date_from)
    except ValueError as exc:
        raise ValueError("Highlightly date_from must be a valid calendar date.") from exc

    owned = client is None
    api = client
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    successful = 0
    dates = [(start + timedelta(days=offset)).isoformat() for offset in range(days)]
    try:
        if api is None:
            from highlightly import HighlightlyClient
            api = HighlightlyClient(api_key=api_key)
        for day in dates:
            offset = 0
            day_succeeded = False
            for page in range(max_pages):
                try:
                    batch = api.matches(
                        date=day, timezone="Etc/UTC",
                        limit=page_size, offset=offset,
                    )
                    if not isinstance(batch, list):
                        raise ValueError("Highlightly matches response was not a list.")
                    fetched = datetime.now(timezone.utc)
                    rows.extend(normalize_highlightly_matches(
                        batch, fetched_at=fetched,
                        source_url=f"{api.base_url}/matches",
                    ))
                    day_succeeded = True
                    pagination = getattr(api, "last_metadata", {}).get("pagination") or {}
                    total = pagination.get("total_count")
                    offset += len(batch)
                    if len(batch) < page_size or (
                        isinstance(total, int) and offset >= total
                    ):
                        break
                    if page == max_pages - 1:
                        errors.append({
                            "scope": day,
                            "error": f"Pagination cap reached at {max_pages} pages; remaining matches may be truncated.",
                        })
                except Exception as exc:
                    errors.append({"scope": day, "error": str(exc)[:300]})
                    break
            if day_succeeded:
                successful += 1
    finally:
        _close_owned(api, owned)
    report = _archive(
        database_url, "highlightly",
        {"dates": dates, "timezone": "Etc/UTC", "status": "Not started",
         "page_size": page_size, "max_pages": max_pages},
        rows, errors, successful,
    )
    metadata = getattr(api, "last_metadata", {})
    report["provider_metadata"] = dict(metadata) if isinstance(metadata, Mapping) else {}
    return report


def collect_api_ninjas_observations(
    database_url: str,
    *,
    season: int,
    leagues: list[str] | None = None,
    client: Any | None = None,
    page_size: int = 50,
    max_pages: int = 10,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Collect current-season scheduled API Ninjas fixtures for its free-tier leagues."""
    if isinstance(season, bool) or not isinstance(season, int) or season < 1900:
        raise ValueError("API Ninjas season must be a valid integer start year.")
    if isinstance(page_size, bool) or not isinstance(page_size, int) or page_size != 50:
        raise ValueError("API Ninjas page_size must remain at the documented default of 50.")
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or not 1 <= max_pages <= 20:
        raise ValueError("API Ninjas max_pages must be between 1 and 20.")
    selected_leagues = list(leagues or API_NINJAS_FREE_LEAGUES)
    if not selected_leagues:
        raise ValueError("At least one API Ninjas free-tier league is required.")

    owned = client is None
    api = client
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    successful = 0
    try:
        if api is None:
            from api_ninjas import APINinjasClient
            api = APINinjasClient(api_key=api_key)
        for league in selected_leagues:
            league_key = str(league or "").strip().casefold()
            if league_key not in API_NINJAS_FREE_LEAGUES:
                errors.append({
                    "scope": league_key or "unknown",
                    "error": "League is outside the documented free-tier competition set.",
                })
                continue
            league_succeeded = False
            offset = 0
            for page in range(max_pages):
                try:
                    batch = api.matches(
                        league=league_key, season=season,
                        status="scheduled", offset=offset,
                    )
                    if not isinstance(batch, list):
                        raise ValueError("API Ninjas matches response was not a list.")
                    fetched = datetime.now(timezone.utc)
                    rows.extend(normalize_api_ninjas_matches(
                        batch, league=league_key, season=season, fetched_at=fetched,
                    ))
                    league_succeeded = True
                    offset += len(batch)
                    if len(batch) < page_size:
                        break
                    if page == max_pages - 1:
                        errors.append({
                            "scope": league_key,
                            "error": f"Pagination cap reached at {max_pages} pages; remaining matches may be truncated.",
                        })
                except Exception as exc:
                    errors.append({"scope": league_key, "error": str(exc)[:300]})
                    break
            if league_succeeded:
                successful += 1
    finally:
        _close_owned(api, owned)
    report = _archive(
        database_url, "api_ninjas",
        {"leagues": selected_leagues, "season": season,
         "status": "scheduled", "page_size": page_size, "max_pages": max_pages},
        rows, errors, successful,
    )
    metadata = getattr(api, "last_metadata", {})
    report["provider_metadata"] = dict(metadata) if isinstance(metadata, Mapping) else {}
    return report
