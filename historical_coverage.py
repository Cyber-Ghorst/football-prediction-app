"""Leakage-safe validation of archived prediction-performance snapshots.

Archives are repeated reports, not independent fixtures. This module validates
and deduplicates the fixture-level evidence before making any sample-size claim.
It is descriptive only and cannot authorize model or provider changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import sqrt
from pathlib import Path
import json
import re
from typing import Any, Iterable, Mapping


_OUTCOMES = {"home", "draw", "away"}
_SCORE = re.compile(r"^(\\d+)\\s*[-:]\\s*(\\d+)$")


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _score_outcome(value: Any) -> tuple[str, tuple[int, int]] | None:
    if not isinstance(value, str):
        return None
    match = _SCORE.fullmatch(value.strip())
    if not match:
        return None
    home, away = int(match.group(1)), int(match.group(2))
    outcome = "home" if home > away else "away" if home < away else "draw"
    return outcome, (home, away)


def _wilson_interval(successes: int, total: int) -> dict[str, float] | None:
    if total <= 0:
        return None
    z = 1.96
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = z * sqrt(
        proportion * (1 - proportion) / total
        + z * z / (4 * total * total)
    ) / denominator
    return {
        "lower": round(max(0.0, center - margin) * 100, 1),
        "upper": round(min(1.0, center + margin) * 100, 1),
    }


def load_archived_performance_reports(
    archive_directory: str | Path,
    *,
    latest_report_path: str | Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load archived and latest JSON reports while recording parse failures."""
    directory = Path(archive_directory)
    paths = sorted(directory.glob("*.json")) if directory.exists() else []
    if latest_report_path is not None:
        latest = Path(latest_report_path)
        if latest.exists() and latest not in paths:
            paths.append(latest)
    reports: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Report root must be a JSON object.")
            reports.append(payload)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            errors.append({"file": path.name, "error": type(exc).__name__})
    return reports, {
        "files_found": len(paths),
        "load_errors": errors,
        "loaded_files": len(reports),
    }


def build_historical_coverage_validation(
    archived_reports: Iterable[Mapping[str, Any]] | None,
    *,
    archive_load_audit: Mapping[str, Any] | None = None,
    minimum_verified_fixtures: int = 30,
) -> dict[str, Any]:
    """Audit archived forecast history without counting repeated snapshots twice."""
    if (
        isinstance(minimum_verified_fixtures, bool)
        or not isinstance(minimum_verified_fixtures, int)
        or minimum_verified_fixtures < 1
    ):
        raise ValueError("minimum_verified_fixtures must be a positive integer.")

    reports = [row for row in (archived_reports or []) if isinstance(row, Mapping)]
    fixtures: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    history_rows = 0
    invalid_rows = 0
    count_mismatches = 0
    for report in reports:
        rows = report.get("performance_history")
        rows = rows if isinstance(rows, list) else []
        history_rows += len(rows)
        model = report.get("model") if isinstance(report.get("model"), Mapping) else {}
        reported_completed = report.get("completed_pre_match_predictions")
        if reported_completed is None:
            reported_completed = model.get("matches")
        if isinstance(reported_completed, int) and not isinstance(reported_completed, bool):
            if reported_completed != len(rows):
                count_mismatches += 1

        for row in rows:
            if not isinstance(row, Mapping):
                invalid_rows += 1
                continue
            competition = str(row.get("competition") or "").strip().casefold()
            home = str(row.get("home_team") or "").strip().casefold()
            away = str(row.get("away_team") or "").strip().casefold()
            kickoff = _timestamp(row.get("kickoff_at"))
            predicted_at = _timestamp(row.get("predicted_at"))
            scored = _score_outcome(row.get("score"))
            predicted = str(row.get("predicted_outcome") or "").strip().casefold()
            actual = str(row.get("actual_outcome") or "").strip().casefold()
            correct = row.get("correct")
            if (
                not all((competition, home, away))
                or kickoff is None
                or predicted_at is None
                or predicted_at >= kickoff
                or scored is None
                or predicted not in _OUTCOMES
                or actual not in _OUTCOMES
                or actual != scored[0]
                or not isinstance(correct, bool)
                or correct != (predicted == actual)
            ):
                invalid_rows += 1
                continue
            identity = (
                competition,
                kickoff.isoformat(),
                home,
                away,
            )
            fixtures.setdefault(identity, []).append({
                "predicted_at": predicted_at,
                "actual_outcome": actual,
                "score": scored[1],
                "predicted_outcome": predicted,
                "correct": correct,
            })

    selected: list[dict[str, Any]] = []
    ambiguous = 0
    duplicate_rows = 0
    for observations in fixtures.values():
        if len(observations) > 1:
            duplicate_rows += len(observations) - 1
        result_pairs = {(row["actual_outcome"], row["score"]) for row in observations}
        if len(result_pairs) != 1:
            ambiguous += 1
            continue
        # Use the latest valid forecast captured before kickoff for each fixture.
        selected.append(max(observations, key=lambda row: row["predicted_at"]))

    count = len(selected)
    correct_count = sum(row["correct"] for row in selected)
    sufficient = count >= minimum_verified_fixtures
    load_errors = (archive_load_audit or {}).get("load_errors") or []
    summary = {
        "reports_scanned": len(reports),
        "archive_files_found": int((archive_load_audit or {}).get("files_found") or len(reports)),
        "archive_load_errors": len(load_errors),
        "history_rows_received": history_rows,
        "valid_history_rows": history_rows - invalid_rows,
        "invalid_history_rows": invalid_rows,
        "duplicate_snapshot_rows": duplicate_rows,
        "ambiguous_fixtures_excluded": ambiguous,
        "unique_verified_fixtures": count,
        "minimum_verified_fixtures": minimum_verified_fixtures,
        "fixtures_remaining_to_minimum": max(0, minimum_verified_fixtures - count),
        "report_count_mismatches": count_mismatches,
        "sample_status": (
            "sample_sufficient_descriptive_only" if sufficient else "insufficient_sample"
        ),
    }
    interval = _wilson_interval(correct_count, count)
    return {
        "summary": summary,
        "metrics": {
            "correct_predictions": correct_count,
            "accuracy_pct": round(correct_count / count * 100, 2) if count else None,
            "accuracy_95pct_wilson_interval": interval,
        },
        "fixtures": [
            {
                "actual_outcome": row["actual_outcome"],
                "predicted_outcome": row["predicted_outcome"],
                "correct": row["correct"],
                "predicted_at": row["predicted_at"].isoformat(),
                "score": f"{row['score'][0]}-{row['score'][1]}",
            }
            for row in sorted(selected, key=lambda item: item["predicted_at"])
        ],
        "historical_validation_passed": False,
        "provider_priority_modified": False,
        "prediction_weights_modified": False,
        "note": (
            "A sufficient sample is descriptive evidence only. It does not establish "
            "causality, calibration, provider superiority or permission to tune the model. "
            "Archived reports are deduplicated and only pre-kickoff forecasts with "
            "score-consistent outcomes are counted."
        ),
    }
