"""Read-only inventory of independent provider evidence in CockroachDB.

This audit inventories source provenance only. It does not reconcile identities,
write canonical records, resolve conflicts, or change prediction inputs.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from provider_data_storage import _connect


QUERIES = {
    "canonical_fixture_provenance": """
        SELECT season_id, league_id, source_provider,
               COUNT(*) AS fixture_rows,
               COUNT(DISTINCT fixture_id) AS distinct_fixtures,
               COUNT(*) FILTER (WHERE LOWER(COALESCE(status, '')) IN
                   ('finished', 'complete', 'completed', 'ft', 'full time', '5'))
                   AS completed_rows,
               MIN(starting_at) AS first_kickoff,
               MAX(starting_at) AS last_kickoff
        FROM football_fixtures
        GROUP BY season_id, league_id, source_provider
        ORDER BY season_id, league_id, source_provider
    """,
    "canonical_statistics_provenance": """
        SELECT f.season_id, f.league_id, s.source_provider,
               COUNT(*) AS statistic_rows,
               COUNT(DISTINCT s.fixture_id) AS fixtures_covered,
               COUNT(DISTINCT s.team_id) AS teams_covered,
               COUNT(DISTINCT s.statistic_type) AS statistic_types,
               MIN(s.collected_at) AS first_collected_at,
               MAX(s.collected_at) AS last_collected_at
        FROM football_fixture_statistics s
        JOIN football_fixtures f ON f.fixture_id = s.fixture_id
        GROUP BY f.season_id, f.league_id, s.source_provider
        ORDER BY f.season_id, f.league_id, s.source_provider
    """,
    "archived_provider_snapshots": """
        SELECT provider, resource_type, COUNT(*) AS snapshot_rows,
               COUNT(DISTINCT cache_key) AS distinct_request_keys,
               MIN(retrieved_at) AS first_retrieved_at,
               MAX(retrieved_at) AS last_retrieved_at
        FROM provider_api_snapshots
        GROUP BY provider, resource_type
        ORDER BY provider, resource_type
    """,
    "approved_entity_links": """
        SELECT provider, entity_type, COUNT(*) AS link_count
        FROM provider_entity_links
        GROUP BY provider, entity_type
        ORDER BY provider, entity_type
    """,
    "provider_sync_state": """
        SELECT provider, resource_type, status, COUNT(*) AS state_rows,
               MAX(last_succeeded_at) AS last_succeeded_at,
               SUM(records_received) AS records_received,
               SUM(records_upserted) AS records_upserted
        FROM football_repository_sync_state
        GROUP BY provider, resource_type, status
        ORDER BY provider, resource_type, status
    """,
}


def _query_rows(cursor: Any, sql: str) -> list[dict[str, Any]]:
    cursor.execute(sql)
    names = [column.name for column in cursor.description]
    return [
        {name: value for name, value in zip(names, row)}
        for row in cursor.fetchall()
    ]


def collect_provider_provenance(database_url: str) -> dict[str, list[dict[str, Any]]]:
    """Run bounded aggregate SELECTs inside an explicitly read-only transaction."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    result: dict[str, list[dict[str, Any]]] = {}
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            for name, sql in QUERIES.items():
                result[name] = _query_rows(cursor, sql)
    return result


def build_report(data: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    fixture_rows = data.get("canonical_fixture_provenance", [])
    stats_rows = data.get("canonical_statistics_provenance", [])
    snapshot_rows = data.get("archived_provider_snapshots", [])
    fixture_providers = sorted({str(row.get("source_provider")) for row in fixture_rows})
    statistic_providers = sorted({str(row.get("source_provider")) for row in stats_rows})
    archived_providers = sorted({str(row.get("provider")) for row in snapshot_rows})
    return {
        "report_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audit_mode": "read_only",
        "database_writes": False,
        "canonical_fixture_providers": fixture_providers,
        "canonical_statistics_providers": statistic_providers,
        "archived_snapshot_providers": archived_providers,
        "independent_canonical_fixture_provider_present": any(
            "sportmonks" not in provider.casefold() for provider in fixture_providers
        ),
        "independent_canonical_statistics_provider_present": any(
            "sportmonks" not in provider.casefold() for provider in statistic_providers
        ),
        "evidence": data,
        "interpretation": (
            "Provider presence is provenance inventory, not proof of independent "
            "fixture identity or data parity. Snapshot-only providers are not treated "
            "as canonical evidence. Crosswalks and conflicts require separate review; "
            "no identity mappings or values are inferred, averaged, or promoted."
        ),
    }


def main() -> int:
    report = build_report(collect_provider_provenance(
        os.getenv("PROVIDER_DATABASE_URL", "")
    ))
    output = Path("reports/independent_provider_provenance")
    output.mkdir(parents=True, exist_ok=True)
    target = output / "latest.json"
    target.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "audit_status": "completed",
        "fixture_providers": report["canonical_fixture_providers"],
        "statistics_providers": report["canonical_statistics_providers"],
        "snapshot_providers": report["archived_snapshot_providers"],
        "report_path": str(target),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
