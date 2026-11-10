"""Read-only OpenScores-to-Highlightly identity and fixture crosswalk audit.

This is a coverage-validation step only. It never writes canonical entities,
provider links, fixture rows, model inputs, or the prediction ledger.
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

from highlightly import HighlightlyClient
from provider_data_storage import _connect

TARGETS = (
    {"openscores_league_id": "4", "openscores_season_id": "4", "name": "Bundesliga", "country": "Germany", "season": 2025},
    {"openscores_league_id": "6", "openscores_season_id": "6", "name": "Ligue 1", "country": "France", "season": 2025},
    {"openscores_league_id": "7", "openscores_season_id": "7", "name": "World Cup", "country": "World", "season": 2026},
)

TEAM_ALIASES = {
    "st pauli": ("fc st pauli",),
    "stuttgart": ("vfb stuttgart",),
    "dortmund": ("borussia dortmund",),
    "fc koln": ("1 fc koln", "1 fc koln"),
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
    "bosnia and herzegovina": ("bosnia herzegovina", "bosnia and herzegovina"),
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


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _records(value: Any, preferred: tuple[str, ...], depth: int = 0) -> list[dict[str, Any]]:
    if depth > 5:
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in preferred:
            if key in value:
                found = _records(value[key], preferred, depth + 1)
                if found:
                    return found
    return []


def _highlightly_catalogue(client: HighlightlyClient) -> list[dict[str, Any]]:
    rows = []
    for page in range(10):
        batch = client.leagues(limit=100, offset=page * 100)
        rows.extend(batch)
        if len(batch) < 100:
            return rows
    raise RuntimeError("Highlightly league catalogue exceeded the safe 10-page limit")


def _league_country(row: Mapping[str, Any]) -> str:
    country = row.get("country")
    if isinstance(country, Mapping):
        return str(country.get("name") or country.get("officialName") or "")
    return str(country or row.get("countryName") or "")


def _resolve_league(catalogue: list[dict[str, Any]], target: Mapping[str, Any]) -> dict[str, Any]:
    matches = [
        row for row in catalogue
        if _norm(row.get("name")) == _norm(target["name"])
        and _norm(_league_country(row)) == _norm(target["country"])
        and row.get("id") is not None
    ]
    if len(matches) == 1:
        return {"status": "unique_exact_name_country", "league": matches[0], "candidate_count": 1}
    return {
        "status": "ambiguous_name_country" if matches else "no_exact_name_country",
        "league": None,
        "candidate_count": len(matches),
        "candidates": [
            {"id": str(row.get("id")), "name": row.get("name"), "country": _league_country(row)}
            for row in matches
        ],
    }


def _fetch_highlightly_matches(
    client: HighlightlyClient, target: Mapping[str, Any], league_id: str
) -> list[dict[str, Any]]:
    rows = []
    for page in range(10):
        batch = client.matches(
            leagueName=target["name"],
            season=int(target["season"]),
            limit=100,
            offset=page * 100,
        )
        rows.extend(batch)
        if len(batch) < 100:
            break
    else:
        raise RuntimeError("Highlightly match pagination exceeded the safe 10-page limit")

    exact = []
    for row in rows:
        league = row.get("league") if isinstance(row.get("league"), Mapping) else {}
        row_league_id = league.get("id") or row.get("leagueId") or row.get("league_id")
        season = league.get("season") if league.get("season") is not None else row.get("season")
        try:
            season_year = int(season.get("year") if isinstance(season, Mapping) else season)
        except (TypeError, ValueError):
            season_year = None
        if str(row_league_id) != str(league_id) or season_year != int(target["season"]):
            continue
        if not row.get("date") or not (row.get("homeTeam") or {}).get("id") or not (row.get("awayTeam") or {}).get("id"):
            continue
        exact.append(row)
    return exact


def _load_observations(database_url: str, target: Mapping[str, Any]) -> list[dict[str, Any]]:
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT provider_fixture_id, provider_home_team_id, provider_away_team_id,
                       home_team_name, away_team_name, kickoff_utc::text
                FROM provider_fixture_observations
                WHERE provider = 'openscores'
                  AND provider_league_id = %s
                  AND provider_season_id = %s
                ORDER BY kickoff_utc, provider_fixture_id
                """,
                (target["openscores_league_id"], target["openscores_season_id"]),
            )
            return [
                {
                    "fixture_id": str(row[0]),
                    "home_id": str(row[1]),
                    "away_id": str(row[2]),
                    "home_name": str(row[3]),
                    "away_name": str(row[4]),
                    "kickoff": str(row[5]),
                }
                for row in cursor.fetchall()
            ]


