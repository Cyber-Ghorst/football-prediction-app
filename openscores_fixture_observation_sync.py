"""Fetch scheduled OpenScores fixtures across competitions and seasons safely."""
from __future__ import annotations

import json
import os
from collections import defaultdict
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
        return (value, "$") if all(isinstance(item, dict) for item in value) else (None, None)
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
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _identity(record: dict[str, Any], flat_keys: tuple[str, ...], nested_key: str) -> str | None:
    for key in flat_keys:
        value = record.get(key)
        if value not in (None, ""):
            return str(value).strip() or None
    nested = record.get(nested_key)
    if isinstance(nested, dict) and nested.get("id") not in (None, ""):
        return str(nested["id"]).strip() or None
    return None


def _pagination(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        value = data.get("pagination")
        if isinstance(value, dict):
            return value
        for child in data.values():
            found = _pagination(child)
            if found:
                return found
    return {}


def run_sync(
    *, client_factory=OpenScoresClient, database_url: str | None = None,
    max_leagues: int | None = None, now: datetime | None = None,
) -> dict[str, Any]:
    """Fetch one globally filtered fixture stream, then group by explicit provider identities."""
    db_url = (database_url or os.getenv("PROVIDER_DATABASE_URL", "")).strip()
    if not db_url:
        raise ValueError("PROVIDER_DATABASE_URL is required")
    if max_leagues is not None and (
        isinstance(max_leagues, bool) or not isinstance(max_leagues, int) or max_leagues < 1
    ):
        raise ValueError("max_leagues must be a positive integer or None")

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
        "seasons_sampled": 0,
        "fixtures_received": 0,
        "fixtures_normalized": 0,
        "fixtures_rejected": 0,
        "fixtures_missing_league_id": 0,
        "fixtures_missing_season_id": 0,
        "fixtures_unknown_league_id": 0,
        "fixtures_duplicate_provider_id": 0,
        "fixtures_conflicting_provider_id": 0,
        "fixtures_outside_window": 0,
        "fixtures_non_scheduled": 0,
        "fixtures_accepted_for_window": 0,
        "pages_fetched": 0,
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
    candidate_by_id: dict[str, tuple[dict[str, Any], str, str]] = {}
    conflicting_provider_ids: set[str] = set()
    grouped_records: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    grouped_retrieval: dict[tuple[str, str], str | None] = {}
    league_names: dict[str, str] = {}

    with client_factory() as client:
        league_result = client.list_leagues()
        leagues, _ = client._league_collection(league_result.get("data"))
        if leagues is None:
            raise RuntimeError("OpenScores league collection could not be normalized")
        report["leagues_discovered"] = len(leagues)
        selected_leagues = leagues if max_leagues is None else leagues[:max_leagues]
        for league in selected_leagues:
            league_id = league.get("id") or league.get("league_id")
            if league_id is not None:
                league_names[str(league_id)] = str(
                    league.get("name") or league.get("league_name") or "Unknown"
                )

        # OpenScores documents status/date filters, but not a league filter.
        # Fetch once globally; never reuse the current loop's league ID as context.
        for page in range(1, max_pages + 1):
            fixture_result = client.list_fixtures(
                status="scheduled", date_from=date_from, date_to=date_to,
                page=page, page_size=page_size,
            )
            fixtures, _ = _records(
                fixture_result.get("data"),
                ("fixtures", "items", "results", "data", "records"),
            )
            fixtures = fixtures or []
            report["pages_fetched"] += 1
            report["fixtures_received"] += len(fixtures)
            retrieved_at = fixture_result.get("retrieved_at_utc")

            for record in fixtures:
                league_id = _identity(
                    record, ("league_id", "competition_id"), "league"
                )
                season_id = _identity(record, ("season_id",), "season")
                if not league_id:
                    report["fixtures_missing_league_id"] += 1
                    continue
                if league_id not in league_names:
                    report["fixtures_unknown_league_id"] += 1
                    continue
                if not season_id:
                    report["fixtures_missing_season_id"] += 1
                    continue
                key = (league_id, season_id)
                grouped_records[key].append(record)
                grouped_retrieval[key] = retrieved_at

            pagination = _pagination(fixture_result.get("data"))
            total_pages = pagination.get("total_pages")
            if isinstance(total_pages, int):
                if page >= total_pages:
                    break
                if page == max_pages:
                    report["pagination_truncated"] = True
            elif len(fixtures) < page_size:
                break
            elif page == max_pages:
                report["pagination_truncated"] = True

    report["seasons_sampled"] = len({season for _, season in grouped_records})
    per_competition: dict[str, dict[str, Any]] = {}
    for (league_id, season_id), records in grouped_records.items():
        normalized = normalize_openscores_fixtures(
            records, league_id=league_id, season_id=season_id,
            retrieved_at_utc=grouped_retrieval.get((league_id, season_id)),
        )
        outside_window = 0
        non_scheduled = 0
        for fixture in normalized["fixtures"]:
            kickoff = _as_utc(fixture.get("kickoff_utc"))
            if kickoff is None or kickoff < window_start or kickoff > window_end:
                outside_window += 1
                continue
            if str(fixture.get("status") or "").strip().casefold() != "scheduled":
                non_scheduled += 1
                continue
            provider_fixture_id = str(fixture["provider_fixture_id"])
            fixture["reconciliation_status"] = "pending_entity_mapping"
            if provider_fixture_id in conflicting_provider_ids:
                continue
            previous = candidate_by_id.get(provider_fixture_id)
            if previous is None:
                candidate_by_id[provider_fixture_id] = (fixture, league_id, season_id)
            else:
                report["fixtures_duplicate_provider_id"] += 1
                if (previous[1], previous[2]) != (league_id, season_id):
                    candidate_by_id.pop(provider_fixture_id, None)
                    conflicting_provider_ids.add(provider_fixture_id)
                    report["fixtures_conflicting_provider_id"] += 1

        item = per_competition.setdefault(league_id, {
            "name": league_names[league_id],
            "league_id": league_id,
            "season_ids_in_fixture_results": [],
            "fixtures_received": 0,
            "fixtures_normalized": 0,
            "fixtures_rejected": 0,
            "fixtures_outside_window": 0,
            "fixtures_non_scheduled": 0,
            "fixtures_accepted_for_window": 0,
        })
        item["season_ids_in_fixture_results"].append(season_id)
        item["fixtures_received"] += normalized["fixtures_received"]
        item["fixtures_normalized"] += normalized["fixtures_normalized"]
        item["fixtures_rejected"] += normalized["fixtures_rejected"]
        item["fixtures_outside_window"] += outside_window
        item["fixtures_non_scheduled"] += non_scheduled
        report["fixtures_normalized"] += normalized["fixtures_normalized"]
        report["fixtures_rejected"] += normalized["fixtures_rejected"]
        report["fixtures_outside_window"] += outside_window
        report["fixtures_non_scheduled"] += non_scheduled

    for provider_fixture_id, (fixture, league_id, _season_id) in candidate_by_id.items():
        if provider_fixture_id not in conflicting_provider_ids:
            observations_by_id[provider_fixture_id] = fixture
            per_competition[league_id]["fixtures_accepted_for_window"] += 1

    report["competitions"] = sorted(
        per_competition.values(), key=lambda item: item["league_id"]
    )
    for item in report["competitions"]:
        item["season_ids_in_fixture_results"] = sorted(set(item["season_ids_in_fixture_results"]))
        report["fixtures_accepted_for_window"] += item["fixtures_accepted_for_window"]

    observations = list(observations_by_id.values())
    report.update(upsert_openscores_observations(db_url, observations))
    report["historical_observations_marked_out_of_window"] = mark_outside_upcoming_window_observations(
        db_url, window_start=window_start, window_end=window_end
    )
    report["reconciliation"] = reconcile_openscores_observations(db_url)

    identity_gaps = (
        report["fixtures_missing_league_id"]
        + report["fixtures_missing_season_id"]
        + report["fixtures_unknown_league_id"]
        + report["fixtures_conflicting_provider_id"]
    )
    report["status"] = (
        "pass" if not identity_gaps and not report["pagination_truncated"]
        else "partial"
    )
    return report


def main() -> int:
    report = run_sync()
    serialized = json.dumps(report, indent=2, default=str)
    Path("openscores-fixture-observation-report.json").write_text(
        serialized + "\n", encoding="utf-8"
    )
    print(serialized)
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("## OpenScores seven-day fixture observation sync\n\n")
            for key in (
                "status", "window_start_utc", "window_end_utc", "leagues_discovered",
                "seasons_sampled", "fixtures_received", "fixtures_normalized",
                "fixtures_rejected", "fixtures_missing_league_id",
                "fixtures_missing_season_id", "fixtures_unknown_league_id",
                "fixtures_duplicate_provider_id", "fixtures_conflicting_provider_id",
                "fixtures_outside_window", "fixtures_non_scheduled",
                "fixtures_accepted_for_window", "pages_fetched",
                "pagination_truncated", "observations_upserted",
                "historical_observations_marked_out_of_window",
                "canonical_fixtures_written", "prediction_ledger_touched",
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
