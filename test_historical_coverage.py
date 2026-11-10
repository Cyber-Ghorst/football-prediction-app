import json
import tempfile
import unittest
from pathlib import Path

from historical_coverage import (
    build_historical_coverage_validation,
    load_archived_performance_reports,
)


def _row(predicted_at="2026-11-01T10:00:00Z", predicted="home", score="2-1"):
    actual = "home" if score == "2-1" else "draw"
    return {
        "competition": "Premier League",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "kickoff_at": "2026-11-01T12:00:00Z",
        "predicted_at": predicted_at,
        "score": score,
        "predicted_outcome": predicted,
        "actual_outcome": actual,
        "correct": predicted == actual,
    }


class HistoricalCoverageTests(unittest.TestCase):
    def test_archived_snapshots_deduplicate_same_fixture(self):
        row = _row()
        reports = [
            {"completed_pre_match_predictions": 1, "model": {"matches": 1}, "performance_history": [row]},
            {"completed_pre_match_predictions": 1, "model": {"matches": 1}, "performance_history": [row]},
        ]
        report = build_historical_coverage_validation(reports)
        self.assertEqual(report["summary"]["reports_scanned"], 2)
        self.assertEqual(report["summary"]["history_rows_received"], 2)
        self.assertEqual(report["summary"]["duplicate_snapshot_rows"], 1)
        self.assertEqual(report["summary"]["unique_verified_fixtures"], 1)

    def test_latest_valid_pre_kickoff_forecast_is_selected(self):
        earlier = _row(predicted_at="2026-11-01T09:00:00Z", predicted="away")
        later = _row(predicted_at="2026-11-01T11:00:00Z", predicted="home")
        report = build_historical_coverage_validation([
            {"performance_history": [earlier]},
            {"performance_history": [later]},
        ])
        self.assertEqual(report["summary"]["unique_verified_fixtures"], 1)
        self.assertTrue(report["fixtures"][0]["correct"])
        self.assertEqual(report["fixtures"][0]["predicted_at"], "2026-11-01T11:00:00+00:00")

    def test_invalid_or_leaking_rows_are_excluded(self):
        late = _row(predicted_at="2026-11-01T12:00:00Z")
        mismatch = _row()
        mismatch["actual_outcome"] = "draw"
        report = build_historical_coverage_validation([
            {"performance_history": [late, mismatch]}
        ])
        self.assertEqual(report["summary"]["invalid_history_rows"], 2)
        self.assertEqual(report["summary"]["unique_verified_fixtures"], 0)

    def test_conflicting_archived_scores_exclude_fixture(self):
        first = _row(score="2-1")
        second = _row(score="1-1", predicted="draw")
        report = build_historical_coverage_validation([
            {"performance_history": [first]},
            {"performance_history": [second]},
        ])
        self.assertEqual(report["summary"]["ambiguous_fixtures_excluded"], 1)
        self.assertEqual(report["summary"]["unique_verified_fixtures"], 0)

    def test_sample_threshold_is_descriptive_only(self):
        rows = []
        for index in range(30):
            row = _row()
            row["home_team"] = f"Home {index}"
            row["away_team"] = f"Away {index}"
            row["kickoff_at"] = f"2026-11-{(index % 28) + 1:02d}T12:00:00Z"
            rows.append(row)
        report = build_historical_coverage_validation(
            [{"performance_history": rows}]
        )
        self.assertEqual(report["summary"]["sample_status"], "sample_sufficient_descriptive_only")
        self.assertFalse(report["historical_validation_passed"])
        self.assertFalse(report["provider_priority_modified"])
        self.assertFalse(report["prediction_weights_modified"])

    def test_report_count_mismatches_are_visible(self):
        report = build_historical_coverage_validation([
            {"completed_pre_match_predictions": 2, "performance_history": [_row()]}
        ])
        self.assertEqual(report["summary"]["report_count_mismatches"], 1)

    def test_archive_loader_reports_bad_files_without_aborting(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.json"
            bad = Path(tmp) / "bad.json"
            good.write_text(json.dumps({"performance_history": [_row()]}), encoding="utf-8")
            bad.write_text("{not json", encoding="utf-8")
            reports, audit = load_archived_performance_reports(tmp)
            self.assertEqual(len(reports), 1)
            self.assertEqual(audit["files_found"], 2)
            self.assertEqual(len(audit["load_errors"]), 1)

    def test_empty_archive_is_insufficient_not_successful(self):
        report = build_historical_coverage_validation([])
        self.assertEqual(report["summary"]["sample_status"], "insufficient_sample")
        self.assertIsNone(report["metrics"]["accuracy_pct"])

    def test_invalid_minimum_is_rejected(self):
        for value in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                build_historical_coverage_validation([], minimum_verified_fixtures=value)


if __name__ == "__main__":
    unittest.main()
