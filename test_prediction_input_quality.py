import unittest
from datetime import datetime, timezone, timedelta

from prediction_input_quality import build_prediction_input_quality_report


NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def profile(team_id, name):
    return {
        "id": team_id,
        "name": name,
        "matches": [
            {
                "fixture_id": f"{team_id}-{index}",
                "date": (NOW - timedelta(days=index + 1)).isoformat(),
                "goals_for": index % 3,
                "goals_against": (index + 1) % 3,
            }
            for index in range(6)
        ],
        "data_quality": {"matches_returned": 6, "season_id": 2026, "history_collection_fetched_at": NOW.isoformat()},
    }


class PredictionInputQualityTests(unittest.TestCase):
    def setUp(self):
        self.home = profile(10, "Arsenal")
        self.away = profile(20, "Chelsea")

    def report(self):
        return build_prediction_input_quality_report(
            self.home, self.away, home_team_id=10, away_team_id=20, now=NOW
        )

    def test_valid_history_passes_without_requiring_optional_statistics(self):
        result = self.report()
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["prediction_allowed"])
        self.assertFalse(result["prediction_inputs_modified"])

    def test_wrong_profile_team_id_blocks_prediction(self):
        self.home["id"] = 99
        result = self.report()
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["prediction_allowed"])

    def test_duplicate_fixture_id_blocks_prediction(self):
        self.home["matches"][1]["fixture_id"] = self.home["matches"][0]["fixture_id"]
        self.assertFalse(self.report()["prediction_allowed"])

    def test_boolean_fractional_negative_and_missing_scores_block_prediction(self):
        for value in (True, 1.5, -1, None, "bad"):
            with self.subTest(value=value):
                self.home = profile(10, "Arsenal")
                self.home["matches"][0]["goals_for"] = value
                self.assertFalse(self.report()["prediction_allowed"])

    def test_missing_fixture_id_blocks_prediction(self):
        self.home["matches"][0]["fixture_id"] = None
        self.assertFalse(self.report()["prediction_allowed"])

    def test_missing_or_invalid_kickoff_blocks_prediction(self):
        for value in (None, "not-a-date"):
            with self.subTest(value=value):
                self.home = profile(10, "Arsenal")
                self.home["matches"][0]["date"] = value
                self.assertFalse(self.report()["prediction_allowed"])

    def test_future_dated_history_blocks_prediction(self):
        self.home["matches"][0]["date"] = (NOW + timedelta(minutes=1)).isoformat()
        self.assertFalse(self.report()["prediction_allowed"])

    def test_out_of_order_history_blocks_recency_weighting(self):
        self.home["matches"][0], self.home["matches"][1] = (
            self.home["matches"][1], self.home["matches"][0]
        )
        self.assertFalse(self.report()["prediction_allowed"])

    def test_insufficient_history_blocks_prediction(self):
        self.home["matches"] = self.home["matches"][:4]
        self.home["data_quality"]["matches_returned"] = 4
        self.assertFalse(self.report()["prediction_allowed"])

    def test_reported_count_mismatch_blocks_prediction(self):
        self.home["data_quality"]["matches_returned"] = 10
        self.assertFalse(self.report()["prediction_allowed"])

    def test_upstream_exclusions_are_warning_if_retained_history_is_clean(self):
        self.home["data_quality"]["history_integrity_status"] = "issues_detected"
        result = self.report()
        self.assertTrue(result["prediction_allowed"])
        self.assertEqual(result["status"], "attention")
        self.assertTrue(result["warnings"])

    def test_conflicting_statistics_are_excluded_and_reported_as_warning(self):
        self.home["matches"][0]["statistics_conflicts"] = [
            {"canonical_name": "Total Shots", "reason": "conflicting_duplicate_observations"}
        ]
        result = self.report()
        self.assertTrue(result["prediction_allowed"])
        self.assertEqual(result["status"], "attention")
        self.assertTrue(any("conflicting" in warning for warning in result["warnings"]))

    def test_missing_season_metadata_is_warning_not_silent_assumption(self):
        self.home["data_quality"].pop("season_id")
        result = self.report()
        self.assertTrue(result["prediction_allowed"])
        self.assertEqual(result["status"], "attention")

    def test_naive_timestamp_is_treated_as_utc_and_timezone_order_is_checked(self):
        self.home["matches"][0]["date"] = "2026-11-09T12:00:00+03:00"
        self.home["matches"][1]["date"] = "2026-11-09T12:30:00Z"
        result = self.report()
        self.assertFalse(result["prediction_allowed"])

    def test_invalid_minimum_is_rejected(self):
        for value in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                build_prediction_input_quality_report(
                    self.home, self.away, home_team_id=10, away_team_id=20,
                    minimum_matches=value, now=NOW,
                )

    def test_stale_history_collection_blocks_prediction(self):
        self.home["data_quality"]["history_collection_fetched_at"] = (
            NOW - timedelta(hours=25)
        ).isoformat()
        result = self.report()
        self.assertFalse(result["prediction_allowed"])
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("older than 24 hours" in failure for failure in result["failures"]))

    def test_fresh_history_collection_passes(self):
        self.home["data_quality"]["history_collection_fetched_at"] = (
            NOW - timedelta(hours=2)
        ).isoformat()
        result = self.report()
        self.assertTrue(result["prediction_allowed"])
        self.assertEqual(result["status"], "passed")

    def test_missing_history_collection_timestamp_downgrades_readiness(self):
        self.home["data_quality"].pop("history_collection_fetched_at")
        result = self.report()
        self.assertTrue(result["prediction_allowed"])
        self.assertEqual(result["status"], "attention")
        self.assertTrue(any("freshness cannot be confirmed" in warning for warning in result["warnings"]))

    def test_future_history_collection_timestamp_blocks_prediction(self):
        self.home["data_quality"]["history_collection_fetched_at"] = (
            NOW + timedelta(minutes=1)
        ).isoformat()
        self.assertFalse(self.report()["prediction_allowed"])

    def test_stale_verified_fixture_blocks_fixture_specific_prediction(self):
        result = build_prediction_input_quality_report(
            self.home, self.away, home_team_id=10, away_team_id=20,
            now=NOW,
            fixture_readiness={"verified": True, "source_freshness": "stale"},
        )
        self.assertFalse(result["prediction_allowed"])
        self.assertEqual(result["status"], "blocked")

    def test_unknown_fixture_freshness_downgrades_but_does_not_block_matchup_analysis(self):
        result = build_prediction_input_quality_report(
            self.home, self.away, home_team_id=10, away_team_id=20,
            now=NOW,
            fixture_readiness={"verified": True, "source_freshness": "unknown"},
        )
        self.assertTrue(result["prediction_allowed"])
        self.assertEqual(result["status"], "attention")

    def test_unresolved_statistics_conflicts_downgrade_without_imputation(self):
        self.home["matches"][0]["statistics_conflicts"] = [
            {"canonical_name": "Total Shots", "reason": "unresolved"}
        ]
        result = self.report()
        self.assertTrue(result["prediction_allowed"])
        self.assertEqual(result["status"], "attention")
        self.assertFalse(result["prediction_inputs_modified"])


if __name__ == "__main__":
    unittest.main()
