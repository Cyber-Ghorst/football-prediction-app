import unittest
from prediction_evaluation import (
    build_prediction_record, evaluate_prediction_ledger,
    merge_prediction_records, outcome_from_score,
)


class PredictionEvaluationTests(unittest.TestCase):
    def _record(self, **overrides):
        args = dict(
            competition="Premier League", country="England", season=2026,
            home_team="Arsenal", away_team="Chelsea",
            probabilities={"home_win": 60, "draw": 25, "away_win": 15},
            predicted_at="2026-11-07T10:00:00+00:00",
            kickoff_at="2026-11-07T12:00:00+00:00",
            opta_probabilities={"home_win": 55, "draw": 25, "away_win": 20},
            opta_source_url="https://theanalyst.com/example",
            opta_captured_at="2026-11-07T09:00:00+00:00",
            player_snapshot={"fetched_at": "2026-11-07T09:30:00+00:00",
                             "availability": "collected",
                             "players": [{"id": 1}], "unknown_players": []},
        )
        args.update(overrides)
        return build_prediction_record(**args)

    def test_prediction_and_player_snapshot_must_precede_kickoff(self):
        row = self._record()
        self.assertTrue(row["prediction_before_kickoff"])
        self.assertTrue(row["player_snapshot_before_kickoff"])
        self.assertIn('"id":1', row["player_snapshot_players_json"])
        late = self._record(predicted_at="2026-11-07T13:00:00+00:00")
        self.assertFalse(late["prediction_before_kickoff"])

    def test_team_only_statistics_are_not_mislabeled_as_player_snapshots(self):
        row = self._record(player_snapshot={
            "fetched_at": "2026-11-07T09:30:00+00:00",
            "availability": "unknown_no_matching_player_statistics",
            "players": [],
            "teams": {"home": {"season_statistics": [{"total": {"games": 10}}]}},
        })
        self.assertFalse(row["player_snapshot_before_kickoff"])
        self.assertTrue(row["team_snapshot_before_kickoff"])
        report = evaluate_prediction_ledger([row])
        self.assertEqual(report["player_snapshots_pre_kickoff"], 0)
        self.assertEqual(report["team_snapshots_pre_kickoff"], 1)

    def test_missing_player_data_is_not_counted_as_a_snapshot(self):
        row = self._record(player_snapshot={"fetched_at": "2026-11-07T09:30:00+00:00",
                                             "availability": "unknown_no_exact_provider_lineup"})
        self.assertFalse(row["player_snapshot_before_kickoff"])

    def test_post_kickoff_player_snapshot_is_excluded(self):
        row = self._record(player_snapshot={"fetched_at": "2026-11-07T13:00:00+00:00",
                                             "players": [{"id": 1}]})
        self.assertFalse(row["player_snapshot_before_kickoff"])

    def test_model_and_opta_scored_on_same_fixture_subset(self):
        row = self._record()
        row.update(actual_home_goals="2", actual_away_goals="0")
        report = evaluate_prediction_ledger([row])
        self.assertEqual(report["model"]["matches"], 1)
        self.assertEqual(report["opta_same_fixtures"]["matches"], 1)
        self.assertEqual(report["opta_comparable_fixtures"], 1)
        self.assertEqual(report["model_metrics_by_competition"]["Premier League"]["matches"], 1)
        self.assertGreater(report["model"]["accuracy_pct"], 0)

    def test_late_predictions_are_not_scored(self):
        row = self._record(predicted_at="2026-11-07T13:00:00+00:00")
        row.update(actual_home_goals="2", actual_away_goals="0")
        report = evaluate_prediction_ledger([row])
        self.assertEqual(report["completed_pre_match_predictions"], 0)

    def test_invalid_probability_sum_is_rejected(self):
        with self.assertRaises(ValueError):
            self._record(probabilities={"home_win": 60, "draw": 20, "away_win": 10})

    def test_opta_captured_after_kickoff_is_excluded(self):
        row = self._record(opta_captured_at="2026-11-07T13:00:00+00:00")
        row.update(actual_home_goals="2", actual_away_goals="0")
        report = evaluate_prediction_ledger([row])
        self.assertEqual(report["opta_comparable_fixtures"], 0)

    def test_missing_opta_is_not_scored_or_penalized(self):
        row = self._record(opta_probabilities=None)
        row.update(actual_home_goals="0", actual_away_goals="0")
        report = evaluate_prediction_ledger([row])
        self.assertEqual(report["opta_comparable_fixtures"], 0)
        self.assertEqual(report["opta_same_fixtures"]["matches"], 0)

    def test_nan_probabilities_are_rejected(self):
        with self.assertRaises(ValueError):
            self._record(probabilities={"home_win": float("nan"), "draw": 25, "away_win": 15})

    def test_outcome_and_merge(self):
        self.assertEqual(outcome_from_score(1, 1), "draw")
        first = self._record()
        enriched = dict(first, actual_home_goals="1", actual_away_goals="0")
        merged = merge_prediction_records([first], [enriched])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["actual_home_goals"], "1")


if __name__ == "__main__":
    unittest.main()
