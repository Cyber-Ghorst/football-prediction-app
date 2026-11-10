"""Read-only coverage audit for OpenScores competitions missing from Sportmonks.

Checks existing secondary providers without writing canonical entities, fixtures,
provider links, prediction inputs, or the prediction ledger.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from api_ninjas import APINinjasClient
from competition_crosswalk import normalize_competition_name, normalize_country
from highlightly import HighlightlyClient

TARGETS = (
    {"name": "Bundesliga", "country": "Germany", "season": 2025, "api_ninjas_slug": "bundesliga"},
    {"name": "Ligue 1", "country": "France", "season": 2025, "api_ninjas_slug": "ligue1"},
    {"name": "World Cup", "country": None, "season": 2026, "api_ninjas_slug": "worldcup"},
)


def _date_value(row: Mapping[str, Any]) -> str | None:
    for key in ("starting_at", "start_time", "date", "kickoff", "utcDate", "dateTime"):
        value = row.get(key)
        if value:
            return str(value)
    return None


def _team_names(row: Mapping[str, Any]) -> set[str]:
    names = set()
    for key in ("home_team_name", "away_team_name", "homeTeam", "awayTeam"):
        value = row.get(key)
        if isinstance(value, Mapping):
            value = value.get("name")
        if value:
            names.add(str(value))
    for key in ("home_team", "away_team"):
        value = row.get(key)
        if isinstance(value, Mapping):
            value = value.get("name")
        if value:
            names.add(str(value))
    return names


def _highlightly_audit(client: HighlightlyClient, target: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    page_size = 100
    for page in range(10):
        batch = client.matches(
            leagueName=target["name"],
            season=int(target["season"]),
            countryName=target["country"],
            limit=page_size,
            offset=page * page_size,
        )
        rows.extend(batch)
        if len(batch) < page_size:
            break
    else:
        raise RuntimeError("Highlightly pagination exceeded the safe 10-page limit")

    exact = []
    for row in rows:
        league = row.get("league") if isinstance(row.get("league"), Mapping) else {}
        league_name = league.get("name") or row.get("leagueName")
        country = league.get("country") or {}
        if isinstance(country, Mapping):
            country_name = country.get("name")
        else:
            country_name = country or league.get("countryName") or row.get("countryName")
        season = league.get("season") if league.get("season") is not None else row.get("season")
        try:
            season_value = int(season.get("year") if isinstance(season, Mapping) else season)
        except (TypeError, ValueError):
            season_value = None
        if normalize_competition_name(str(league_name or "")) != normalize_competition_name(target["name"]):
            continue
        if target["country"] and normalize_country(str(country_name or "")) != normalize_country(target["country"]):
            continue
        if season_value != int(target["season"]):
            continue
        exact.append(row)

    dates = sorted(value for value in (_date_value(row) for row in exact) if value)
    teams = sorted({name for row in exact for name in _team_names(row)})
    return {
        "status": "exact_coverage" if exact else "no_exact_coverage",
        "rows_returned": len(rows),
        "exact_identity_rows": len(exact),
        "distinct_teams": len(teams),
        "team_names_sample": teams[:12],
        "earliest_fixture": dates[0] if dates else None,
        "latest_fixture": dates[-1] if dates else None,
        "request_metadata": dict(client.last_metadata or {}),
    }


def _api_ninjas_audit(client: APINinjasClient, target: Mapping[str, Any]) -> dict[str, Any]:
    rows = client.matches(
        league=str(target["api_ninjas_slug"]),
        season=int(target["season"]),
    )
    exact = []
    for row in rows:
        league = str(row.get("league") or target["api_ninjas_slug"])
        season = row.get("season")
        if league != str(target["api_ninjas_slug"]):
            continue
        if season is not None and str(season) != str(target["season"]):
            continue
        exact.append(row)
    dates = sorted(value for value in (_date_value(row) for row in exact) if value)
    teams = sorted({name for row in exact for name in _team_names(row)})
    return {
        "status": "exact_coverage" if exact else "no_exact_coverage",
        "rows_returned": len(rows),
        "exact_identity_rows": len(exact),
        "distinct_teams": len(teams),
        "team_names_sample": teams[:12],
        "earliest_fixture": dates[0] if dates else None,
        "latest_fixture": dates[-1] if dates else None,
        "request_metadata": dict(client.last_metadata or {}),
    }


def run_audit() -> dict[str, Any]:
    report: dict[str, Any] = {
        "operation": "openscores_secondary_provider_coverage_audit",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "canonical_tables_modified": False,
        "provider_entity_links_written": 0,
        "prediction_ledger_touched": False,
        "targets": [],
    }
    for target in TARGETS:
        row = {
            "competition": target["name"],
            "country": target["country"],
            "season": target["season"],
            "providers": {},
        }
        for provider, client_type, fn in (
            ("highlightly", HighlightlyClient, _highlightly_audit),
            ("api_ninjas", APINinjasClient, _api_ninjas_audit),
        ):
            client = None
            try:
                with client_type() as client:
                    row["providers"][provider] = fn(client, target)
            except Exception as exc:
                row["providers"][provider] = {
                    "status": "unavailable_or_error",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:240],
                    "request_metadata": dict(getattr(client, "last_metadata", {}) or {}),
                }
        report["targets"].append(row)

    coverage_count = sum(
        1
        for target in report["targets"]
        for provider in target["providers"].values()
        if provider.get("status") == "exact_coverage"
    )
    report["providers_with_exact_coverage"] = coverage_count
    report["status"] = "pass" if coverage_count else "no_secondary_coverage"
    return report


def main() -> int:
    report = run_audit()
    Path("openscores-secondary-provider-coverage-report.json").write_text(
        json.dumps(report, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, default=str))
    summary_path = __import__("os").getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("## OpenScores secondary-provider coverage audit\n\n")
            summary.write(f"- Status: {report['status']}\n")
            summary.write(f"- Providers with exact competition/season coverage: {coverage_count}\n")
            summary.write("- Read-only: yes; canonical tables and prediction ledger unchanged\n")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
