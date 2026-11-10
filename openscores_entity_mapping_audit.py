"""Read-only candidate audit for explicit OpenScores-to-canonical entity mappings.

Name matches are suggestions for human review only. This module never writes
provider_entity_links, canonical football tables, fixtures, or prediction data.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from openscores import OpenScoresClient
from provider_data_storage import _connect


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("&", " and ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def _records(value: Any, preferred: tuple[str, ...], depth: int = 0):
    if depth > 6:
        return None
    if isinstance(value, list):
        return value if all(isinstance(item, dict) for item in value) else None
    if isinstance(value, dict):
        for key in preferred:
            if key in value:
                found = _records(value[key], preferred, depth + 1)
                if found is not None:
                    return found
        for key, child in value.items():
            if key not in preferred and isinstance(child, (dict, list)):
                found = _records(child, preferred, depth + 1)
                if found is not None:
                    return found
    return None


def _country(value: Any) -> str:
    if isinstance(value, Mapping):
        value = value.get("name") or value.get("displayName") or value.get("country_name") or ""
    return str(value or "")


def _league_country(league: Mapping[str, Any]) -> str:
    for key in ("country", "country_name", "countryName", "area", "region"):
        value = _country(league.get(key))
        if value:
            return value
    return ""


def _key_inventory(payloads: list[Any], *, max_depth: int = 3) -> list[str]:
    """Return JSON field paths only; never expose raw provider payload values."""
    paths: set[str] = set()

    def visit(value: Any, prefix: str = "", depth: int = 0) -> None:
        if depth >= max_depth:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                path = f"{prefix}.{key}" if prefix else str(key)
                paths.add(path)
                visit(child, path, depth + 1)
        elif isinstance(value, list):
            for child in value[:5]:
                visit(child, prefix, depth + 1)

    for payload in payloads:
        visit(payload)
    return sorted(paths)


def _source_id_keys(payloads: list[Any]) -> list[str]:
    keys: set[str] = set()
    for payload in payloads:
        if not isinstance(payload, Mapping):
            continue
        source_ids = payload.get("source_ids")
        if isinstance(source_ids, Mapping):
            keys.update(str(key) for key in source_ids)
    return sorted(keys)



def _source_id_summary(records: list[Any]) -> dict[str, Any]:
    """Summarize explicit external-ID namespaces without treating names as IDs."""
    counts: dict[str, int] = {}
    examples: dict[str, list[str]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            continue
        for namespace, value in record.items():
            key = str(namespace).strip().casefold()
            if not key or value in (None, ""):
                continue
            counts[key] = counts.get(key, 0) + 1
            sample = str(value)
            if sample not in examples.setdefault(key, []) and len(examples[key]) < 5:
                examples[key].append(sample)
    return {
        "namespace_counts": dict(sorted(counts.items())),
        "examples": dict(sorted(examples.items())),
    }


def _external_id_evidence(
    observation_rows: list[tuple[Any, Any]],
    leagues: list[Mapping[str, Any]],
    seasons_by_league: Mapping[str, list[Mapping[str, Any]]],
) -> dict[str, Any]:
    fixture_ids = []
    team_ids = []
    for source_ids, raw_payload in observation_rows:
        if isinstance(source_ids, Mapping):
            fixture_ids.append(source_ids)
        if isinstance(raw_payload, Mapping):
            for key in ("home_team", "away_team"):
                team = raw_payload.get(key)
                if not isinstance(team, Mapping):
                    continue
                ids = team.get("source_ids") or team.get("external_ids")
                if isinstance(ids, Mapping):
                    team_ids.append(ids)
    league_ids = [
        item.get("source_ids") or item.get("external_ids")
        for item in leagues if isinstance(item, Mapping)
    ]
    season_ids = [
        season.get("source_ids") or season.get("external_ids")
        for rows in seasons_by_league.values() for season in rows
        if isinstance(season, Mapping)
    ]
    return {
        "fixture_external_ids": _source_id_summary(fixture_ids),
        "team_external_ids": _source_id_summary(team_ids),
        "league_external_ids": _source_id_summary([x for x in league_ids if isinstance(x, Mapping)]),
        "season_external_ids": _source_id_summary([x for x in season_ids if isinstance(x, Mapping)]),
        "matching_policy": (
            "Evidence only. Shared provider IDs must be checked against canonical provider links "
            "before any crosswalk can be approved."
        ),
    }

def _unique_name_candidates(source: Mapping[str, Any], canonical: list[Mapping[str, Any]],
                            *, require_country: bool = False) -> dict[str, Any]:
    source_name = _norm(source.get("name"))
    source_country = _norm(_country(source.get("country")) )
    if not source_name:
        return {"status": "insufficient_source_identity", "candidates": []}
    matches = []
    for row in canonical:
        if _norm(row.get("name")) != source_name:
            continue
        target_country = _norm(row.get("country"))
        if source_country and target_country and source_country != target_country:
            continue
        matches.append({
            "canonical_id": str(row.get("id")),
            "name": row.get("name"),
            "country": row.get("country"),
            "source_provider": row.get("source_provider"),
        })
    if len(matches) == 1:
        country_missing = require_country and (not source_country or not _norm(matches[0].get("country")))
        status = (
            "unique_name_candidate_requires_country_review"
            if country_missing else "unique_name_candidate_requires_review"
        )
    elif len(matches) > 1:
        status = "ambiguous_name_candidates"
    else:
        status = "no_name_candidate"
    return {"status": status, "candidates": matches}


def _season_candidates(source: Mapping[str, Any], canonical: list[Mapping[str, Any]],
                       canonical_league_id: str | None) -> dict[str, Any]:
    if not canonical_league_id:
        return {"status": "blocked_until_league_mapping", "candidates": []}
    source_name = _norm(source.get("name"))
    source_start = str(source.get("starting_at") or source.get("start_date") or "")[:10]
    source_end = str(source.get("ending_at") or source.get("end_date") or "")[:10]
    matches = []
    for row in canonical:
        if str(row.get("league_id")) != canonical_league_id:
            continue
        target_name = _norm(row.get("name"))
        target_start = str(row.get("start_date") or "")[:10]
        target_end = str(row.get("end_date") or "")[:10]
        exact_name = bool(source_name and target_name and source_name == target_name)
        exact_dates = bool(source_start and source_end and source_start == target_start and source_end == target_end)
        if exact_name or exact_dates:
            matches.append({
                "canonical_id": str(row.get("id")),
                "name": row.get("name"),
                "start_date": row.get("start_date"),
                "end_date": row.get("end_date"),
                "match_basis": "exact_name" if exact_name else "exact_start_and_end_dates",
            })
    status = ("unique_candidate_requires_review" if len(matches) == 1 else
              "ambiguous_candidates" if len(matches) > 1 else "no_candidate")
    return {"status": status, "candidates": matches}


def build_entity_mapping_candidates(
    *, leagues: list[Mapping[str, Any]], seasons_by_league: Mapping[str, list[Mapping[str, Any]]],
    observed_teams: list[Mapping[str, Any]], canonical_leagues: list[Mapping[str, Any]],
    canonical_seasons: list[Mapping[str, Any]], canonical_teams: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build conservative review candidates; never treat name similarity as proof."""
    league_rows = []
    season_rows = []
    for league in leagues:
        source_id = str(league.get("id") or league.get("league_id") or "")
        candidate = _unique_name_candidates(league, canonical_leagues, require_country=True)
        canonical_league_id = (
            candidate["candidates"][0]["canonical_id"]
            if candidate["status"] == "unique_name_candidate_requires_review" else None
        )
        league_rows.append({
            "provider_entity_id": source_id,
            "name": league.get("name"),
            "country": _league_country(league),
            **candidate,
            "automatic_mapping_created": False,
        })
        for season in seasons_by_league.get(source_id, []):
            season_id = str(season.get("id") or season.get("season_id") or "")
            season_candidate = _season_candidates(season, canonical_seasons, canonical_league_id)
            season_rows.append({
                "provider_entity_id": season_id,
                "provider_league_id": source_id,
                "name": season.get("name") or season.get("starting_at"),
                **season_candidate,
                "automatic_mapping_created": False,
            })

    team_rows = []
    for team in observed_teams:
        candidate = _unique_name_candidates(team, canonical_teams)
        team_rows.append({
            "provider_entity_id": str(team.get("provider_team_id")),
            "name": team.get("name"),
            "country": team.get("country"),
            "observation_count": int(team.get("observation_count") or 0),
            **candidate,
            "automatic_mapping_created": False,
        })
    return {
        "leagues": league_rows,
        "seasons": season_rows,
        "teams": team_rows,
        "policy": "Candidates are for review only; no entity links are written from names.",
    }


