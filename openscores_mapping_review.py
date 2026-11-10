"""Read-only exact-identity candidate review for OpenScores crosswalks.

This module proposes candidate links only. It never writes provider_entity_links,
canonical football tables, prediction inputs, or the prediction ledger.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from football_repository import ensure_football_repository
from openscores_observation_store import ensure_observation_store
from provider_data_storage import _connect


def _key(value: Any) -> str:
    """Case/whitespace-normalized exact label; punctuation and words are preserved."""
    return re.sub(r"\\s+", " ", str(value or "").strip()).casefold()


def exact_name_candidates(
    provider_entities: list[dict[str, Any]],
    canonical_entities: list[dict[str, Any]],
    *,
    require_country: bool = False,
) -> list[dict[str, Any]]:
    """Return exact, unique suggestions; never fuzzy-match or auto-approve."""
    output = []
    for entity in provider_entities:
        name = str(entity.get("name") or "").strip()
        name_key = _key(name)
        country = str(entity.get("country") or "").strip()
        candidates = []
        if name_key:
            for canonical in canonical_entities:
                if _key(canonical.get("name")) != name_key:
                    continue
                canonical_country = str(canonical.get("country") or "").strip()
                if country and canonical_country and _key(country) != _key(canonical_country):
                    continue
                if require_country and country and not canonical_country:
                    continue
                candidates.append(canonical)
        if len(candidates) == 1:
            status = "unique_exact_candidate"
        elif len(candidates) > 1:
            status = "ambiguous_exact_candidates"
        else:
            status = "no_exact_candidate"
        output.append({
            **entity,
            "candidate_status": status,
            "candidate_count": len(candidates),
            "candidates": [
                {
                    "canonical_entity_id": str(candidate.get("id")),
                    "name": candidate.get("name"),
                    "country": candidate.get("country"),
                }
                for candidate in candidates
            ],
            "auto_linked": False,
        })
    return output


def run_review(database_url: str | None = None) -> dict[str, Any]:
    db_url = (database_url or os.getenv("PROVIDER_DATABASE_URL", "")).strip()
    if not db_url:
        raise ValueError("PROVIDER_DATABASE_URL is required")
    ensure_football_repository(db_url)
    ensure_observation_store(db_url)

    with _connect(db_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT o.provider_league_id,
                       COALESCE(r.competition_name, '') AS name,
                       COALESCE(r.country, '') AS country
                FROM provider_fixture_observations o
                LEFT JOIN provider_competition_registry r
                  ON r.provider = 'openscores'
                 AND r.provider_competition_id = o.provider_league_id
                 AND r.provider_season_id = o.provider_season_id
                WHERE o.provider = 'openscores'
                ORDER BY o.provider_league_id
                """
            )
            provider_leagues = [
                {"id": row[0], "name": row[1], "country": row[2]}
                for row in cursor.fetchall()
            ]
            cursor.execute(
                """
                SELECT DISTINCT provider_season_id, provider_league_id,
                       COALESCE(r.season_name, '') AS name
                FROM provider_fixture_observations o
                LEFT JOIN provider_competition_registry r
                  ON r.provider = 'openscores'
                 AND r.provider_competition_id = o.provider_league_id
                 AND r.provider_season_id = o.provider_season_id
                WHERE o.provider = 'openscores'
                ORDER BY provider_league_id, provider_season_id
                """
            )
            provider_seasons = [
                {"id": row[0], "league_id": row[1], "name": row[2]}
                for row in cursor.fetchall()
            ]
            cursor.execute(
                """
                SELECT provider_home_team_id, home_team_name
                FROM provider_fixture_observations
                WHERE provider = 'openscores'
                UNION
                SELECT provider_away_team_id, away_team_name
                FROM provider_fixture_observations
                WHERE provider = 'openscores'
                ORDER BY 1
                """
            )
            provider_teams = [
                {"id": row[0], "name": row[1], "country": ""}
                for row in cursor.fetchall()
            ]
            cursor.execute("SELECT league_id, name, country FROM football_leagues ORDER BY name, league_id")
            canonical_leagues = [
                {"id": row[0], "name": row[1], "country": row[2] or ""}
                for row in cursor.fetchall()
            ]
            cursor.execute(
                "SELECT season_id, league_id, COALESCE(name, '') FROM football_seasons ORDER BY league_id, season_id"
            )
            canonical_seasons = [
                {"id": row[0], "league_id": row[1], "name": row[2]}
                for row in cursor.fetchall()
            ]
            cursor.execute("SELECT team_id, name, country FROM football_teams ORDER BY name, team_id")
            canonical_teams = [
                {"id": row[0], "name": row[1], "country": row[2] or ""}
                for row in cursor.fetchall()
            ]
            cursor.execute(
                """
                SELECT entity_type, provider_entity_id, canonical_entity_id
                FROM provider_entity_links WHERE provider = 'openscores'
                ORDER BY entity_type, provider_entity_id
                """
            )
            existing_links = [
                {"entity_type": row[0], "provider_entity_id": row[1],
                 "canonical_entity_id": row[2]}
                for row in cursor.fetchall()
            ]

    league_candidates = exact_name_candidates(
        provider_leagues, canonical_leagues, require_country=True
    )
    team_candidates = exact_name_candidates(provider_teams, canonical_teams)
    season_candidates = []
    for season in provider_seasons:
        league = next(
            (item for item in league_candidates if str(item["id"]) == str(season["league_id"])),
            None,
        )
        scoped = [
            item for item in canonical_seasons
            if league and item["league_id"] == (
                league["candidates"][0]["canonical_entity_id"]
                if league["candidate_status"] == "unique_exact_candidate" else None
            )
        ]
        candidates = [
            item for item in scoped if _key(item["name"]) == _key(season["name"])
            and _key(season["name"])
        ]
        season_candidates.append({
            **season,
            "candidate_status": (
                "unique_exact_candidate" if len(candidates) == 1
                else "ambiguous_exact_candidates" if len(candidates) > 1
                else "no_exact_candidate"
            ),
            "candidate_count": len(candidates),
            "candidates": [
                {"canonical_entity_id": str(item["id"]), "name": item["name"]}
                for item in candidates
            ],
            "auto_linked": False,
        })

    report = {
        "operation": "openscores_mapping_review",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "provider_observations_read_only": True,
        "canonical_records_modified": False,
        "crosswalk_rows_written": 0,
        "prediction_ledger_touched": False,
        "existing_openscores_links": len(existing_links),
        "existing_links": existing_links,
        "league_candidates": league_candidates,
        "season_candidates": season_candidates,
        "team_candidates": team_candidates,
        "summary": {
            "leagues": len(league_candidates),
            "league_unique_exact": sum(x["candidate_status"] == "unique_exact_candidate" for x in league_candidates),
            "seasons": len(season_candidates),
            "season_unique_exact": sum(x["candidate_status"] == "unique_exact_candidate" for x in season_candidates),
            "teams": len(team_candidates),
            "team_unique_exact": sum(x["candidate_status"] == "unique_exact_candidate" for x in team_candidates),
        },
        "review_rule": (
            "Candidates are suggestions only. A separate explicit approval step is required "
            "before any provider_entity_links row can be created."
        ),
    }
    return report


def main() -> int:
    report = run_review()
    serialized = json.dumps(report, indent=2, default=str)
    Path("openscores-mapping-review-report.json").write_text(
        serialized + "\\n", encoding="utf-8"
    )
    print(serialized)
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("## OpenScores mapping candidate review (read-only)\\n\\n")
            summary.write(f"- Summary: {report['summary']}\\n")
            summary.write("- Crosswalk rows written: 0\\n")
            summary.write("- Prediction ledger touched: false\\n")
            summary.write("\\nNo candidate is auto-approved.\\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
