"""Read-only OpenScores-to-Highlightly crosswalk audit from existing cached payloads.

Uses only already archived Highlightly responses in CockroachDB. It does not
make provider API requests or write canonical entities, provider links,
fixtures, prediction inputs, or the prediction ledger.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from provider_data_storage import _connect

TARGETS = (
    {"openscores_league_id": "4", "openscores_season_id": "4", "name": "Bundesliga", "country": "Germany", "season": 2025, "highlightly_league_id": "67162"},
    {"openscores_league_id": "6", "openscores_season_id": "6", "name": "Ligue 1", "country": "France", "season": 2025, "highlightly_league_id": "52695"},
    {"openscores_league_id": "7", "openscores_season_id": "7", "name": "World Cup", "country": "World", "season": 2026, "highlightly_league_id": "1635"},
)

TEAM_ALIASES = {
    "st pauli": ("fc st pauli",),
    "stuttgart": ("vfb stuttgart",),
    "dortmund": ("borussia dortmund",),
    "fc koln": ("1 fc koln",),
    "heidenheim": ("1 fc heidenheim",),
    "mainz": ("1 fsv mainz 05",),
    "b monchengladbach": ("borussia monchengladbach",),
    "augsburg": ("fc augsburg",),
    "union berlin": ("1 fc union berlin",),
    "bayern munich": ("fc bayern munchen",),
    "hoffenheim": ("tsg hoffenheim",),
    "freiburg": ("sc freiburg",),
    "wolfsburg": ("vfl wolfsburg",),
    "werder bremen": ("sv werder bremen",),
    "brest": ("stade brestois 29",),
    "psg": ("paris saint germain",),
    "lyon": ("olympique lyonnais",),
    "marseille": ("olympique de marseille",),
    "monaco": ("as monaco",),
    "lille": ("losc lille",),
    "nice": ("ogc nice",),
    "nantes": ("fc nantes",),
    "lens": ("rc lens",),
    "toulouse": ("toulouse fc",),
    "auxerre": ("aj auxerre",),
    "angers": ("angers sco",),
    "strasbourg": ("rc strasbourg alsace",),
    "rennes": ("stade rennais fc",),
    "lorient": ("fc lorient",),
    "le havre": ("le havre ac",),
    "metz": ("fc metz",),
    "bosnia and herzegovina": ("bosnia herzegovina",),
    "d r congo": ("congo dr", "dr congo"),
    "ivory coast": ("cote d ivoire",),
    "czech republic": ("czechia",),
    "usa": ("united states",),
    "turkey": ("turkiye",),
    "cape verde": ("cabo verde",),
    "iran": ("ir iran",),
    "south korea": ("korea republic",),
}


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("&", " and ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def _dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        if isinstance(data, dict):
            return [data]
    return []


def _load_cached_matches(database_url: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    matches: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT request_params, payload, retrieved_at::text, expires_at::text
                FROM provider_api_snapshots
                WHERE provider = 'highlightly'
                  AND resource_type = '_get_response'
                ORDER BY retrieved_at DESC
                LIMIT 2000
                """
            )
            for request_params, payload, retrieved_at, expires_at in cursor.fetchall():
                params = request_params if isinstance(request_params, Mapping) else {}
                args = params.get("args") or []
                kwargs = params.get("kwargs") or {}
                if not args or str(args[0]).strip("/") != "matches":
                    continue
                query = args[1] if len(args) > 1 and isinstance(args[1], Mapping) else kwargs
                if not isinstance(query, Mapping):
                    continue
                for row in _rows(payload):
                    matches.append(row)
                metadata.append({
                    "leagueName": query.get("leagueName"),
                    "season": query.get("season"),
                    "leagueId": query.get("leagueId"),
                    "retrieved_at": retrieved_at,
                    "expires_at": expires_at,
                    "row_count": len(_rows(payload)),
                })
    return matches, metadata


