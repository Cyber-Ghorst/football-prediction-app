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
        season_counts: dict[str, int] = {}
        for season in seasons:
            key = str(season.get("league_id") or "")
            season_counts[key] = season_counts.get(key, 0) + 1
        # Cross-check the account-scoped catalogue through Sportmonks' Core API
        # and the documented name-search route. These are reads only.
        api_root = client.base_url.rsplit("/football", 1)[0]
        try:
            response = client.session.get(
                f"{api_root}/my/leagues",
                timeout=client.timeout,
            )
            response.raise_for_status()
            my_leagues = client._rows(response.json())
            report["my_leagues"] = {
                "status": "ok",
                "http_status": response.status_code,
                "count": len(my_leagues),
                "league_ids": sorted(str(row.get("id")) for row in my_leagues if row.get("id") is not None),
            }
        except Exception as exc:
            report["my_leagues"] = {
                "status": "error",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }

        report["country_search_probes"] = {}
        for country_name in ("Germany", "France", "World", "International"):
            try:
                response = client.session.get(
                    f"{api_root}/core/countries/search/{country_name}",
                    params={"include": "leagues"},
                    timeout=client.timeout,
                )
                response.raise_for_status()
                country_rows = client._rows(response.json())
                report["country_search_probes"][country_name] = {
                    "status": "ok",
                    "http_status": response.status_code,
                    "count": len(country_rows),
                    "countries": [
                        {
                            "id": row.get("id"),
                            "name": row.get("name"),
                            "leagues": [
                                {
                                    "id": league.get("id"),
                                    "name": league.get("name"),
                                }
                                for league in client._rows(row.get("leagues"))
                            ],
                        }
                        for row in country_rows
                    ],
                }
            except Exception as exc:
                report["country_search_probes"][country_name] = {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }

        # Country -> leagues is a separate documented route. A country
        # include may expose catalogue records not returned by /leagues, so
        # verify each candidate through both country-scoped and ID endpoints.
        report["country_league_endpoint_probes"] = {}
        for country_name, country_probe in report["country_search_probes"].items():
            rows = country_probe.get("countries", []) if country_probe.get("status") == "ok" else []
            for country_row in rows:
                country_id = country_row.get("id")
                if country_id is None:
                    continue
                try:
                    country_leagues = client._all_pages(
                        f"leagues/countries/{country_id}",
                        include="country",
                    )
                    report["country_league_endpoint_probes"][country_name] = {
                        "status": "ok",
                        "country_id": country_id,
                        "count": len(country_leagues),
                        "matches": [
                            {
                                "id": str(row.get("id")),
                                "name": row.get("name"),
                                "country": _country_name(row),
                                "active": row.get("active"),
                                "type": row.get("type"),
                                "sub_type": row.get("sub_type"),
                            }
                            for row in country_leagues
                            if _norm(row.get("name")) in {"bundesliga", "ligue 1"}
                            or "bundesliga" in _norm(row.get("name"))
                            or "ligue 1" in _norm(row.get("name"))
                        ],
                    }
                except Exception as exc:
                    report["country_league_endpoint_probes"][country_name] = {
                        "status": "error",
                        "country_id": country_id,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }

        report["direct_league_id_probes"] = {}
        for target_name, provider_id in (("Bundesliga", 82), ("Ligue 1", 301)):
            try:
                payload = client._get(
                    f"leagues/{provider_id}",
                    {"include": "country;seasons"},
                )
                league_rows = client._rows(payload)
                report["direct_league_id_probes"][target_name] = {
                    "status": "ok",
                    "http_status": client.last_metadata.get("http_status"),
                    "count": len(league_rows),
                    "data": league_rows[0] if league_rows else None,
                }
            except Exception as exc:
                report["direct_league_id_probes"][target_name] = {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "http_status": client.last_metadata.get("http_status"),
                }

        search_queries = {
            "Bundesliga": ("Bundesliga",),
            "Ligue 1": ("Ligue 1", "Ligue"),
            "World Cup": ("World Cup", "FIFA World Cup"),
        }
        report["name_search_probes"] = {}
        for target_name, queries in search_queries.items():
            probe_rows = []
            for query in queries:
                try:
                    rows = client._all_pages(
                        f"leagues/search/{query}",
                        include="country",
                    )
                    probe_rows.append({
                        "query": query,
                        "status": "ok",
                        "count": len(rows),
                        "matches": [
                            {
                                "id": str(row.get("id")),
                                "name": row.get("name"),
                                "country": _country_name(row),
                                "country_id": row.get("country_id"),
                                "type": row.get("type"),
                                "sub_type": row.get("sub_type"),
                            }
                            for row in rows
                        ],
                    })
                except Exception as exc:
                    probe_rows.append({
                        "query": query,
                        "status": "error",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    })
            report["name_search_probes"][target_name] = probe_rows

        report["catalogue_leagues"] = [
            {
                "sportmonks_league_id": str(league.get("id")),
                "name": league.get("name"),
                "country": _country_name(league),
                "season_count": season_counts.get(str(league.get("id")), 0),
            }
            for league in leagues
        ]
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
