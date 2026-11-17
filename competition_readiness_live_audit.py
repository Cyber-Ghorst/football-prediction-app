"""Read-only readiness audit over the live CockroachDB football repository.

Only exact provider links with matching approval-audit rows and existing
repository targets count as approved. Legacy Sportmonks anchors are not
silently promoted to verified identities. Missing statistics/tactical
contracts remain incomplete until explicitly modelled.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Mapping

from competition_readiness import build_competition_readiness_report
from provider_data_storage import _connect
from provider_neutral_repository import split_provider_identity

FRESHNESS_WINDOW = timedelta(hours=24)
UPCOMING_STATUSES = {"scheduled", "not started", "not_started", "ns", "upcoming", "fixture"}
COMPLETED_STATUSES = {"ft", "finished", "complete", "completed", "full time", "full_time"}


def _rows(cursor, query: str) -> list[dict[str, Any]]:
    cursor.execute(query)
    names = [column.name for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _approved_source_ids(rows: list[dict[str, Any]]) -> dict[str, set[str]]:
    approved: dict[str, set[str]] = {}
    for row in rows:
        provider = str(row.get("provider") or "").strip().casefold()
        entity_type = str(row.get("entity_type") or "").strip().casefold()
        source_id = str(row.get("provider_entity_id") or "").strip()
        if provider and entity_type and source_id:
            approved.setdefault(f"{provider}:{entity_type}", set()).add(source_id)
    return approved


def build_live_readiness_records(
    leagues: list[Mapping[str, Any]],
    seasons: list[Mapping[str, Any]],
    fixtures: list[Mapping[str, Any]],
    approved_links: list[Mapping[str, Any]],
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    """Build conservative per-season evidence records from normalized DB rows."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    approved = _approved_source_ids([dict(row) for row in approved_links])
    league_by_id = {str(row.get("league_id")): dict(row) for row in leagues}
    fixtures_by_season: dict[str, list[dict[str, Any]]] = {}
    for fixture in fixtures:
        fixtures_by_season.setdefault(str(fixture.get("season_id")), []).append(dict(fixture))

    output: list[dict[str, Any]] = []
    for season in seasons:
        season = dict(season)
        season_id = str(season.get("season_id") or "")
        league_id = str(season.get("league_id") or "")
        league = league_by_id.get(league_id)
        if not league:
            continue
        provider = str(league.get("source_provider") or season.get("source_provider") or "").casefold()
        league_source_id = split_provider_identity(league_id, league.get("source_provider")).get("provider_entity_id")
        season_source_id = split_provider_identity(season_id, season.get("source_provider")).get("provider_entity_id")
        league_approved = league_source_id in approved.get(f"{provider}:league", set())
        season_provider = str(season.get("source_provider") or provider).casefold()
        season_approved = season_source_id in approved.get(f"{season_provider}:season", set())

        season_fixtures = fixtures_by_season.get(season_id, [])
        participating: set[str] = set()
        history: dict[str, int] = {}
        upcoming: list[dict[str, Any]] = []
        for fixture in season_fixtures:
            home = str(fixture.get("home_team_id") or "")
            away = str(fixture.get("away_team_id") or "")
            if home:
                participating.add(home)
            if away:
                participating.add(away)
            status = str(fixture.get("status") or "").strip().casefold()
            if status in COMPLETED_STATUSES and fixture.get("home_goals") is not None and fixture.get("away_goals") is not None:
                if home:
                    history[home] = history.get(home, 0) + 1
                if away:
                    history[away] = history.get(away, 0) + 1
            kickoff = fixture.get("starting_at")
            if kickoff and getattr(kickoff, "tzinfo", None) is not None:
                if kickoff.astimezone(timezone.utc) > now.astimezone(timezone.utc) and status in UPCOMING_STATUSES:
                    upcoming.append(fixture)

        team_ids = sorted(participating)
        team_mapped = 0
        for team_id in team_ids:
            team_source_id = split_provider_identity(team_id, provider).get("provider_entity_id")
            if team_source_id in approved.get(f"{provider}:team", set()):
                team_mapped += 1

        verified_upcoming = []
        for fixture in upcoming:
            fixture_provider = str(fixture.get("source_provider") or provider).casefold()
            fixture_source_id = split_provider_identity(fixture.get("fixture_id"), fixture_provider).get("provider_entity_id")
            home_source = split_provider_identity(fixture.get("home_team_id"), provider).get("provider_entity_id")
            away_source = split_provider_identity(fixture.get("away_team_id"), provider).get("provider_entity_id")
            fixture_linked = fixture_source_id in approved.get(f"{fixture_provider}:fixture", set())
            teams_linked = (
                home_source in approved.get(f"{provider}:team", set())
                and away_source in approved.get(f"{provider}:team", set())
                and home_source != away_source
            )
            if fixture_linked and teams_linked and league_approved and season_approved:
                verified_upcoming.append(fixture)

        freshest = None
        for fixture in upcoming:
            stamp = fixture.get("provider_updated_at") or fixture.get("collected_at")
            if stamp and getattr(stamp, "tzinfo", None) is not None:
                stamp = stamp.astimezone(timezone.utc)
                freshest = stamp if freshest is None or stamp > freshest else freshest
        freshness = (
            "fresh" if freshest and now.astimezone(timezone.utc) - freshest <= FRESHNESS_WINDOW
            else "stale" if freshest else "unknown"
        )

        canonical_season = next(
            (str(row.get("canonical_entity_id")) for row in approved_links
             if str(row.get("provider") or "").casefold() == season_provider
             and row.get("entity_type") == "season"
             and str(row.get("provider_entity_id")) == str(season_source_id)),
            None,
        )
        output.append({
            "competition": {
                "name": league.get("name"),
                "country": league.get("country"),
                "type": league.get("competition_type"),
                "identity_verified": league_approved,
            },
            "season": {
                "id": canonical_season,
                "name": season.get("name"),
                "active": season.get("is_current") is True,
                "identity_verified": season_approved,
            },
            "teams": {
                "participating_count": len(team_ids),
                "approved_mapping_count": team_mapped,
                "history_by_team": {
                    team_id: history.get(team_id, 0) for team_id in team_ids
                },
                # No authoritative completeness contract currently exists in
                # this repository; unknown is intentionally represented as false.
                "statistics_complete_by_team": {team_id: False for team_id in team_ids},
                "tactical_components_by_team": {},
            },
            "fixture": {
                "upcoming_valid": bool(verified_upcoming),
                "source_freshness": freshness,
            },
            "evidence_generated_at": now.astimezone(timezone.utc).isoformat(),
            "source_provider": provider,
            "source_competition_id": league_id,
            "source_season_id": season_id,
            "stored_fixture_count": len(season_fixtures),
            "participating_team_count": len(team_ids),
            "approved_team_mapping_count": team_mapped,
            "completed_fixture_count": sum(
                1 for fixture in season_fixtures
                if str(fixture.get("status") or "").strip().casefold() in COMPLETED_STATUSES
                and fixture.get("home_goals") is not None and fixture.get("away_goals") is not None
            ),
            "upcoming_fixture_candidates": len(upcoming),
            "verified_upcoming_fixtures": len(verified_upcoming),
            "statistics_contract_status": "not_defined_fail_closed",
            "tactical_evidence_status": "not_stored_fail_closed",
        })
    return output