def _load_observations(database_url: str, target: Mapping[str, Any]) -> list[dict[str, Any]]:
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT provider_fixture_id, provider_home_team_id, provider_away_team_id,
                       home_team_name, away_team_name, kickoff_utc::text
                FROM provider_fixture_observations
                WHERE provider = 'openscores'
                  AND provider_league_id = %s AND provider_season_id = %s
                ORDER BY kickoff_utc, provider_fixture_id
                """,
                (target["openscores_league_id"], target["openscores_season_id"]),
            )
            return [
                {"fixture_id": str(r[0]), "home_id": str(r[1]), "away_id": str(r[2]),
                 "home_name": str(r[3]), "away_name": str(r[4]), "kickoff": str(r[5])}
                for r in cursor.fetchall()
            ]


def _team_candidate(names: set[str], team_index: Mapping[str, dict[str, str]]) -> dict[str, Any]:
    exact = {
        str(team_index[_norm(name)]["id"])
        for name in names if _norm(name) in team_index
    }
    candidates = exact
    method = "exact_normalized_name"
    if not candidates:
        candidates = set()
        method = "curated_alias"
        for name in names:
            for alias in TEAM_ALIASES.get(_norm(name), ()):
                if _norm(alias) in team_index:
                    candidates.add(str(team_index[_norm(alias)]["id"]))
    if len(candidates) == 1:
        target_id = next(iter(candidates))
        target = next(row for row in team_index.values() if str(row["id"]) == target_id)
        return {"status": "unique_candidate", "highlightly_team_id": target_id,
                "highlightly_team_name": target["name"], "method": method}
    return {"status": "ambiguous" if candidates else "no_candidate",
            "candidate_ids": sorted(candidates), "method": method}


def _audit_target(
    database_url: str, cached_matches: list[dict[str, Any]],
    cache_metadata: list[dict[str, Any]], target: Mapping[str, Any],
) -> dict[str, Any]:
    fixtures = []
    for row in cached_matches:
        league = row.get("league") if isinstance(row.get("league"), Mapping) else {}
        league_id = league.get("id") or row.get("leagueId") or row.get("league_id")
        season = league.get("season") if league.get("season") is not None else row.get("season")
        try:
            season_year = int(season.get("year") if isinstance(season, Mapping) else season)
        except (TypeError, ValueError):
            season_year = None
        if str(league_id) == str(target["highlightly_league_id"]) and season_year == int(target["season"]):
            if row.get("date") and (row.get("homeTeam") or {}).get("id") and (row.get("awayTeam") or {}).get("id"):
                fixtures.append(row)

    observations = _load_observations(database_url, target)
    if not fixtures:
        return {
            "competition": target["name"], "country": target["country"], "season": target["season"],
            "highlightly_league_id": target["highlightly_league_id"],
            "openscores_observations": len(observations), "cached_highlightly_fixtures": 0,
            "status": "no_cached_highlightly_fixtures",
        }

    team_index: dict[str, dict[str, str]] = {}
    name_ids: dict[str, set[str]] = defaultdict(set)
    for fixture in fixtures:
        for side in ("homeTeam", "awayTeam"):
            team = fixture.get(side) or {}
            if team.get("id") is None or not team.get("name"):
                continue
            key = _norm(team["name"])
            name_ids[key].add(str(team["id"]))
            team_index[key] = {"id": str(team["id"]), "name": str(team["name"])}
    for key, ids in name_ids.items():
        if len(ids) > 1:
            team_index.pop(key, None)

    source_names: dict[str, set[str]] = defaultdict(set)
    for obs in observations:
        source_names[obs["home_id"]].add(obs["home_name"])
        source_names[obs["away_id"]].add(obs["away_name"])
    mappings = {pid: _team_candidate(names, team_index) for pid, names in source_names.items()}
    reverse: dict[str, list[str]] = defaultdict(list)
    for pid, mapping in mappings.items():
        if mapping["status"] == "unique_candidate":
            reverse[mapping["highlightly_team_id"]].append(pid)
    collisions = {hid: pids for hid, pids in reverse.items() if len(pids) > 1}
    for hid, pids in collisions.items():
        for pid in pids:
            mappings[pid]["status"] = "ambiguous_reverse_collision"

    fixture_index: dict[tuple[str, str], list[tuple[dict[str, Any], datetime]]] = defaultdict(list)
    for fixture in fixtures:
        home_id = str((fixture.get("homeTeam") or {}).get("id"))
        away_id = str((fixture.get("awayTeam") or {}).get("id"))
        kickoff = _dt(fixture.get("date"))
        if kickoff:
            fixture_index[(home_id, away_id)].append((fixture, kickoff))

    matched = no_match = ambiguous = blocked = 0
    rows = []
    for obs in observations:
        home = mappings.get(obs["home_id"], {"status": "no_candidate"})
        away = mappings.get(obs["away_id"], {"status": "no_candidate"})
        if home.get("status") != "unique_candidate" or away.get("status") != "unique_candidate":
            blocked += 1
            rows.append({"openscores_fixture_id": obs["fixture_id"], "status": "blocked_team_mapping",
                         "home": home, "away": away})
            continue
        source_kickoff = _dt(obs["kickoff"])
        candidates = []
        if source_kickoff:
            for fixture, kickoff in fixture_index.get((
                home["highlightly_team_id"], away["highlightly_team_id"]
            ), []):
                if abs((kickoff - source_kickoff).total_seconds()) <= 300:
                    candidates.append(fixture)
        if len(candidates) == 1:
            matched += 1
            rows.append({"openscores_fixture_id": obs["fixture_id"], "status": "unique_fixture_match",
                         "highlightly_fixture_id": str(candidates[0].get("id"))})
        elif len(candidates) > 1:
            ambiguous += 1
            rows.append({"openscores_fixture_id": obs["fixture_id"], "status": "ambiguous_fixture_match",
                         "highlightly_fixture_ids": [str(x.get("id")) for x in candidates]})
        else:
            no_match += 1
            rows.append({"openscores_fixture_id": obs["fixture_id"], "status": "no_fixture_match"})

    relevant_cache = [
        row for row in cache_metadata
        if _norm(row.get("leagueName")) == _norm(target["name"])
        and str(row.get("season")) == str(target["season"])
    ]
    return {
        "competition": target["name"], "country": target["country"], "season": target["season"],
        "openscores_league_id": target["openscores_league_id"],
        "openscores_season_id": target["openscores_season_id"],
        "highlightly_league_id": target["highlightly_league_id"],
        "cached_highlightly_fixtures": len(fixtures),
        "openscores_observations": len(observations),
        "observed_teams": len(source_names),
        "unique_team_mappings": sum(1 for x in mappings.values() if x["status"] == "unique_candidate"),
        "unmapped_or_ambiguous_teams": [
            {"openscores_team_id": pid, "names": sorted(source_names[pid]), **mapping}
            for pid, mapping in mappings.items() if mapping["status"] != "unique_candidate"
        ],
        "team_mapping_collisions": collisions,
        "fixture_matches": matched, "no_fixture_match": no_match,
        "ambiguous_fixture_matches": ambiguous, "observations_blocked_by_team_mapping": blocked,
        "fixture_match_rows": rows,
        "cache_requests": relevant_cache,
        "status": "pass" if matched == len(observations) and not ambiguous and not blocked and not collisions else "partial",
    }


def run_audit() -> dict[str, Any]:
    database_url = os.getenv("PROVIDER_DATABASE_URL", "").strip()
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required")
    cached_matches, cache_metadata = _load_cached_matches(database_url)
    report: dict[str, Any] = {
        "operation": "openscores_highlightly_cached_identity_audit",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True, "canonical_tables_modified": False,
        "provider_entity_links_written": 0, "prediction_ledger_touched": False,
        "cached_highlightly_match_rows": len(cached_matches),
        "cached_highlightly_match_requests": len(cache_metadata),
        "competitions": [],
    }
    for target in TARGETS:
        report["competitions"].append(_audit_target(
            database_url, cached_matches, cache_metadata, target
        ))
    report["observations_checked"] = sum(int(x.get("openscores_observations") or 0) for x in report["competitions"])
    report["fixture_matches"] = sum(int(x.get("fixture_matches") or 0) for x in report["competitions"])
    report["ambiguous_fixture_matches"] = sum(int(x.get("ambiguous_fixture_matches") or 0) for x in report["competitions"])
    report["pending_team_mapping_observations"] = sum(int(x.get("observations_blocked_by_team_mapping") or 0) for x in report["competitions"])
    report["status"] = "pass" if (
        report["observations_checked"] == report["fixture_matches"]
        and report["ambiguous_fixture_matches"] == 0
        and report["pending_team_mapping_observations"] == 0
    ) else "partial"
    return report


def main() -> int:
    report = run_audit()
    Path("openscores-highlightly-cached-identity-report.json").write_text(
        json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, default=str))
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("## OpenScores ↔ Highlightly cached identity audit\n\n")
            summary.write(f"- Status: {report['status']}\n")
            summary.write(f"- Cached Highlightly match rows: {report['cached_highlightly_match_rows']}\n")
            summary.write(f"- OpenScores observations checked: {report['observations_checked']}\n")
            summary.write(f"- Unique fixture matches: {report['fixture_matches']}\n")
            summary.write(f"- Ambiguous fixture matches: {report['ambiguous_fixture_matches']}\n")
            summary.write("- Read-only: yes; no canonical or prediction writes\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
