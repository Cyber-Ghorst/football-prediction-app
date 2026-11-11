"""Bounded Sportmonks catalogue sync for canonical competition/season/team identities.

Imports current-season catalogue entities only. It fetches no fixtures or
statistics and never touches the Neon prediction ledger.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import sys
from contextlib import redirect_stdout
import re
import time
from typing import Any, Iterable, Mapping

from football_repository import ensure_football_repository, import_sportmonks_season
from sportmonks import SportmonksClient

DEFAULT_MAX_SEASONS = 40
MAX_ALLOWED_SEASONS = 100
PRIORITY_LEAGUES = (
    "premier league", "la liga", "bundesliga", "serie a", "ligue 1",
    "eredivisie", "primeira liga", "championship", "scottish premiership",
    "mls", "brasileirao serie a",
)


def _season_start_year(row: Mapping[str, Any]) -> int | None:
    for value in (row.get("starting_at"), row.get("name")):
        match = re.search(r"(?<!\d)(20\d{2})(?!\d)", str(value or ""))
        if match:
            return int(match.group(1))
    return None


def select_current_seasons(
    leagues: Iterable[Mapping[str, Any]],
    seasons: Iterable[Mapping[str, Any]],
    *,
    target_year: int,
    max_seasons: int = DEFAULT_MAX_SEASONS,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Return bounded current-year league/season pairs in predictable priority order."""
    if isinstance(max_seasons, bool) or not isinstance(max_seasons, int):
        raise ValueError("max_seasons must be an integer.")
    if not 1 <= max_seasons <= MAX_ALLOWED_SEASONS:
        raise ValueError(f"max_seasons must be between 1 and {MAX_ALLOWED_SEASONS}.")
    league_by_id = {
        str(row.get("id")): dict(row)
        for row in leagues
        if isinstance(row, Mapping) and row.get("id") is not None
    }
    selected: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for season in seasons:
        if not isinstance(season, Mapping) or season.get("id") is None:
            continue
        if _season_start_year(season) != int(target_year):
            continue
        league_id = season.get("league_id")
        league = league_by_id.get(str(league_id)) if league_id is not None else None
        if league is not None:
            selected[str(season["id"])] = (league, dict(season))

    def priority(pair: tuple[dict[str, Any], dict[str, Any]]) -> tuple[int, str, str]:
        league, season = pair
        name = str(league.get("name") or "").strip().casefold()
        rank = next((i for i, item in enumerate(PRIORITY_LEAGUES) if item in name), len(PRIORITY_LEAGUES))
        return rank, name, str(season.get("id"))

    return sorted(selected.values(), key=priority)[:max_seasons]


def sync_sportmonks_catalogue(
    database_url: str,
    *,
    target_year: int | None = None,
    max_seasons: int = DEFAULT_MAX_SEASONS,
    pause_seconds: float = 0.2,
    client_factory=SportmonksClient,
    importer=import_sportmonks_season,
    repository_initializer=ensure_football_repository,
) -> dict[str, Any]:
    """Import current-season leagues, seasons and teams; no fixtures or stats."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    if target_year is None:
        target_year = datetime.now(timezone.utc).year
    if isinstance(pause_seconds, bool) or float(pause_seconds) < 0:
        raise ValueError("pause_seconds must be non-negative.")
    started = datetime.now(timezone.utc)
    repository_initializer(database_url)
    report: dict[str, Any] = {
        "report_name": "sportmonks_canonical_catalogue_sync",
        "started_at_utc": started.isoformat(),
        "target_year": int(target_year),
        "max_seasons": int(max_seasons),
        "catalogue_only": True,
        "fixtures_requested": 0,
        "statistics_requested": 0,
        "neon_prediction_ledger_modified": False,
        "selected_seasons": 0,
        "imported_seasons": [],
        "errors": [],
    }
    with client_factory() as client:
        leagues = client.available_leagues(include="country")
        seasons = client.available_seasons()
        selected = select_current_seasons(
            leagues, seasons, target_year=int(target_year), max_seasons=int(max_seasons)
        )
        report["available_leagues"] = len(leagues)
        report["available_seasons"] = len(seasons)
        report["eligible_current_year_seasons"] = sum(
            1 for row in seasons if isinstance(row, Mapping)
            and _season_start_year(row) == int(target_year)
        )
        report["selected_seasons"] = len(selected)
        for index, (league, season) in enumerate(selected):
            season_id = str(season["id"])
            try:
                teams = client.teams_by_season(season_id)
                if not teams:
                    report["errors"].append({
                        "league": league.get("name"),
                        "season_id": season_id,
                        "error": "No teams returned; season was not imported.",
                    })
                    continue
                result = importer(
                    database_url, league=league, season=season,
                    teams=teams, fixtures=[],
                )
                report["imported_seasons"].append({
                    "league_id": str(league.get("id")),
                    "league": league.get("name"),
                    "country": (
                        league.get("country", {}).get("name")
                        if isinstance(league.get("country"), Mapping) else None
                    ),
                    "season_id": season_id,
                    "season": season.get("name"),
                    "teams_received": len(teams),
                    "teams_upserted": (result.get("upserted") or {}).get("teams", 0),
                    "fixtures_upserted": (result.get("upserted") or {}).get("fixtures", 0),
                    "provider_links_written": result.get("provider_links_written", 0),
                })
            except Exception as exc:
                report["errors"].append({
                    "league": league.get("name"),
                    "season_id": season_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:240],
                })
            if pause_seconds and index + 1 < len(selected):
                time.sleep(float(pause_seconds))
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["seasons_imported"] = len(report["imported_seasons"])
    report["teams_upserted"] = sum(x["teams_upserted"] for x in report["imported_seasons"])
    report["fixtures_upserted"] = sum(x["fixtures_upserted"] for x in report["imported_seasons"])
    report["provider_links_written"] = sum(x["provider_links_written"] for x in report["imported_seasons"])
    # A bounded catalogue run can make useful partial progress when a
    # provider endpoint refuses a complete page. Report that separately from
    # full coverage so a single inaccessible competition does not hide imports.
    report["success"] = bool(report["seasons_imported"])
    report["complete"] = (
        bool(report["seasons_imported"])
        and report["seasons_imported"] == report["selected_seasons"]
        and not report["errors"]
    )
    return report


def main() -> int:
    database_url = os.getenv("PROVIDER_DATABASE_URL", "").strip()
    year_value = os.getenv("SPORTMONKS_CATALOGUE_YEAR", "").strip()
    max_value = os.getenv("SPORTMONKS_CATALOGUE_MAX_SEASONS", str(DEFAULT_MAX_SEASONS))
    try:
        # Repository import helpers may emit progress messages. Keep stdout
        # reserved for the single machine-readable JSON report.
        with redirect_stdout(sys.stderr):
            report = sync_sportmonks_catalogue(
                database_url,
                target_year=int(year_value) if year_value else None,
                max_seasons=int(max_value),
            )
    except Exception as exc:
        report = {
            "report_name": "sportmonks_canonical_catalogue_sync",
            "success": False,
            "error_type": type(exc).__name__,
            "error": str(exc)[:240],
            "neon_prediction_ledger_modified": False,
        }
    print(json.dumps(report, sort_keys=True, default=str))
    return 0 if report.get("seasons_imported", 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
