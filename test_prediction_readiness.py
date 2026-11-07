import unittest
from datetime import datetime, timezone

from prediction_readiness import build_prediction_readiness


def profile(name, count):
    matches = [
        {"statistics": {"Ball Possession": 50}, "opponent_strength": 60}
        for _ in range(count)
    ]
    return {
        "name": name,
        "matches": matches,
        "data_quality": {"matches_returned": count},
        "tactical_summary": {
            "playing_style": 50,
            "defensive_structure": None,
            "attacking_approach": 40,
        },
        "availability": {"injury_data_available": False},
        "lineups": {"lineups_available": False},
    }


def fixture():
    return {
        "id": 123,
        "season_id": 2026,
        "starting_at_timestamp": int(datetime(2026, 11, 8, 15, tzinfo=timezone.utc).timestamp()),
        "state": {"short_name": "NS", "name": "Not Started"},
        "updated_at": None,
        "participants": [
            {"id": 10, "name": "Home FC", "meta": {"location": "home"}},
            {"id": 20, "name": "Away FC", "meta": {"location": "away"}},
        ],
    }


class PredictionReadinessTests(unittest.TestCase):
    NOW = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)

    def report(self, home_count=10, away_count=10, selected_fixture=None):
        return build_prediction_readiness(
            profile("Home FC", home_count),
            profile("Away FC", away_count),
            selected_fixture=selected_fixture,
            home_team_id=10,
            away_team_id=20,
            season_id=2026,
            now=self.NOW,
        )

    def test_ready_requires_exact_fixture_and_ten_matches_each(self):
        report = self.report(selected_fixture=fixture())
        self.assertEqual(report["overall_status"], "ready")
        self.assertTrue(report["fixture"]["verified"])
        self.assertTrue(report["ten_match_history_target_met"])

    def test_five_to_nine_matches_is_limited_history(self):
        report = self.report(7, 9, fixture())
        self.assertEqual(report["overall_status"], "limited_history")
        self.assertTrue(report["prediction_minimum_history_met"])
        self.assertFalse(report["ten_match_history_target_met"])

    def test_history_collection_diagnostics_are_exposed_per_team(self):
        home = profile("Home FC", 7)
        home["data_quality"].update({
            "fixtures_scanned": 38,
            "same_season_fixtures": 38,
            "team_fixtures": 12,
            "completed_fixtures": 9,
            "fixtures_with_valid_scores": 7,
            "excluded_missing_scores": 2,
            "history_shortfall": 3,
        })
        report = build_prediction_readiness(
            home, profile("Away FC", 10), selected_fixture=fixture(),
            home_team_id=10, away_team_id=20, season_id=2026, now=self.NOW,
        )
        diagnostics = report["teams"]["home"]["history_collection_diagnostics"]
        self.assertEqual(diagnostics["completed_fixtures"], 9)
        self.assertEqual(diagnostics["fixtures_with_valid_scores"], 7)
        self.assertEqual(diagnostics["history_shortfall"], 3)

    def test_integrity_diagnostics_are_exposed(self):
        home = profile("Home FC", 9)
        home["data_quality"].update({
            "duplicate_fixture_id_count": 1,
            "duplicate_fixture_ids": [999],
            "excluded_invalid_kickoff": 1,
            "excluded_invalid_scores": 1,
            "team_fixture_accounting_gap": 0,
            "team_fixture_accounting_status": "balanced",
            "statistics_core_metrics": ["Ball Possession", "Passes %"],
            "statistics_coverage_by_metric": {"Ball Possession": 8, "Passes %": 6},
            "matches_with_any_statistics": 9,
            "matches_with_complete_core_statistics": 6,
            "core_statistics_completeness_pct": 77.8,
            "history_integrity_status": "issues_detected",
        })
        report = build_prediction_readiness(
            home, profile("Away FC", 9), selected_fixture=fixture(),
            home_team_id=10, away_team_id=20, season_id=2026, now=self.NOW,
        )
        diagnostics = report["teams"]["home"]["history_collection_diagnostics"]
        self.assertEqual(diagnostics["duplicate_fixture_id_count"], 1)
        self.assertEqual(diagnostics["history_integrity_status"], "issues_detected")
        self.assertEqual(diagnostics["core_statistics_completeness_pct"], 77.8)

    def test_history_order_and_collection_timestamp_are_exposed(self):
        home = profile("Home FC", 9)
        home["data_quality"].update({
            "history_latest_match_at": "2026-11-01T15:00:00Z",
            "history_oldest_match_at": "2026-09-01T15:00:00Z",
            "history_collection_fetched_at": "2026-11-07T12:00:00+00:00",
            "history_order": "newest_first_by_parsed_utc_kickoff",
        })
        report = build_prediction_readiness(
            home, profile("Away FC", 9), selected_fixture=fixture(),
            home_team_id=10, away_team_id=20, season_id=2026, now=self.NOW,
        )
        diagnostics = report["teams"]["home"]["history_collection_diagnostics"]
        self.assertEqual(diagnostics["history_order"], "newest_first_by_parsed_utc_kickoff")
        self.assertEqual(diagnostics["history_latest_match_at"], "2026-11-01T15:00:00Z")
        self.assertEqual(
            diagnostics["history_collection_fetched_at"],
            "2026-11-07T12:00:00+00:00",
        )

    def test_missing_exact_fixture_is_reported_not_substituted(self):
        report = self.report(selected_fixture=None)
        self.assertEqual(report["overall_status"], "fixture_unverified")
        self.assertFalse(report["fixture"]["verified"])

    def test_sportmonks_scheduled_state_id_is_accepted_without_state_label(self):
        row = fixture()
        row["state"] = {}
        row["state_id"] = 1
        report = self.report(selected_fixture=row)
        self.assertTrue(report["fixture"]["verified"])
        self.assertEqual(report["overall_status"], "ready")

    def test_non_scheduled_state_id_fails_closed(self):
        row = fixture()
        row["state"] = {}
        row["state_id"] = 5
        report = self.report(selected_fixture=row)
        self.assertFalse(report["fixture"]["verified"])
        self.assertEqual(report["overall_status"], "fixture_unverified")

    def test_wrong_home_away_orientation_fails_closed(self):
        row = fixture()
        row["participants"][0]["meta"]["location"] = "away"
        row["participants"][1]["meta"]["location"] = "home"
        report = self.report(selected_fixture=row)
        self.assertFalse(report["fixture"]["verified"])
        self.assertEqual(report["overall_status"], "fixture_unverified")

    def test_wrong_season_fails_closed(self):
        row = fixture()
        row["season_id"] = 2025
        report = self.report(selected_fixture=row)
        self.assertFalse(report["fixture"]["verified"])

    def test_past_kickoff_fails_closed(self):
        row = fixture()
        row["starting_at_timestamp"] = int(datetime(2026, 11, 6, tzinfo=timezone.utc).timestamp())
        report = self.report(selected_fixture=row)
        self.assertFalse(report["fixture"]["verified"])

    def test_under_five_matches_is_insufficient(self):
        report = self.report(4, 10, fixture())
        self.assertEqual(report["overall_status"], "insufficient_history")
        self.assertFalse(report["prediction_minimum_history_met"])

    def test_unknown_availability_and_lineups_stay_unknown(self):
        report = self.report(selected_fixture=fixture())
        home = report["teams"]["home"]
        self.assertEqual(home["player_availability_evidence"], "unknown")
        self.assertEqual(home["confirmed_lineup_evidence"], "unknown")
        self.assertFalse(home["tactical_components_available"]["defensive_structure"])


if __name__ == "__main__":
    unittest.main()
