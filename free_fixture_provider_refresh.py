"""Scheduled read-only refresh of free future-fixture provider observations."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from free_fixture_adapters import (
    BzzoiroAdapter,
    OpenFootballAdapter,
    OpenLigaDBAdapter,
)
from free_fixture_observation_pipeline import (
    collect_bzzoiro_observations,
    collect_highlightly_observations,
    collect_api_ninjas_observations,
    collect_livescore_observations,
    collect_openfootball_observations,
    collect_openligadb_observations,
)
from livescore_football import LiveScoreFootballClient


def _rotate_batch(items: list[Any], batch_size: int, slot: int) -> list[Any]:
    if not items:
        return []
    size = max(1, int(batch_size))
    start = (max(0, int(slot)) * size) % len(items)
    return [items[(start + offset) % len(items)] for offset in range(min(size, len(items)))]


def _error(provider: str, exc: Exception) -> dict[str, Any]:
    return {
        "provider": provider,
        "archived": False,
        "observation_count": 0,
        "eligible_for_review_count": 0,
        "errors": [{"scope": "discovery", "error": f"{type(exc).__name__}: {str(exc)[:250]}"}],
    }


def refresh_free_fixture_sources(
    database_url: str,
    *,
    today: datetime | None = None,
    bzzoiro_token: str | None = None,
    highlightly_token: str | None = None,
    api_ninjas_token: str | None = None,
    max_openligadb_scopes: int = 45,
    max_livescore_leagues: int = 30,
) -> dict[str, Any]:
    """Discover current provider scopes, collect schedules and archive observations."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    now = today or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    season_start_year = now.year if now.month >= 7 else now.year - 1
    date_from = now.date().isoformat()
    date_to = (now.date() + timedelta(days=7)).isoformat()
    batch_slot = int(now.timestamp() // (6 * 60 * 60))
    results: dict[str, Any] = {}

    # OpenLigaDB publishes a league catalogue by season. Keep requests below
    # its documented 60/minute ceiling and archive only future scheduled rows
    # as eligible observations.
    try:
        with OpenLigaDBAdapter() as client:
            all_scopes = client.discover_scopes(
                [season_start_year, season_start_year + 1],
                max_scopes=1000,
            )
            scopes = _rotate_batch(all_scopes, max_openligadb_scopes, batch_slot)
            results["openligadb"] = collect_openligadb_observations(
                database_url, scopes, client=client, request_delay_seconds=1.05,
            ) if scopes else {
                "provider": "openligadb", "archived": False,
                "observation_count": 0, "eligible_for_review_count": 0,
                "errors": [{"scope": "discovery", "error": "No current-season league scopes returned."}],
            }
    except Exception as exc:
        results["openligadb"] = _error("openligadb", exc)

    # football.json's current-season directory is public. Dataset filenames
    # are discovered rather than hard-coded; timezone-less kickoff rows remain
    # excluded by the adapter.
    season_dir = f"{season_start_year}-{str((season_start_year + 1) % 100).zfill(2)}"
    try:
        with OpenFootballAdapter() as client:
            datasets = client.discover_season_files(season_dir)
            results["openfootball"] = collect_openfootball_observations(
                database_url, datasets, client=client,
            ) if datasets else {
                "provider": "openfootball", "archived": False,
                "observation_count": 0, "eligible_for_review_count": 0,
                "errors": [{"scope": season_dir, "error": "No JSON season files returned."}],
            }
    except Exception as exc:
        results["openfootball"] = _error("openfootball", exc)

    # LiveScoreFootball discovery is bounded to avoid an uncontrolled burst of
    # per-league calls. Only explicit league slugs are queried.
    livescore_client = None
    try:
        livescore_client = LiveScoreFootballClient()
        league_rows = livescore_client.leagues(kind="all", available=True)
        slugs = []
        league_sync_times = {}
        if isinstance(league_rows, list):
            for row in league_rows:
                if not isinstance(row, dict):
                    continue
                slug = row.get("slug") or row.get("league_slug") or row.get("leagueSlug")
                if slug and str(slug) not in slugs:
                    slugs.append(str(slug))
                    league_sync_times[str(slug)] = row.get("lastSyncedAt")
        all_slugs = list(slugs)
        slugs = _rotate_batch(all_slugs, max_livescore_leagues, batch_slot)
        results["livescore_football"] = collect_livescore_observations(
            database_url, slugs, date_from=date_from, date_to=date_to,
            client=livescore_client, request_delay_seconds=0.5,
            league_sync_times=league_sync_times,
        ) if slugs else {
            "provider": "livescore_football", "archived": False,
            "observation_count": 0, "eligible_for_review_count": 0,
            "errors": [{"scope": "discovery", "error": "No league slugs returned by the league catalogue."}],
        }
    except Exception as exc:
        results["livescore_football"] = _error("livescore_football", exc)
    finally:
        if livescore_client is not None:
            livescore_client.close()

    # Bzzoiro's v2 upcoming endpoint returns all accessible competitions via
    # pagination. The token is passed only to the client, never to snapshot metadata.
    try:
        if bzzoiro_token:
            with BzzoiroAdapter(token=bzzoiro_token) as client:
                results["bzzoiro"] = collect_bzzoiro_observations(
                    database_url, client=client, max_pages=20,
                )
        else:
            results["bzzoiro"] = collect_bzzoiro_observations(database_url, max_pages=20)
    except Exception as exc:
        results["bzzoiro"] = _error("bzzoiro", exc)

    # Highlightly documents scheduled matches with stable IDs and UTC dates.
    # Query each UTC day separately and retain all observations for review only.
    if highlightly_token:
        try:
            results["highlightly"] = collect_highlightly_observations(
                database_url, date_from=date_from, days=7,
                api_key=highlightly_token,
            )
        except Exception as exc:
            results["highlightly"] = _error("highlightly", exc)
    else:
        results["highlightly"] = {
            "provider": "highlightly", "archived": False,
            "observation_count": 0, "eligible_for_review_count": 0,
            "skipped": "HIGHLIGHTLY_API_KEY is not configured",
            "errors": [],
        }

    # API Ninjas' documented free tier covers eight current-season leagues.
    # Restrict discovery to those leagues and keep the result read-only.
    if api_ninjas_token:
        try:
            results["api_ninjas"] = collect_api_ninjas_observations(
                database_url, season=season_start_year,
                api_key=api_ninjas_token,
            )
        except Exception as exc:
            results["api_ninjas"] = _error("api_ninjas", exc)
    else:
        results["api_ninjas"] = {
            "provider": "api_ninjas", "archived": False,
            "observation_count": 0, "eligible_for_review_count": 0,
            "skipped": "API_NINJAS_API_KEY is not configured",
            "errors": [],
        }

    # Open Matchday is intentionally excluded from unattended refresh because
    # its upstream licence is non-commercial-only. The manual UI requires an
    # explicit acknowledgement before any collection.
    results["open_matchday"] = {
        "provider": "open_matchday",
        "archived": False,
        "observation_count": 0,
        "eligible_for_review_count": 0,
        "skipped": "non-commercial-only licence; manual acknowledgement required",
        "errors": [],
    }
    return {
        "run_at": now.isoformat(),
        "window": {"date_from": date_from, "date_to": date_to},
        "batch_slot": batch_slot,
        "providers": results,
        "canonical_fixture_writes": 0,
        "prediction_ledger_writes": 0,
    }


def main() -> int:
    database_url = os.getenv("PROVIDER_DATABASE_URL", "")
    token = os.getenv("BZZOIRO_API_TOKEN", "")
    highlightly_token = os.getenv("HIGHLIGHTLY_API_KEY") or os.getenv("API_FOOTBALL_KEY")
    api_ninjas_token = os.getenv("API_NINJAS_API_KEY") or os.getenv("API_NINJAS_KEY")
    max_openligadb = int(os.getenv("FREE_FIXTURE_OPENLIGADB_MAX_SCOPES", "45"))
    max_livescore = int(os.getenv("FREE_FIXTURE_LIVESCORE_MAX_LEAGUES", "30"))
    report = refresh_free_fixture_sources(
        database_url,
        bzzoiro_token=token or None,
        highlightly_token=highlightly_token or None,
        api_ninjas_token=api_ninjas_token or None,
        max_openligadb_scopes=max_openligadb,
        max_livescore_leagues=max_livescore,
    )
    print(json.dumps(report, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