def _team_candidate(source_names: set[str], team_index: Mapping[str, dict[str, str]]) -> dict[str, Any]:
    exact_ids = {
        str(team_index[_norm(name)]["id"])
        for name in source_names
        if _norm(name) in team_index
    }
    if exact_ids:
        candidates = exact_ids
        method = "exact_normalized_name"
    else:
        candidates = set()
        for source_name in source_names:
            aliases = TEAM_ALIASES.get(_norm(source_name), ())
            for alias in aliases:
                candidate = team_index.get(_norm(alias))
                if candidate:
                    candidates.add(str(candidate["id"]))
        method = "curated_alias"
    if len(candidates) == 1:
        candidate_id = next(iter(candidates))
        candidate = next(team for team in team_index.values() if str(team["id"]) == candidate_id)
        return {
            "status": "unique_candidate",
            "highlightly_team_id": candidate_id,
            "highlightly_team_name": candidate["name"],
            "method": method,
        }
    return {
        "status": "ambiguous" if candidates else "no_candidate",
        "candidate_ids": sorted(candidates),
        "method": method,
    }


def _audit_competition(
    client: HighlightlyClient,
    database_url: str,
    catalogue: list[dict[str, Any]],
    target: Mapping[str, Any],
) -> dict[str, Any]:
    league_result = _resolve_league(catalogue, target)
    if league_result["status"] != "unique_exact_name_country":
        return {
            "competition": target["name"],
            "country": target["country"],
            "season": target["season"],
            "league_resolution": league_result,
            "status": "blocked_league_identity",
        }

    league = league_result["league"]
    league_id = str(league["id"])
    fixtures = _fetch_highlightly_matches(client, target, league_id)
    observations = _load_observations(database_url, target)

    team_index: dict[str, dict[str, str]] = {}
    team_ids_by_name: dict[str, set[str]] = defaultdict(set)
    for fixture in fixtures:
        for side in ("homeTeam", "awayTeam"):
            team = fixture.get(side) or {}
            if team.get("id") is None or not team.get("name"):
                continue
            name_key = _norm(team["name"])
            team_ids_by_name[name_key].add(str(team["id"]))
            team_index[name_key] = {"id": str(team["id"]), "name": str(team["name"])}

    # Preserve duplicate same-name teams as ambiguous instead of last-write-wins.
    for name_key, ids in team_ids_by_name.items():
        if len(ids) > 1:
            team_index.pop(name_key, None)

    source_team_names: dict[str, set[str]] = defaultdict(set)
    for obs in observations:
        source_team_names[obs["home_id"]].add(obs["home_name"])
        source_team_names[obs["away_id"]].add(obs["away_name"])

    team_mappings = {
        provider_id: _team_candidate(names, team_index)
        for provider_id, names in source_team_names.items()
    }
    reverse: dict[str, list[str]] = defaultdict(list)
    for provider_id, mapping in team_mappings.items():
        if mapping["status"] == "unique_candidate":
            reverse[mapping["highlightly_team_id"]].append(provider_id)
    collisions = {
        highlightly_id: provider_ids
        for highlightly_id, provider_ids in reverse.items()
        if len(provider_ids) > 1
    }
    for highlightly_id, provider_ids in collisions.items():
        for provider_id in provider_ids:
            team_mappings[provider_id]["status"] = "ambiguous_reverse_collision"

    fixture_index: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for fixture in fixtures:
        home_id = str((fixture.get("homeTeam") or {}).get("id") or "")
        away_id = str((fixture.get("awayTeam") or {}).get("id") or "")
        kickoff = _parse_dt(fixture.get("date"))
        if home_id and away_id and kickoff:
            fixture_index[(home_id, away_id)].append({"row": fixture, "kickoff": kickoff})

    matched = 0
    no_match = 0
    ambiguous = 0
    pending_team_mapping = 0
    match_rows = []
    for obs in observations:
        home_map = team_mappings.get(obs["home_id"], {"status": "no_candidate"})
        away_map = team_mappings.get(obs["away_id"], {"status": "no_candidate"})
        if home_map.get("status") != "unique_candidate" or away_map.get("status") != "unique_candidate":
            pending_team_mapping += 1
            match_rows.append({
                "openscores_fixture_id": obs["fixture_id"],
                "status": "blocked_team_mapping",
                "home_team_mapping": home_map,
                "away_team_mapping": away_map,
            })
            continue
        source_kickoff = _parse_dt(obs["kickoff"])
        candidates = []
        if source_kickoff:
            for item in fixture_index.get((
                home_map["highlightly_team_id"], away_map["highlightly_team_id"]
            ), []):
                delta = abs((item["kickoff"] - source_kickoff).total_seconds())
                if delta <= 300:
                    candidates.append(item["row"])
        if len(candidates) == 1:
            matched += 1
            match_rows.append({
                "openscores_fixture_id": obs["fixture_id"],
                "status": "unique_fixture_match",
                "highlightly_fixture_id": str(candidates[0].get("id")),
                "kickoff_tolerance_seconds": 300,
            })
        elif len(candidates) > 1:
            ambiguous += 1
            match_rows.append({
                "openscores_fixture_id": obs["fixture_id"],
                "status": "ambiguous_fixture_match",
                "highlightly_fixture_ids": [str(row.get("id")) for row in candidates],
            })
        else:
            no_match += 1
            match_rows.append({
                "openscores_fixture_id": obs["fixture_id"],
                "status": "no_fixture_match",
            })

    return {
        "competition": target["name"],
        "country": target["country"],
        "season": target["season"],
        "openscores_league_id": target["openscores_league_id"],
        "openscores_season_id": target["openscores_season_id"],
        "highlightly_league_id": league_id,
        "league_resolution": league_result["status"],
        "highlightly_fixtures": len(fixtures),
        "openscores_observations": len(observations),
        "observed_teams": len(source_team_names),
        "unique_team_mappings": sum(1 for x in team_mappings.values() if x["status"] == "unique_candidate"),
        "unmapped_or_ambiguous_teams": [
            {"openscores_team_id": team_id, "names": sorted(source_team_names[team_id]), **mapping}
            for team_id, mapping in team_mappings.items()
            if mapping["status"] != "unique_candidate"
        ],
        "team_mapping_collisions": collisions,
        "fixture_matches": matched,
        "no_fixture_match": no_match,
        "ambiguous_fixture_matches": ambiguous,
        "observations_blocked_by_team_mapping": pending_team_mapping,
        "fixture_match_rows": match_rows,
        "status": (
            "pass" if matched == len(observations) and not ambiguous
            and not pending_team_mapping and not collisions
            else "partial"
        ),
    }


