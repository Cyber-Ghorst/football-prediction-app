"""Fetch a bounded OpenScores sample and stage normalized observations only."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openscores import OpenScoresClient
from openscores_normalizer import normalize_openscores_fixtures
from openscores_observation_store import (
    reconcile_openscores_observations,
    upsert_openscores_observations,
)


def _records(value: Any, preferred: tuple[str, ...], depth: int = 0):
    if depth > 6:
        return None, None
    if isinstance(value, list):
        if value and all(isinstance(item, dict) for item in value):
            return value, "$"
        return None, None
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


def run_sync(
    *,
    client_factory=OpenScoresClient,
    database_url: str | None = None,
    max_leagues: int = 6,
) -> dict[str, Any]:
    """Sample one returned season per league, then stage—not promote—fixtures."""
    db_url = (database_url or os.getenv("PROVIDER_DATABASE_URL", "")).strip()
    if not db_url:
        raise ValueError("PROVIDER_DATABASE_URL is required")
    if isinstance(max_leagues, bool) or not isinstance(max_leagues, int) or not 1 <= max_leagues <= 6:
        raise ValueError("max_leagues must be between 1 and 6")

    report: dict[str, Any] = {
        "operation": "openscores_fixture_observation_sync",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "fail",
        "leagues_discovered": 0,
        "seasons_sampled": 0,
        "fixtures_received": 0,
        "fixtures_normalized": 0,
        "fixtures_rejected": 0,
        "observations_upserted": 0,
        "canonical_fixtures_written": 0,
        "reconciliation": None,
        "competitions": [],
        "read_only_for_canonical_fixtures": True,
        "prediction_ledger_touched": False,
    }
    observations = []
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
                report["competitions"].append({
                    "name": league_name, "status": "skipped_missing_league_id"
                })
                continue
            season_result = client.list_seasons(league_id)
            seasons, _ = _records(
                season_result.get("data"),
                ("seasons", "items", "results", "data", "records"),
            )
            if not seasons:
                report["competitions"].append({
                    "name": league_name, "status": "skipped_no_season"
                })
                continue
            season = seasons[0]
            season_id = season.get("id") or season.get("season_id")
            if season_id is None:
                report["competitions"].append({
                    "name": league_name, "status": "skipped_missing_season_id"
                })
                continue
            report["seasons_sampled"] += 1
            fixture_result = client.list_fixtures(season_id=season_id)
            fixtures, collection_path = _records(
                fixture_result.get("data"),
                ("fixtures", "items", "results", "data", "records"),
            )
            fixtures = fixtures or []
            normalized = normalize_openscores_fixtures(
                fixtures,
                league_id=league_id,
                season_id=season_id,
                retrieved_at_utc=fixture_result.get("retrieved_at_utc"),
            )
            observations.extend(normalized["fixtures"])
            report["fixtures_received"] += normalized["fixtures_received"]
            report["fixtures_normalized"] += normalized["fixtures_normalized"]
            report["fixtures_rejected"] += normalized["fixtures_rejected"]
            report["competitions"].append({
                "name": league_name,
                "league_id": str(league_id),
                "season_id": str(season_id),
                "fixture_collection_path": collection_path,
                "fixtures_received": normalized["fixtures_received"],
                "fixtures_normalized": normalized["fixtures_normalized"],
                "fixtures_rejected": normalized["fixtures_rejected"],
                "rejected_reasons": normalized["rejected"],
            })

    saved = upsert_openscores_observations(db_url, observations)
    report.update(saved)
    report["reconciliation"] = reconcile_openscores_observations(db_url)
    report["status"] = "pass"
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
            summary.write("## OpenScores fixture observation sync\n\n")
            for key in (
                "status", "leagues_discovered", "seasons_sampled",
                "fixtures_received", "fixtures_normalized", "fixtures_rejected",
                "observations_upserted", "canonical_fixtures_written",
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
