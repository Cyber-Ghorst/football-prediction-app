"""Read-only OpenScores fixture, team and player response-shape audit.

This audit probes one provider-native sample chain and records schema metadata
only. It does not persist provider payloads or create canonical mappings.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from openscores import OpenScoresClient


def find_records(value: Any, preferred: tuple[str, ...], depth: int = 0):
    if depth > 6:
        return None, None
    if isinstance(value, list):
        if value and all(
            isinstance(row, dict)
            and any(key in row for key in ("id", "league_id", "season_id", "fixture_id", "team_id", "player_id"))
            for row in value
        ):
            return value, "$"
        return None, None
    if isinstance(value, dict):
        for key in preferred:
            if key in value:
                rows, path = find_records(value[key], preferred, depth + 1)
                if rows is not None:
                    return rows, key if path == "$" else f"{key}.{path}"
        for key, child in value.items():
            if key not in preferred and isinstance(child, (dict, list)):
                rows, path = find_records(child, preferred, depth + 1)
                if rows is not None:
                    return rows, f"{key}.{path}"
    return None, None


def payload_shape(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        fields = {}
        for key, child in list(value.items())[:40]:
            fields[str(key)] = {
                "type": type(child).__name__,
                "keys": sorted(str(k) for k in child.keys())[:30] if isinstance(child, dict) else None,
                "list_length": len(child) if isinstance(child, list) else None,
                "first_item_keys": sorted(str(k) for k in child[0].keys())[:30]
                if isinstance(child, list) and child and isinstance(child[0], dict) else None,
            }
        return {"root_type": "dict", "root_keys": sorted(str(k) for k in value)[:50], "fields": fields}
    if isinstance(value, list):
        return {
            "root_type": "list",
            "length": len(value),
            "first_item_type": type(value[0]).__name__ if value else None,
            "first_item_keys": sorted(str(k) for k in value[0])[:50]
            if value and isinstance(value[0], dict) else [],
        }
    return {"root_type": type(value).__name__}


def extract_id(value: Any, direct_keys: tuple[str, ...], nested_keys: tuple[str, ...] = ()) -> int | str | None:
    if not isinstance(value, dict):
        return None
    for key in direct_keys:
        candidate = value.get(key)
        if isinstance(candidate, (int, str)) and str(candidate).strip():
            return candidate
    for key in nested_keys:
        candidate = value.get(key)
        if isinstance(candidate, dict):
            found = extract_id(candidate, ("id", "team_id", "player_id"))
            if found is not None:
                return found
        elif isinstance(candidate, (int, str)) and str(candidate).strip():
            return candidate
    return None


def run_audit(client_factory: Callable[[], OpenScoresClient] = OpenScoresClient) -> dict[str, Any]:
    report: dict[str, Any] = {
        "operation": "openscores_data_shape_audit",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "openscores",
        "status": "fail",
        "read_only": True,
        "raw_provider_values_published": False,
        "database_writes": False,
        "prediction_ledger_touched": False,
        "canonical_mappings_created": False,
        "requests_attempted": 0,
        "tool_names": [],
        "league_count_sampled": 0,
        "season_count_sampled": 0,
        "fixture_count_sampled": 0,
        "fixture_detail_status": "not_attempted",
        "team_detail_status": "not_attempted",
        "player_detail_status": "not_attempted",
    }
    try:
        with client_factory() as client:
            catalogue = client.list_tools()
            report["requests_attempted"] += 1
            tools = catalogue.get("tools", [])
            report["tool_names"] = sorted(
                str(item.get("name")) for item in tools
                if isinstance(item, dict) and item.get("name")
            )
            report["tool_argument_fields"] = {
                str(item["name"]): sorted(
                    (item.get("inputSchema") or {}).get("properties", {}).keys()
                )
                for item in tools
                if isinstance(item, dict) and item.get("name")
            }

            league_result = client.list_leagues()
            report["requests_attempted"] += 1
            leagues, league_path = client._league_collection(league_result.get("data"))
            report["league_count_sampled"] = len(leagues or [])
            report["league_collection_path"] = league_path
            report["league_shape"] = payload_shape(leagues[0]) if leagues else None
            if not leagues:
                raise RuntimeError("No identifiable league records returned.")

            league_id = extract_id(leagues[0], ("id", "league_id"))
            if league_id is None:
                raise RuntimeError("Sample league had no usable provider ID.")

            season_result = client.list_seasons(league_id)
            report["requests_attempted"] += 1
            seasons, season_path = find_records(
                season_result.get("data"), ("seasons", "items", "results", "data", "records")
            )
            report["season_count_sampled"] = len(seasons or [])
            report["season_collection_path"] = season_path
            report["season_shape"] = payload_shape(seasons[0]) if seasons else None
            if not seasons:
                raise RuntimeError("No identifiable season records returned.")

            season_id = extract_id(seasons[0], ("id", "season_id"))
            if season_id is None:
                raise RuntimeError("Sample season had no usable provider ID.")

            fixture_result = client.list_fixtures(season_id=season_id)
            report["requests_attempted"] += 1
            fixtures, fixture_path = find_records(
                fixture_result.get("data"), ("fixtures", "items", "results", "data", "records")
            )
            report["fixture_count_sampled"] = len(fixtures or [])
            report["fixture_collection_path"] = fixture_path
            report["fixture_shape"] = payload_shape(fixtures[0]) if fixtures else None
            if not fixtures:
                raise RuntimeError("No identifiable fixture records returned.")

            fixture_id = extract_id(fixtures[0], ("id", "fixture_id"))
            if fixture_id is None:
                raise RuntimeError("Sample fixture had no usable provider ID.")

            detail = client.get_fixture(fixture_id)
            report["requests_attempted"] += 1
            fixture_data = detail.get("data")
            report["fixture_detail_status"] = "returned"
            report["fixture_detail_shape"] = payload_shape(fixture_data)

            home_team_id = extract_id(
                fixture_data if isinstance(fixture_data, dict) else {},
                ("home_team_id", "home_id"),
                ("home_team", "home"),
            )
            if home_team_id is None:
                home_team_id = extract_id(
                    fixtures[0], ("home_team_id", "home_id"), ("home_team", "home")
                )
            if home_team_id is not None:
                team = client.get_team(home_team_id)
                report["requests_attempted"] += 1
                team_data = team.get("data")
                report["team_detail_status"] = "returned"
                report["team_detail_shape"] = payload_shape(team_data)
                players, player_path = find_records(
                    team_data, ("players", "squad", "roster", "team_players")
                )
                report["team_player_collection_path"] = player_path
                report["team_player_count_sampled"] = len(players or [])
                if players:
                    player_id = extract_id(players[0], ("id", "player_id"))
                    if player_id is not None:
                        player = client.get_player(player_id)
                        report["requests_attempted"] += 1
                        report["player_detail_status"] = "returned"
                        report["player_detail_shape"] = payload_shape(player.get("data"))
                    else:
                        report["player_detail_status"] = "skipped_no_provider_player_id"
                else:
                    report["player_detail_status"] = "skipped_no_player_collection"
            else:
                report["team_detail_status"] = "skipped_no_provider_team_id"
                report["player_detail_status"] = "skipped_no_provider_team_id"

            report["status"] = "pass"
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        report["error"] = str(exc)[:180]
    return report


def main() -> int:
    report = run_audit()
    serialized = json.dumps(report, indent=2)
    Path("openscores-data-shape-audit.json").write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    try:
        with open(__import__("os").environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write("## OpenScores read-only data-shape audit\n\n")
            for key in (
                "status", "requests_attempted", "league_count_sampled",
                "season_count_sampled", "fixture_count_sampled",
                "fixture_detail_status", "team_detail_status",
                "player_detail_status", "team_player_count_sampled",
            ):
                summary.write(f"- {key}: {report.get(key)}\n")
            summary.write("- No raw provider values published; no database or prediction-ledger writes.\n")
    except KeyError:
        pass
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