def run_audit() -> dict[str, Any]:
    database_url = os.getenv("PROVIDER_DATABASE_URL", "").strip()
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required")
    report: dict[str, Any] = {
        "operation": "openscores_highlightly_fixture_identity_audit",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "canonical_tables_modified": False,
        "provider_entity_links_written": 0,
        "prediction_ledger_touched": False,
        "competitions": [],
    }
    with HighlightlyClient() as client:
        catalogue = _highlightly_catalogue(client)
        for target in TARGETS:
            report["competitions"].append(
                _audit_competition(client, database_url, catalogue, target)
            )
    report["observations_checked"] = sum(
        int(row.get("openscores_observations") or 0)
        for row in report["competitions"]
    )
    report["fixture_matches"] = sum(int(row.get("fixture_matches") or 0) for row in report["competitions"])
    report["ambiguous_fixture_matches"] = sum(int(row.get("ambiguous_fixture_matches") or 0) for row in report["competitions"])
    report["pending_team_mapping_observations"] = sum(
        int(row.get("observations_blocked_by_team_mapping") or 0)
        for row in report["competitions"]
    )
    report["status"] = (
        "pass" if report["observations_checked"] == report["fixture_matches"]
        and report["ambiguous_fixture_matches"] == 0
        and report["pending_team_mapping_observations"] == 0
        else "partial"
    )
    return report


def main() -> int:
    report = run_audit()
    Path("openscores-highlightly-fixture-identity-report.json").write_text(
        json.dumps(report, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, default=str))
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("## OpenScores ↔ Highlightly read-only identity audit\n\n")
            summary.write(f"- Status: {report['status']}\n")
            summary.write(f"- Observations checked: {report['observations_checked']}\n")
            summary.write(f"- Unique fixture matches: {report['fixture_matches']}\n")
            summary.write(f"- Ambiguous fixture matches: {report['ambiguous_fixture_matches']}\n")
            summary.write("- Canonical tables, provider links and prediction ledger unchanged\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
