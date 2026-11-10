import unittest

from prediction_evaluation import build_prediction_record, evaluate_tipmaster_benchmark


def _prediction(**changes):
    row = build_prediction_record(
        competition="Premier League",
        country="England",
        season=2026,
        home_team="Arsenal",
        away_team="Chelsea",
        fixture_id="sportmonks-123",
        fixture_provider="sportmonks",
        probabilities={"home_win": 60, "draw": 25, "away_win": 15},
        predicted_at="2026-11-10T10:00:00+00:00",
        kickoff_at="2026-11-10T20:00:00+00:00",
    )
    row.update({
        "actual_home_goals": 2,
        "actual_away_goals": 0,
        "actual_result_provider": "sportmonks",
        "actual_result_fixture_id": "sportmonks-123",
        "actual_result_verified_at": "2026-11-10T22:00:00+00:00",
        "actual_result_verification": "exact_fixture_team_competition_season_and_score",
    })
    row.update(changes)
    return row


def _benchmark(**changes):
    row = {
        "source": "tipmaster",
        "source_match_id": "national:123",
        "competition": "Premier League",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "kickoff_at": "2026-11-10T20:05:00+00:00",
        "prediction_locked_at": "2026-11-10T19:00:00+00:00",
        "prediction_inputs_eligible": False,
        "groups": {
            "top20": {"sample": 100, "shares": {"home": .8, "draw": .1, "away": .1}},
            "all": {"sample": 500, "shares": {"home": .7, "draw": .2, "away": .1}},
        },
    }
    row.update(changes)
    return row


class TipMasterBenchmarkEvaluationTests(unittest.TestCase):
    def test_scores_only_exactly_matched_verified_fixtures(self):
        report = evaluate_tipmaster_benchmark([_prediction()], [_benchmark()])
        self.assertEqual(report["matched_verified_fixtures"], 1)
        self.assertEqual(report["groups"]["top20"]["matches"], 1)
        self.assertAlmostEqual(report["groups"]["top20"]["distributional_brier"], .06)
        self.assertEqual(report["groups"]["top20"]["model_same_fixtures"]["matches"], 1)
        self.assertFalse(report["prediction_inputs_eligible"])

    def test_rejects_unverified_scores(self):
        row = _prediction(actual_result_verification="manual")
        report = evaluate_tipmaster_benchmark([row], [_benchmark()])
        self.assertEqual(report["completed_verified_model_fixtures"], 0)
        self.assertEqual(report["matched_verified_fixtures"], 0)

    def test_requires_pre_kickoff_prediction_and_benchmark_lock(self):
        late_prediction = _prediction(predicted_at="2026-11-10T20:00:00+00:00")
        report = evaluate_tipmaster_benchmark([late_prediction], [_benchmark()])
        self.assertEqual(report["matched_verified_fixtures"], 0)

        late_lock = _benchmark(prediction_locked_at="2026-11-10T20:06:00+00:00")
        report = evaluate_tipmaster_benchmark([_prediction()], [late_lock])
        self.assertEqual(report["invalid_benchmark_records_excluded"], 1)
        self.assertEqual(report["matched_verified_fixtures"], 0)

    def test_requires_team_competition_and_kickoff_match(self):
        for changes in (
            {"home_team": "Arsenal FC"},
            {"competition": "FA Cup"},
            {"kickoff_at": "2026-11-10T21:00:00+00:00"},
        ):
            report = evaluate_tipmaster_benchmark([_prediction()], [_benchmark(**changes)])
            self.assertEqual(report["matched_verified_fixtures"], 0)

    def test_ambiguous_multiple_matches_are_excluded(self):
        duplicate = _benchmark(source_match_id="national:124")
        report = evaluate_tipmaster_benchmark([_prediction()], [_benchmark(), duplicate])
        self.assertEqual(report["matched_verified_fixtures"], 0)
        self.assertEqual(report["ambiguous_fixture_matches_excluded"], 1)

    def test_duplicate_prediction_runs_use_latest_forecast(self):
        earlier = _prediction(predicted_at="2026-11-10T09:00:00+00:00")
        later = _prediction(predicted_at="2026-11-10T10:00:00+00:00")
        report = evaluate_tipmaster_benchmark([earlier, later], [_benchmark()])
        self.assertEqual(report["matched_verified_fixtures"], 1)
        self.assertEqual(report["groups"]["top20"]["matches"], 1)

    def test_invalid_benchmark_isolation_flag_is_rejected(self):
        row = _benchmark(prediction_inputs_eligible=True)
        report = evaluate_tipmaster_benchmark([_prediction()], [row])
        self.assertEqual(report["invalid_benchmark_records_excluded"], 1)
        self.assertEqual(report["matched_verified_fixtures"], 0)


if __name__ == "__main__":
    unittest.main()
