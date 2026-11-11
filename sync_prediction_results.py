"""Scheduled, fail-closed synchronization of verified completed prediction results.

This job updates only blank result fields for exact Sportmonks fixture records.
It never changes forecasts, model weights, or manually entered scores.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from typing import Any, Callable, Mapping

from prediction_evaluation import evaluate_prediction_ledger
from prediction_results import group_completed_fixture_candidates, verified_final_score
from prediction_storage import load_prediction_ledger, save_prediction_records
from sportmonks import SportmonksClient, SportmonksError
from free_fixture_result_sync import sync_free_source_results


def _utc_now(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _evaluation_summary(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    evaluation = evaluate_prediction_ledger(records)
    return {
        "saved_records": evaluation.get("records_total", len(records)),
        "pre_match_predictions": evaluation.get("pre_match_predictions", 0),
        "completed_pre_match_predictions": evaluation.get("completed_pre_match_predictions", 0),
        "model_metrics": evaluation.get("model"),
        "evaluation_sample_assessment": evaluation.get("evaluation_sample_assessment"),
    }


def sync_completed_results(
    *,
    database_url: str | None,
    api_token: str | None = None,
    limit: int = 10,
    now: datetime | None = None,
    ledger_loader: Callable[[str], list[dict[str, Any]]] | None = None,
    ledger_saver: Callable[[str, list[Mapping[str, Any]]], int] | None = None,
    client_factory: Callable[..., Any] | None = None,
    provider_database_url: str | None = None,
    bzzoiro_token: str | None = None,
    free_source_limit: int = 10,
) -> tuple[dict[str, Any], int]:
    """Sync up to `limit` unique fixtures; return a report and process exit code."""
    started = _utc_now(now)
    report: dict[str, Any] = {
        "report_name": "scheduled_prediction_result_sync",
        "status": "starting",
        "started_at_utc": started.isoformat(),
        "fixture_limit": limit,
        "fixtures_checked": 0,
        "fixtures_without_verified_final_score": 0,
        "records_updated": 0,
        "errors": [],
        "fixture_results": [],
    }
    if not isinstance(limit, int) or limit < 1 or limit > 50:
        report["status"] = "invalid_limit"
        report["error"] = "limit must be an integer between 1 and 50"
        report["completed_at_utc"] = _utc_now().isoformat()
        return report, 2
    if not database_url:
        report["status"] = "skipped_database_not_configured"
        report["note"] = "DATABASE_URL is not configured; no ledger or provider data was accessed."
        report["completed_at_utc"] = _utc_now().isoformat()
        return report, 0

    loader = ledger_loader or load_prediction_ledger
    saver = ledger_saver or save_prediction_records
    try:
        records = loader(database_url)
    except Exception as exc:
        report["status"] = "database_read_failed"
        report["error_type"] = type(exc).__name__
        report["completed_at_utc"] = _utc_now().isoformat()
        return report, 1

    report["ledger_records"] = len(records)
    updated_rows: list[dict[str, Any]] = []
    try:
        free_report, free_updated_rows = sync_free_source_results(
            records,
            provider_database_url=provider_database_url,
            now=started,
            limit=free_source_limit,
            bzzoiro_token=bzzoiro_token,
        )
        report["free_source_results"] = free_report
        updated_rows.extend(free_updated_rows)
        report["records_updated"] = len(updated_rows)
    except Exception as exc:
        report["free_source_results"] = {
            "status": "processing_error",
            "error_type": type(exc).__name__,
            "message": str(exc)[:250],
        }

    candidates = group_completed_fixture_candidates(records, started)
    report["candidate_fixtures"] = len(candidates)
    report["limit_reached"] = len(candidates) > limit
    report["fixtures_deferred"] = max(0, len(candidates) - limit)
    if not candidates:
        try:
            if updated_rows:
                saver(database_url, updated_rows)
                report["status"] = "updated"
            else:
                report["status"] = (
                    "attention_required"
                    if report.get("free_source_results", {}).get("errors")
                    else "no_eligible_fixtures"
                )
        except Exception as exc:
            report["status"] = "database_write_failed"
            report["error_type"] = type(exc).__name__
            report["completed_at_utc"] = _utc_now().isoformat()
            return report, 1
        report["evaluation"] = _evaluation_summary(records)
        report["completed_at_utc"] = _utc_now().isoformat()
        return report, 0

    token = (api_token or os.getenv("SPORTMONKS_API_TOKEN") or os.getenv("SPORTMONKS_API_KEY") or "").strip()
    if not token:
        if updated_rows:
            try:
                saver(database_url, updated_rows)
                report["status"] = "updated_without_sportmonks_credential"
            except Exception as exc:
                report["status"] = "database_write_failed"
                report["error_type"] = type(exc).__name__
                report["completed_at_utc"] = _utc_now().isoformat()
                return report, 1
        else:
            report["status"] = "blocked_missing_sportmonks_credential"
            report["note"] = "Sportmonks results could not be checked because no credential is configured. No unverified score was changed."
        report["evaluation"] = _evaluation_summary(records)
        report["completed_at_utc"] = _utc_now().isoformat()
        return report, 0

    factory = client_factory or SportmonksClient
    try:
        client_context = factory(api_token=token)
    except TypeError:
        client_context = factory()

    with client_context as client:
        for group in candidates[:limit]:
            representative = group[0]
            fixture_id = str(representative.get("fixture_id") or "")
            item_report: dict[str, Any] = {
                "fixture_id": fixture_id,
                "ledger_records": len(group),
                "status": "not_verified",
            }
            try:
                fixture = client.fixture(
                    fixture_id,
                    include="participants;scores;state;league;season",
                )
                report["fixtures_checked"] += 1
                metadata = getattr(client, "last_metadata", {}) or {}
                item_report["http_status"] = metadata.get("http_status")
                item_report["request_seconds"] = metadata.get("request_seconds")
                item_report["rate_remaining"] = metadata.get("rate_remaining")
                if not isinstance(fixture, Mapping):
                    report["fixtures_without_verified_final_score"] += 1
                    item_report["reason"] = "fixture_detail_not_returned"
                    report["fixture_results"].append(item_report)
                    continue

                score = verified_final_score(representative, fixture)
                if score is None:
                    report["fixtures_without_verified_final_score"] += 1
                    item_report["reason"] = "exact_fixture_or_final_90_minute_score_not_verified"
                    report["fixture_results"].append(item_report)
                    continue

                verified_at = _utc_now().isoformat()
                fixture_updated = 0
                for row in group:
                    if not isinstance(row, dict) or verified_final_score(row, fixture) != score:
                        continue
                    # group_completed_fixture_candidates excludes all rows with
                    # existing scores; this guard protects against future callers.
                    if row.get("actual_home_goals") not in (None, "") or row.get("actual_away_goals") not in (None, ""):
                        continue
                    home_goals, away_goals = score
                    row["actual_home_goals"] = home_goals
                    row["actual_away_goals"] = away_goals
                    row["actual_result"] = (
                        "home" if home_goals > away_goals
                        else "away" if home_goals < away_goals
                        else "draw"
                    )
                    row["actual_result_provider"] = "sportmonks"
                    row["actual_result_fixture_id"] = str(fixture.get("id"))
                    row["actual_result_verified_at"] = verified_at
                    row["actual_result_verification"] = "exact_fixture_team_competition_season_and_score"
                    row["actual_result_provider_updated_at"] = (
                        fixture.get("updated_at") or fixture.get("last_processed_at") or ""
                    )
                    updated_rows.append(row)
                    fixture_updated += 1

                report["records_updated"] += fixture_updated
                item_report["records_updated"] = fixture_updated
                item_report["verified_score"] = f"{score[0]}-{score[1]}"
                item_report["status"] = "updated" if fixture_updated else "no_matching_blank_ledger_rows"
                report["fixture_results"].append(item_report)
                if not fixture_updated:
                    report["fixtures_without_verified_final_score"] += 1
            except SportmonksError as exc:
                report["errors"].append({
                    "fixture_id": fixture_id,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                })
                item_report["status"] = "provider_error"
                item_report["error_type"] = type(exc).__name__
                report["fixture_results"].append(item_report)
            except Exception as exc:
                report["errors"].append({
                    "fixture_id": fixture_id,
                    "error_type": type(exc).__name__,
                })
                item_report["status"] = "processing_error"
                item_report["error_type"] = type(exc).__name__
                report["fixture_results"].append(item_report)

    if updated_rows:
        try:
            saver(database_url, updated_rows)
        except Exception as exc:
            report["status"] = "database_write_failed"
            report["error_type"] = type(exc).__name__
            report["completed_at_utc"] = _utc_now().isoformat()
            return report, 1

    report["evaluation"] = _evaluation_summary(records)
    if report["errors"] and report["records_updated"]:
        report["status"] = "updated_with_errors"
    elif report["errors"]:
        report["status"] = "attention_required"
    elif report["records_updated"]:
        report["status"] = "updated"
    else:
        report["status"] = "no_verified_results"
    report["completed_at_utc"] = _utc_now().isoformat()
    report["elapsed_seconds"] = round(
        (_utc_now() - started).total_seconds(), 3
    )
    return report, 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    report, exit_code = sync_completed_results(
        database_url=os.getenv("DATABASE_URL"),
        api_token=os.getenv("SPORTMONKS_API_TOKEN") or os.getenv("SPORTMONKS_API_KEY"),
        provider_database_url=os.getenv("PROVIDER_DATABASE_URL"),
        bzzoiro_token=os.getenv("BZZOIRO_API_TOKEN"),
        limit=args.limit,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
