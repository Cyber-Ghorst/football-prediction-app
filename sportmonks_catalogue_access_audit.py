"""Read-only audit of the Sportmonks account catalogue.

This operation performs no database writes and never creates entity links.
It establishes whether requested competitions/seasons are actually visible
through the configured Sportmonks subscription before reconciliation is run.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from sportmonks import SportmonksClient

TARGETS = (
    {"name": "Bundesliga", "country": "Germany", "country_code": "DEU"},
    {"name": "Ligue 1", "country": "France", "country_code": "FRA"},
    {"name": "World Cup", "country": "", "country_code": ""},
)


def _country_name(league: Mapping[str, Any]) -> str:
    country = league.get("country") or league.get("country_name") or ""
    if isinstance(country, Mapping):
        return str(country.get("name") or country.get("official_name") or "")
    return str(country or "")


def _norm(value: Any) -> str:
    return " ".join(str(value or "").casefold().replace("&", "and").split())


def build_catalogue_report(client_factory=SportmonksClient) -> dict[str, Any]:
    report: dict[str, Any] = {
        "operation": "sportmonks_catalogue_access_audit",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "fail",
        "read_only": True,
        "database_touched": False,
        "entity_links_written": 0,
        "prediction_model_modified": False,
        "prediction_ledger_touched": False,
        "league_catalogue_count": 0,
        "season_catalogue_count": 0,
        "targets": [],
    }
    with client_factory() as client:
        leagues = client.available_leagues(include="country")
        seasons = client.available_seasons()
        report["league_catalogue_count"] = len(leagues)
        report["season_catalogue_count"] = len(seasons)
        for target in TARGETS:
            matches = [
                row for row in leagues
                if _norm(row.get("name")) == _norm(target["name"])
                and (
                    _norm(_country_name(row)) == _norm(target["country"])
                    if target["country"] else
                    _norm(_country_name(row)) in {"", "world", "international", "global"}
                )
            ]
            target_result = {
                **target,
                "status": "unique_exact_catalogue_match" if len(matches) == 1 else
                          "ambiguous_catalogue_match" if matches else
                          "not_visible_in_account_catalogue",
                "candidate_count": len(matches),
                "candidates": [],
            }
            for league in matches:
                league_id = league.get("id")
                league_seasons = [
                    season for season in seasons
                    if str(season.get("league_id")) == str(league_id)
                ]
                target_result["candidates"].append({
                    "sportmonks_league_id": str(league_id),
                    "catalogue_name": league.get("name"),
                    "catalogue_country": _country_name(league),
                    "season_count": len(league_seasons),
                    "seasons": [
                        {
                            "sportmonks_season_id": str(season.get("id")),
                            "name": season.get("name"),
                            "starting_at": season.get("starting_at"),
                            "ending_at": season.get("ending_at"),
                        }
                        for season in league_seasons
                    ],
                })
            report["targets"].append(target_result)
    statuses = {item["status"] for item in report["targets"]}
    report["status"] = "pass" if statuses == {"unique_exact_catalogue_match"} else "partial"
    return report


def main() -> int:
    try:
        report = build_catalogue_report()
    except Exception as exc:
        report = {
            "operation": "sportmonks_catalogue_access_audit",
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "fail",
            "read_only": True,
            "database_touched": False,
            "entity_links_written": 0,
            "prediction_model_modified": False,
            "prediction_ledger_touched": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    serialized = json.dumps(report, indent=2, default=str)
    Path("sportmonks-catalogue-access-report.json").write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("## Sportmonks account catalogue access audit\n\n")
            summary.write(f"- Status: {report['status']}\n")
            summary.write(f"- Leagues visible: {report.get('league_catalogue_count', 0)}\n")
            summary.write(f"- Seasons visible: {report.get('season_catalogue_count', 0)}\n")
            summary.write("- Database touched: no\n- Entity links written: 0\n")
            for item in report.get("targets", []):
                summary.write(f"- {item['name']} ({item['country_code'] or 'international'}): {item['status']} ({item['candidate_count']} candidates)\n")
    return 0 if report["status"] in {"pass", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
