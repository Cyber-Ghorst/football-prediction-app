"""Autonomous, read-only OpenScores connection and fixture-schema diagnostic."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from openscores import OpenScoresClient


def _find_records(value: Any, preferred: tuple[str, ...], depth: int = 0):
    """Find a list of ID-bearing records without assuming one response wrapper."""
    if depth > 6:
        return None, None
    if isinstance(value, list):
        if value and all(isinstance(row, dict) and
                         any(key in row for key in ("id", "league_id", "season_id", "fixture_id"))
                         for row in value):
            return value, "$"
        return None, None
    if isinstance(value, dict):
        for key in preferred:
            if key in value:
                rows, path = _find_records(value[key], preferred, depth + 1)
                if rows is not None:
                    return rows, key if path == "$" else f"{key}.{path}"
        for key, child in value.items():
            if key not in preferred and isinstance(child, (dict, list)):
                rows, path = _find_records(child, preferred, depth + 1)
                if rows is not None:
                    return rows, f"{key}.{path}"
    return None, None


def _record_shape(records: list[dict[str, Any]] | None) -> dict[str, Any]:
    if records is None:
        return {"collection_found": False, "count": None, "first_record_keys": []}
    first = records[0] if records else {}
    nested = {}
    for key, value in list(first.items())[:30]:
        nested[str(key)] = {
            "type": type(value).__name__,
            "keys": sorted(str(k) for k in value.keys())[:25] if isinstance(value, dict) else None,
            "first_item_keys": sorted(str(k) for k in value[0].keys())[:25]
            if isinstance(value, list) and value and isinstance(value[0], dict) else None,
        }
    return {
        "collection_found": True,
        "count": len(records),
        "first_record_keys": sorted(str(key) for key in first.keys())[:40],
        "first_record_field_shapes": nested,
    }


def run_check(client_factory: Callable[[], OpenScoresClient] = OpenScoresClient) -> dict:
    """Probe league → season → fixture discovery; never persist or expose raw records."""
    report = {
        "operation": "openscores_connection_check",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "openscores",
        "status": "fail",
        "authenticated": False,
        "league_count_returned": None,
        "season_count_sampled": None,
        "fixture_count_sampled": None,
        "league_response_shape": None,
        "season_response_shape": None,
        "fixture_response_shape": None,
        "requests_attempted": 0,
        "read_only": True,
        "prediction_ledger_touched": False,
        "fixtures_imported": False,
    }
    try:
        with client_factory() as client:
            league_result = client.list_leagues()
            report["requests_attempted"] += 1
            league_data = league_result.get("data")
            leagues, league_path = client._league_collection(league_data)
            report["authenticated"] = True
            report["league_count_returned"] = len(leagues) if leagues is not None else None
            report["league_collection_path"] = league_path
            report["league_response_shape"] = _record_shape(leagues)
            if leagues:
                league_id = leagues[0].get("id") or leagues[0].get("league_id")
                if league_id is not None:
                    season_result = client.list_seasons(league_id)
                    report["requests_attempted"] += 1
                    season_data = season_result.get("data")
                    seasons, season_path = _find_records(
                        season_data, ("seasons", "items", "results", "data", "records")
                    )
                    report["season_count_sampled"] = len(seasons) if seasons is not None else None
                    report["season_collection_path"] = season_path
                    report["season_response_shape"] = _record_shape(seasons)
                    if seasons:
                        season_id = seasons[0].get("id") or seasons[0].get("season_id")
                        if season_id is not None:
                            fixture_result = client.list_fixtures(season_id=season_id)
                            report["requests_attempted"] += 1
                            fixture_data = fixture_result.get("data")
                            fixtures, fixture_path = _find_records(
                                fixture_data, ("fixtures", "items", "results", "data", "records")
                            )
                            report["fixture_count_sampled"] = len(fixtures) if fixtures is not None else None
                            report["fixture_collection_path"] = fixture_path
                            report["fixture_response_shape"] = _record_shape(fixtures)
            report["status"] = "pass"
    except Exception as exc:
        report["error_type"] = type(exc).__name__
    return report


def main() -> int:
    report = run_check()
    serialized = json.dumps(report, indent=2)
    Path("openscores-connection-report.json").write_text(serialized + "\\n", encoding="utf-8")
    print(serialized)
    try:
        with open(__import__("os").environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write("## OpenScores fixture-schema diagnostic\\n\\n")
            for key in ("status", "authenticated", "league_count_returned",
                        "season_count_sampled", "fixture_count_sampled", "requests_attempted"):
                summary.write(f"- {key}: {report.get(key)}\\n")
            summary.write("- Read-only: yes; fixtures imported: no; prediction ledger touched: no\\n")
            for key in ("league_response_shape", "season_response_shape", "fixture_response_shape"):
                summary.write(f"\\n### {key}\\n\\n```json\\n{json.dumps(report.get(key), indent=2)}\\n```\\n")
    except KeyError:
        pass
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
