"""Fetch scheduled OpenScores fixtures across seasons inside a strict seven-day window."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from openscores import OpenScoresClient
from openscores_normalizer import normalize_openscores_fixtures
from openscores_observation_store import (
    mark_outside_upcoming_window_observations,
    reconcile_openscores_observations,
    upsert_openscores_observations,
)


def _records(value: Any, preferred: tuple[str, ...], depth: int = 0):
    if depth > 6:
        return None, None
    if isinstance(value, list):
        return (value, "$") if value and all(isinstance(item, dict) for item in value) else (None, None)
    if isinstance(value, dict):
        for key in preferred:
            if key in value:
                found, path = _records(value[key], preferred, depth + 1)
                if found is not None:
                    return found, key if path == "$" else f"{key}.{path}"
        for key, child in value.items():
            if key not in preferred and isinstance(child, (dict, list)):
                found, path = _records(child, preferred, depth + 1)
                if found is not None:
                    return found, f"{key}.{path}"
    return None, None


def _as_utc(value: Any) -> datetime | None:
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def run_sync(
    *, client_factory=OpenScoresClient, database_url: str | None = None,
    max_leagues: int = 6, now: datetime | None = None,
) -> dict[str, Any]:
    """Fetch scheduled fixtures across all provider seasons from now through seven days."""
    db_url = (database_url or os.getenv("PROVIDER_DATABASE_URL", "")).strip()
    if not db_url:
        raise ValueError("PROVIDER_DATABASE_URL is required")
    if isinstance(max_leagues, bool) or not isinstance(max_leagues, int) or not 1 <= max_leagues <= 6:
        raise ValueError("max_leagues must be between 1 and 6")

    window_start = _as_utc(now or datetime.now(timezone.utc))
    if window_start is None:
        raise ValueError("now must be a valid datetime")
    window_end = window_start + timedelta(days=7)
    date_from = window_start.isoformat().replace("+00:00", "Z")
    date_to = window_end.isoformat().replace("+00:00", "Z")
    page_size, max_pages = 200, 10

    report: dict[str, Any] = {
        "operation": "openscores_fixture_observation_sync",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "fail",
        "window_days": 7,
        "window_start_utc": date_from,
        "window_end_utc": date_to,
        "leagues_discovered": 0,
        "seasons_discovered": 0,
        "seasons_sampled": 0,
        "fixtures_received": 0,
        "fixtures_normalized": 0,
        "fixtures_rejected": 0,
        "fixtures_missing_season_id": 0,
        "fixtures_outside_window": 0,
        "fixtures_non_scheduled": 0,
        "fixtures_accepted_for_window": 0,
        "pagination_truncated": False,
        "observations_upserted": 0,
        "historical_observations_marked_out_of_window": 0,
        "canonical_fixtures_written": 0,
        "reconciliation": None,
        "competitions": [],
        "read_only_for_canonical_fixtures": True,
        "prediction_ledger_touched": False,
    }
    observations_by_id: dict[str, dict[str, Any]] = {}
    all_season_ids: set[str] = set()

    with client_factory() as client:
        league_result = client.list_leagues()
        leagues, _ = client._league_collection(league_result.get("data"))
        if leagues is None:
            raise RuntimeError("OpenScores league collection could not be normalized")
        report["leagues_discovered"] = len(leagues)

        for league in leagues[:max_leagues]:
            league_id = league.get("id") or league.get("league_id")
            league_name = str(league.get("name") or league.get("league_name") or "Unknown")
            if league_id is None:
                report["competitions"].append({"name": league_name, "status": "skipped_missing_league_id"})
                continue

            season_result = client.list_seasons(league_id)
            seasons, _ = _records(season_result.get("data"), ("seasons", "items", "results", "data", "records"))
            seasons = seasons or []
            report["seasons_discovered"] += len(seasons)
            season_ids = [
                str(item.get("id") or item.get("season_id"))
                for item in seasons if item.get("id") is not None or item.get("season_id") is not None
            ]
            fallback_season_id = season_ids[0] if len(season_ids) == 1 else None

            competition_fixtures: dict[str, dict[str, Any]] = {}
            comp_received = comp_normalized = comp_rejected = 0
            comp_missing_season = comp_outside = comp_non_scheduled = 0
            comp_pages = 0
            comp_season_ids: set[str] = set()
            collection_path = None
            comp_truncated = False

            for page in range(1, max_pages + 1):
                # No season_id filter: this lets the provider return the current
                # season even if its season catalogue is stale or incomplete.
                fixture_result = client.list_fixtures(
                    status="scheduled", date_from=date_from, date_to=date_to,
                    page=page, page_size=page_size,
                )
                fixtures, page_path = _records(
                    fixture_result.get("data"), ("fixtures", "items", "results", "data", "records")
                )
                fixtures = fixtures or []
                comp_pages += 1
                comp_received += len(fixtures)
                if collection_path is None:
                    collection_path = page_path

                grouped: dict[str, list[dict[str, Any]]] = {}
                for record in fixtures:
                    record_season = record.get("season_id")
                    season_key = str(record_season) if record_season not in (None, "") else fallback_season_id
                    if not season_key:
                        comp_missing_season += 1
                        continue
                    grouped.setdefault(season_key, []).append(record)

                for season_key, season_records in grouped.items():
                    comp_season_ids.add(season_key)
                    all_season_ids.add(season_key)
                    normalized = normalize_openscores_fixtures(
                        season_records, league_id=league_id, season_id=season_key,
                        retrieved_at_utc=fixture_result.get("retrieved_at_utc"),
                    )
                    comp_normalized += normalized["fixtures_normalized"]
                    comp_rejected += normalized["fixtures_rejected"]
                    for fixture in normalized["fixtures"]:
                        kickoff = _as_utc(fixture.get("kickoff_utc"))
                        if kickoff is None or kickoff < window_start or kickoff > window_end:
                            comp_outside += 1
                            continue
                        if str(fixture.get("status") or "").strip().casefold() != "scheduled":
                            comp_non_scheduled += 1
                            continue
                        fixture["reconciliation_status"] = "pending_entity_mapping"
                        competition_fixtures[str(fixture["provider_fixture_id"])] = fixture

                pagination = fixture_result.get("data", {}).get("pagination", {}) if isinstance(fixture_result.get("data"), dict) else {}
                total_pages = pagination.get("total_pages") if isinstance(pagination, dict) else None
                if isinstance(total_pages, int):
                    if page >= total_pages:
                        break
                    if page == max_pages:
                        comp_truncated = True
                elif len(fixtures) < page_size:
                    break
                elif page == max_pages:
                    comp_truncated = True

            report["fixtures_received"] += comp_received
            report["fixtures_normalized"] += comp_normalized
            report["fixtures_rejected"] += comp_rejected
            report["fixtures_missing_season_id"] += comp_missing_season
            report["fixtures_outside_window"] += comp_outside
            report["fixtures_non_scheduled"] += comp_non_scheduled
            report["fixtures_accepted_for_window"] += len(competition_fixtures)
            report["pagination_truncated"] = report["pagination_truncated"] or comp_truncated
            observations_by_id.update(competition_fixtures)
            report["competitions"].append({
                "name": league_name, "league_id": str(league_id),
                "season_ids_discovered": season_ids,
                "season_ids_in_fixture_results": sorted(comp_season_ids),
                "fixture_collection_path": collection_path,
                "pages_fetched": comp_pages, "page_size": page_size,
                "fixtures_received": comp_received, "fixtures_normalized": comp_normalized,
                "fixtures_rejected": comp_rejected, "fixtures_missing_season_id": comp_missing_season,
                "fixtures_outside_window": comp_outside, "fixtures_non_scheduled": comp_non_scheduled,
                "fixtures_accepted_for_window": len(competition_fixtures),
                "season_filter": None, "status_filter": "scheduled",
                "date_from": date_from, "date_to": date_to,
                "pagination_truncated": comp_truncated,
            })

    report["seasons_sampled"] = len(all_season_ids)
    observations = list(observations_by_id.values())
    report.update(upsert_openscores_observations(db_url, observations))
    report["historical_observations_marked_out_of_window"] = mark_outside_upcoming_window_observations(
        db_url, window_start=window_start, window_end=window_end
    )
    report["reconciliation"] = reconcile_openscores_observations(db_url)
    report["status"] = "pass"
    return report


def main() -> int:
    report = run_sync()
    serialized = json.dumps(report, indent=2, default=str)
    Path("openscores-fixture-observation-report.json").write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("## OpenScores seven-day fixture observation sync\n\n")
            for key in (
                "status", "window_start_utc", "window_end_utc", "leagues_discovered",
                "seasons_discovered", "seasons_sampled", "fixtures_received",
                "fixtures_normalized", "fixtures_rejected", "fixtures_missing_season_id",
                "fixtures_outside_window", "fixtures_non_scheduled", "fixtures_accepted_for_window",
                "pagination_truncated", "observations_upserted",
                "historical_observations_marked_out_of_window", "canonical_fixtures_written",
                "prediction_ledger_touched",
            ):
                summary.write(f"- {key}: {report.get(key)}\n")
            summary.write("\n### Reconciliation\n\n")
            summary.write(f"`{json.dumps(report.get('reconciliation'), sort_keys=True)}`\n")
            summary.write("\n### Competition samples\n\n")
            for item in report["competitions"]:
                summary.write(f"- {item}\n")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