def run_audit(*, client_factory=OpenScoresClient, database_url: str | None = None) -> dict[str, Any]:
    db_url = (database_url or os.getenv("PROVIDER_DATABASE_URL", "")).strip()
    if not db_url:
        raise ValueError("PROVIDER_DATABASE_URL is required")
    report: dict[str, Any] = {
        "operation": "openscores_entity_mapping_audit",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "fail",
        "read_only": True,
        "entity_links_written": 0,
        "canonical_tables_modified": False,
        "prediction_ledger_touched": False,
    }
    with client_factory() as client:
        league_result = client.list_leagues()
        leagues, _ = client._league_collection(league_result.get("data"))
        if leagues is None:
            raise RuntimeError("OpenScores league catalogue could not be normalized")
        seasons_by_league: dict[str, list[Mapping[str, Any]]] = {}
        for league in leagues:
            league_id = str(league.get("id") or league.get("league_id") or "")
            if not league_id:
                continue
            season_result = client.list_seasons(league_id)
            seasons_by_league[league_id] = _records(
                season_result.get("data"), ("seasons", "items", "results", "data", "records")
            ) or []

    with _connect(db_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT league_id, name, country, source_provider, raw_payload FROM football_leagues ORDER BY name, league_id")
            canonical_leagues = [
                {"id": row[0], "name": row[1], "country": row[2] or _league_country(row[4] or {}),
                 "source_provider": row[3], "raw_payload": row[4] or {}}
                for row in cursor.fetchall()
            ]
            cursor.execute("SELECT season_id, league_id, name, start_date::text, end_date::text FROM football_seasons ORDER BY league_id, season_id")
            canonical_seasons = [
                {"id": row[0], "league_id": row[1], "name": row[2], "start_date": row[3], "end_date": row[4]}
                for row in cursor.fetchall()
            ]
            cursor.execute("SELECT team_id, name, country, source_provider, raw_payload FROM football_teams ORDER BY name, team_id")
            canonical_teams = [
                {"id": row[0], "name": row[1], "country": row[2], "source_provider": row[3],
                 "raw_payload": row[4] or {}}
                for row in cursor.fetchall()
            ]
            cursor.execute("""
                SELECT provider_home_team_id, home_team_name, COUNT(*)
                FROM provider_fixture_observations
                WHERE provider = 'openscores'
                GROUP BY provider_home_team_id, home_team_name
                UNION ALL
                SELECT provider_away_team_id, away_team_name, COUNT(*)
                FROM provider_fixture_observations
                WHERE provider = 'openscores'
                GROUP BY provider_away_team_id, away_team_name
            """)
            team_counts: dict[str, dict[str, Any]] = {}
            for team_id, team_name, count in cursor.fetchall():
                key = str(team_id)
                item = team_counts.setdefault(key, {
                    "provider_team_id": key, "name": team_name, "observation_count": 0
                })
                item["observation_count"] += int(count or 0)
            cursor.execute("""
                SELECT COUNT(*), COUNT(DISTINCT provider_league_id),
                       COUNT(DISTINCT provider_season_id), COUNT(DISTINCT provider_home_team_id)
                FROM provider_fixture_observations WHERE provider = 'openscores'
            """)
            observation_summary = cursor.fetchone()
            cursor.execute("""
                SELECT raw_payload, source_ids
                FROM provider_fixture_observations
                WHERE provider = 'openscores'
                ORDER BY kickoff_utc
                LIMIT 100
            """)
            openscores_payload_rows = cursor.fetchall()
            cursor.execute("""
                SELECT raw_payload
                FROM football_fixtures
                ORDER BY starting_at DESC
                LIMIT 100
            """)
            canonical_fixture_payloads = [row[0] or {} for row in cursor.fetchall()]

    candidates = build_entity_mapping_candidates(
        leagues=leagues,
        seasons_by_league=seasons_by_league,
        observed_teams=list(team_counts.values()),
        canonical_leagues=canonical_leagues,
        canonical_seasons=canonical_seasons,
        canonical_teams=canonical_teams,
    )
    # A provider team may appear as home in one query and away in another;
    # merge above by ID. The counts are observation appearances, not unique fixtures.
    report.update({
        "status": "pass",
        "observations": {
            "fixture_observations": int(observation_summary[0] or 0),
            "distinct_leagues": int(observation_summary[1] or 0),
            "distinct_seasons": int(observation_summary[2] or 0),
            "distinct_home_teams": int(observation_summary[3] or 0),
            "distinct_teams_seen_home_or_away": len(team_counts),
        },
        "canonical_entity_counts": {
            "leagues": len(canonical_leagues),
            "seasons": len(canonical_seasons),
            "teams": len(canonical_teams),
        },
        "canonical_catalogue": {
            "leagues": [
                {key: row.get(key) for key in ("id", "name", "country", "source_provider")}
                for row in canonical_leagues
            ],
            "seasons": [
                {key: row.get(key) for key in ("id", "league_id", "name", "start_date", "end_date")}
                for row in canonical_seasons
            ],
        },
        "source_identity_evidence": {
            "openscores_league_fields": {
                str(league.get("id") or league.get("league_id") or ""): sorted(str(key) for key in league)
                for league in leagues
            },
            "openscores_fixture_payload_field_paths": _key_inventory(
                [row[0] or {} for row in openscores_payload_rows]
            ),
            "openscores_source_id_keys": sorted({
                str(key) for row in openscores_payload_rows
                if isinstance(row[1], Mapping) for key in row[1]
            }),
            "canonical_fixture_payload_field_paths": _key_inventory(canonical_fixture_payloads),
            "canonical_team_payload_field_paths": _key_inventory(
                [row.get("raw_payload") or {} for row in canonical_teams]
            ),
        },
        "candidates": candidates,
        "external_id_evidence": _external_id_evidence(
            source_id_observations, leagues, seasons_by_league
        ),
        "summary": {
            "league_unique_candidates": sum(x["status"] == "unique_name_candidate_requires_review" for x in candidates["leagues"]),
            "league_country_review_candidates": sum(x["status"] == "unique_name_candidate_requires_country_review" for x in candidates["leagues"]),
            "season_unique_candidates": sum(x["status"] == "unique_candidate_requires_review" for x in candidates["seasons"]),
            "team_unique_candidates": sum(x["status"] == "unique_name_candidate_requires_review" for x in candidates["teams"]),
            "league_ambiguous": sum(x["status"] == "ambiguous_name_candidates" for x in candidates["leagues"]),
            "team_ambiguous": sum(x["status"] == "ambiguous_name_candidates" for x in candidates["teams"]),
        },
    })
    return report


def main() -> int:
    report = run_audit()
    serialized = json.dumps(report, indent=2, default=str)
    Path("openscores-entity-mapping-audit.json").write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("## OpenScores entity mapping audit (read-only)\n\n")
            summary.write(f"- Status: {report['status']}\n")
            summary.write(f"- Observations: {report['observations']['fixture_observations']}\n")
            summary.write(f"- Candidate counts: {json.dumps(report['summary'], sort_keys=True)}\n")
            summary.write("- Entity links written: 0\n- Prediction ledger touched: no\n")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
