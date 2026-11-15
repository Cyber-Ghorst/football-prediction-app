"""Stage existing Sportmonks catalogue rows as provider-native source evidence.

Only existing league, season and team catalogue rows are copied. Fixtures,
statistics, canonical entities and cross-provider links are never read or written.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from provider_data_storage import _connect
from provider_neutral_repository import split_provider_identity
from provider_source_repository import store_provider_source_bundle

REPORT = Path("provider-source-legacy-catalogue-stage-report.json")


def extract_legacy_catalogue_entities(
    leagues: list[dict[str, Any]],
    seasons: list[dict[str, Any]],
    teams: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract only provider-native catalogue identities from existing legacy rows."""
    output = []

    def provider_id(value: Any, label: str) -> str:
        identity = split_provider_identity(value, "sportmonks")
        if identity["identity_status"] != "namespaced_source_identity":
            raise ValueError(f"{label} does not have a valid Sportmonks namespace.")
        return str(identity["provider_entity_id"])

    for row in leagues:
        output.append({
            "entity_type": "competition",
            "provider_entity_id": provider_id(row.get("league_id"), "League ID"),
            "name": str(row.get("name") or "").strip(),
            "country": row.get("country"),
            "competition_type": row.get("competition_type"),
            "raw_payload": {
                "source": "existing football_leagues row",
                "legacy_repository_id": row.get("league_id"),
                "source_provider": row.get("source_provider"),
                "provider_updated_at": str(row.get("provider_updated_at") or ""),
                "raw_payload": row.get("raw_payload"),
            },
        })

    for row in seasons:
        parent_id = provider_id(row.get("league_id"), "Season parent competition ID")
        output.append({
            "entity_type": "season",
            "provider_entity_id": provider_id(row.get("season_id"), "Season ID"),
            "name": str(row.get("name") or "").strip(),
            "season_label": str(row.get("name") or "").strip(),
            "parent_competition_provider_id": parent_id,
            "start_date": row.get("start_date"),
            "end_date": row.get("end_date"),
            "raw_payload": {
                "source": "existing football_seasons row",
                "legacy_repository_id": row.get("season_id"),
                "legacy_parent_repository_id": row.get("league_id"),
                "source_provider": row.get("source_provider"),
                "raw_payload": row.get("raw_payload"),
            },
        })

    for row in teams:
        output.append({
            "entity_type": "team",
            "provider_entity_id": provider_id(row.get("team_id"), "Team ID"),
            "name": str(row.get("name") or "").strip(),
            "country": row.get("country"),
            "raw_payload": {
                "source": "existing football_teams row",
                "legacy_repository_id": row.get("team_id"),
                "source_provider": row.get("source_provider"),
                "team_scope_evidence": "not enriched by this migration",
                "raw_payload": row.get("raw_payload"),
            },
        })
    return output


def read_legacy_catalogue(database_url: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(
                """SELECT league_id, name, country, competition_type,
                          source_provider, provider_updated_at, raw_payload
                   FROM football_leagues ORDER BY league_id"""
            )
            league_columns = (
                "league_id", "name", "country", "competition_type",
                "source_provider", "provider_updated_at", "raw_payload",
            )
            leagues = [dict(zip(league_columns, row)) for row in cursor.fetchall()]
            cursor.execute(
                """SELECT season_id, league_id, name, start_date, end_date,
                          source_provider, raw_payload
                   FROM football_seasons ORDER BY season_id"""
            )
            season_columns = (
                "season_id", "league_id", "name", "start_date", "end_date",
                "source_provider", "raw_payload",
            )
            seasons = [dict(zip(season_columns, row)) for row in cursor.fetchall()]
            cursor.execute(
                """SELECT team_id, name, country, source_provider, raw_payload
                   FROM football_teams ORDER BY team_id"""
            )
            team_columns = ("team_id", "name", "country", "source_provider", "raw_payload")
            teams = [dict(zip(team_columns, row)) for row in cursor.fetchall()]
    return leagues, seasons, teams


def main() -> int:
    database_url = os.getenv("PROVIDER_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("PROVIDER_DATABASE_URL is not configured.")
    leagues, seasons, teams = read_legacy_catalogue(database_url)
    entities = extract_legacy_catalogue_entities(leagues, seasons, teams)
    counts = store_provider_source_bundle(
        database_url, "sportmonks", entities=entities,
        write_scope="provider_source_evidence_only",
    )
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "source_provider": "sportmonks",
        "legacy_catalogue_rows_read": {
            "competitions": len(leagues), "seasons": len(seasons), "teams": len(teams),
        },
        "source_entities_written": counts["entities"],
        "source_fixtures_written": counts["fixtures"],
        "source_statistics_written": counts["statistics"],
        "canonical_entities_written": 0,
        "cross_provider_links_written": 0,
        "legacy_repository_rows_changed": 0,
        "prediction_model_modified": False,
        "prediction_ledger_touched": False,
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
                      encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