def read_live_repository_evidence(database_url: str) -> dict[str, Any]:
    """Read competition, season, fixture and approved-link rows in a read-only txn."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            leagues = _rows(cursor, """
                SELECT league_id, name, country, competition_type, source_provider,
                       provider_updated_at, collected_at
                FROM football_leagues ORDER BY league_id
            """)
            seasons = _rows(cursor, """
                SELECT season_id, league_id, name, start_date, end_date, is_current,
                       source_provider, provider_updated_at, collected_at
                FROM football_seasons ORDER BY league_id, season_id
            """)
            fixtures = _rows(cursor, """
                SELECT fixture_id, season_id, league_id, home_team_id, away_team_id,
                       starting_at, status, home_goals, away_goals, source_provider,
                       provider_updated_at, collected_at
                FROM football_fixtures ORDER BY season_id, starting_at
            """)
            approved_links = _rows(cursor, """
                SELECT DISTINCT link.provider, link.entity_type,
                       link.provider_entity_id, link.canonical_entity_id
                FROM provider_entity_links AS link
                INNER JOIN provider_entity_link_approval_audit AS approval
                  ON approval.link_id = link.link_id
                 AND approval.provider = link.provider
                 AND approval.entity_type = link.entity_type
                 AND approval.provider_entity_id = link.provider_entity_id
                 AND approval.canonical_entity_id = link.canonical_entity_id
                 AND LENGTH(BTRIM(approval.approval_reason)) >= 12
                INNER JOIN (
                    SELECT 'league' AS entity_type, league_id AS entity_id FROM football_leagues
                    UNION ALL SELECT 'season', season_id FROM football_seasons
                    UNION ALL SELECT 'team', team_id FROM football_teams
                    UNION ALL SELECT 'fixture', fixture_id FROM football_fixtures
                ) AS target
                  ON target.entity_type = link.entity_type
                 AND target.entity_id = link.canonical_entity_id
                ORDER BY link.provider, link.entity_type, link.provider_entity_id
            """)
    now = datetime.now(timezone.utc)
    records = build_live_readiness_records(
        leagues, seasons, fixtures, approved_links, now=now,
    )
    report = build_competition_readiness_report(records, now=now)
    report["report_scope"] = (
        "All competition-season rows currently stored in the CockroachDB football repository. "
        "Read-only audit; no identities, mappings, fixtures, predictions or model settings are written."
    )
    report["database_read_only"] = True
    report["database_rows_read"] = {
        "competitions": len(leagues), "seasons": len(seasons),
        "fixtures": len(fixtures), "audited_approved_links": len(approved_links),
    }
    report["competitions"] = [
        {**result, **{
            key: record[key] for key in (
                "source_provider", "source_competition_id", "source_season_id",
                "stored_fixture_count", "participating_team_count",
                "approved_team_mapping_count", "completed_fixture_count",
                "upcoming_fixture_candidates", "verified_upcoming_fixtures",
                "statistics_contract_status", "tactical_evidence_status",
            )
        }}
        for result, record in zip(report["competitions"], sorted(
            records, key=lambda row: (
                str(row["competition"].get("country") or "").casefold(),
                str(row["competition"].get("name") or "").casefold(),
                str(row["season"].get("name") or "").casefold(),
            )
        ))
    ]
    return report


def write_live_readiness_report(
    database_url: str,
    output_dir: str = "reports/competition_readiness",
) -> dict[str, Any]:
    report = read_live_repository_evidence(database_url)
    destination = Path(output_dir)
    archive = destination / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"
    (destination / "latest.json").write_text(encoded, encoding="utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (archive / f"live-{stamp}.json").write_text(encoded, encoding="utf-8")
    lines = [
        "# Live competition readiness audit", "",
        f"Generated: {report['generated_at_utc']}", "",
        "| Status | Competition-seasons |",
        "|---|---:|",
    ]
    for status in ("not_ready", "partially_ready", "prediction_ready"):
        lines.append(f"| {status} | {report['summary'][status]} |")
    lines.extend(["", "## Competition-season blockers", ""])
    for row in report["competitions"]:
        lines.append(
            f"### {row.get('competition_name')} — {row.get('country')} "
            f"({row.get('season_name')})"
        )
        for blocker in row["hard_blockers"] + row["improvement_blockers"]:
            lines.append(f"- {blocker}")
        lines.append(
            f"- Stored fixtures: {row.get('stored_fixture_count', 0)}; "
            f"participants: {row.get('participating_team_count', 0)}; "
            f"verified upcoming fixtures: {row.get('verified_upcoming_fixtures', 0)}"
        )
        lines.append("")
    (destination / "latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    import os
    result = write_live_readiness_report(os.environ.get("PROVIDER_DATABASE_URL", ""))
    print(json.dumps({
        "summary": result["summary"],
        "database_rows_read": result["database_rows_read"],
        "database_read_only": result["database_read_only"],
    }, sort_keys=True))
