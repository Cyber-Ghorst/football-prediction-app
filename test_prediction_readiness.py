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

    def report(self, home_count=10, away_count=10, selected_fixture=None, exact_pairing_fixture=None):
        return build_prediction_readiness(
            profile("Home FC", home_count),
            profile("Away FC", away_count),
            selected_fixture=selected_fixture,
            home_team_id=10,
            away_team_id=20,
            season_id=2026,
            now=self.NOW,
            exact_pairing_fixture=exact_pairing_fixture,
        )

    def test_ready_requires_exact_fixture_and_ten_matches_each(self):
        report = self.report(selected_fixture=fixture())
        self.assertEqual(report["overall_status"], "ready")
        self.assertTrue(report["fixture"]["verified"])
        self.assertTrue(report["ten_match_history_target_met"])

    def test_sportmonks_state_id_one_verifies_future_fixture_without_state_object(self):
        row = fixture()
        row.pop("state")
        row["state_id"] = 1
        report = self.report(selected_fixture=row)
        self.assertTrue(report["fixture"]["verified"])
        self.assertEqual(report["overall_status"], "ready")

    def test_string_status_fallback_verifies_future_fixture(self):
        row = fixture()
        row.pop("state")
        row["status"] = "NS"
        report = self.report(selected_fixture=row)
        self.assertTrue(report["fixture"]["verified"])

    def test_live_sportmonks_state_id_does_not_verify_upcoming_fixture(self):
        row = fixture()
        row.pop("state")
        row["state_id"] = 2
        report = self.report(selected_fixture=row)
        self.assertFalse(report["fixture"]["verified"])
        self.assertEqual(report["overall_status"], "fixture_unverified")
        self.assertIn("fixture state is not confirmed as scheduled", report["fixture"]["reason"])

    def test_fixture_fetch_age_is_reported_without_freshness_threshold(self):
        row = fixture()
        row["fixture_details_fetched_at"] = "2026-11-07T11:30:00+00:00"
        report = self.report(selected_fixture=row)
        self.assertEqual(report["fixture"]["source_fetched_at"], "2026-11-07T11:30:00+00:00")
        self.assertEqual(report["fixture"]["source_age_seconds"], 1800.0)
        self.assertEqual(report["fixture"]["source_age_minutes"], 30.0)
        self.assertEqual(report["fixture"]["source_freshness"], "fresh")
        self.assertIn("less than 24 hours", report["fixture"]["freshness_note"])

    def test_fixture_retrieved_just_under_24_hours_is_fresh(self):
        row = fixture()
        row["fixture_details_fetched_at"] = "2026-11-06T12:00:01+00:00"
        report = self.report(selected_fixture=row)
        self.assertEqual(report["fixture"]["source_freshness"], "fresh")

    def test_fixture_retrieved_exactly_24_hours_ago_is_stale(self):
        row = fixture()
        row["fixture_details_fetched_at"] = "2026-11-06T12:00:00+00:00"
        report = self.report(selected_fixture=row)
        self.assertEqual(report["fixture"]["source_age_seconds"], 86400.0)
        self.assertEqual(report["fixture"]["source_freshness"], "stale")
        self.assertIn("24 hours ago or earlier", report["fixture"]["freshness_note"])

    def test_future_fixture_retrieval_timestamp_is_unknown(self):
        row = fixture()
        row["fixture_details_fetched_at"] = "2026-11-07T12:00:01+00:00"
        report = self.report(selected_fixture=row)
        self.assertEqual(report["fixture"]["source_freshness"], "unknown")
        self.assertIn("later than the diagnostic clock", report["fixture"]["freshness_note"])

    def test_fixture_fetch_age_stays_unknown_when_timestamp_missing(self):
        report = self.report(selected_fixture=fixture())
        self.assertIsNone(report["fixture"]["source_fetched_at"])
        self.assertIsNone(report["fixture"]["source_age_seconds"])
        self.assertEqual(report["fixture"]["source_freshness"], "unknown")

    def test_five_to_nine_matches_are_prediction_eligible_with_limited_label(self):
        report = self.report(7, 9, fixture())
        self.assertEqual(report["overall_status"], "limited_history")
        self.assertTrue(report["prediction_minimum_history_met"])
        self.assertFalse(report["ten_match_history_target_met"])
        self.assertTrue(report["prediction_allowed_by_history"])
        self.assertEqual(report["history_policy"]["minimum_matches_per_team"], 5)
        self.assertTrue(report["history_policy"]["target_is_advisory"])

    def test_exactly_five_matches_meets_minimum_for_both_teams(self):
        report = self.report(5, 5, fixture())
        self.assertEqual(report["overall_status"], "limited_history")
        self.assertTrue(report["prediction_allowed_by_history"])

    def test_four_matches_still_blocks_history_eligibility(self):
        report = self.report(4, 10, fixture())
        self.assertFalse(report["prediction_allowed_by_history"])

    def test_missing_exact_fixture_is_reported_not_substituted(self):
        report = self.report(selected_fixture=None)
        self.assertEqual(report["overall_status"], "fixture_unverified")
        self.assertFalse(report["fixture"]["verified"])

    def test_past_exact_pairing_is_distinguished_from_missing_fixture(self):
        past = fixture()
        past["starting_at_timestamp"] = int(datetime(2026, 11, 6, tzinfo=timezone.utc).timestamp())
        report = self.report(selected_fixture=None, exact_pairing_fixture=past)
        self.assertEqual(report["fixture"]["status"], "past_fixture")
        self.assertFalse(report["fixture"]["verified"])
        self.assertEqual(report["fixture"]["fixture_id"], 123)
        self.assertIn("kickoff has already passed", report["fixture"]["reason"])
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
