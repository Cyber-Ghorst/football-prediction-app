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

    def test_evaluator_recomputes_pre_kickoff_status_instead_of_trusting_csv_flag(self):
        row = self._record()
        row["prediction_before_kickoff"] = True
        row["predicted_at"] = "2026-11-07T13:00:00+00:00"
        row.update(actual_home_goals="2", actual_away_goals="0")
        report = evaluate_prediction_ledger([row])
        self.assertEqual(report["pre_match_predictions"], 0)
        self.assertEqual(report["completed_pre_match_predictions"], 0)

    def test_repeated_fixture_predictions_count_once_using_latest_pre_match_row(self):
        earlier = self._record()
        later = dict(earlier)
        later["record_id"] = "later-record"
        later["predicted_at"] = "2026-11-07T11:00:00+00:00"
        later["model_home_win"] = 20
        later["model_draw"] = 30
        later["model_away_win"] = 50
        earlier.update(actual_home_goals="2", actual_away_goals="0")
        later.update(actual_home_goals="2", actual_away_goals="0")
        report = evaluate_prediction_ledger([earlier, later])
        self.assertEqual(report["pre_match_prediction_records"], 2)
        self.assertEqual(report["pre_match_predictions"], 1)
        self.assertEqual(report["duplicate_records_excluded"], 1)
        self.assertEqual(report["model"]["matches"], 1)
        self.assertEqual(report["model"]["accuracy_pct"], 0.0)
        self.assertEqual(len(report["performance_history"]), 1)
        self.assertEqual(report["performance_history"][0]["predicted_outcome"], "away")
        self.assertFalse(report["performance_history"][0]["correct"])

    def test_performance_history_contains_only_completed_pre_match_fixtures(self):
        valid = self._record(fixture_id="fixture-1", fixture_provider="sportmonks")
        valid.update(actual_home_goals="2", actual_away_goals="0")
        late = self._record(
            home_team="Liverpool", away_team="Everton",
            predicted_at="2026-11-07T13:00:00+00:00",
            fixture_id="fixture-2", fixture_provider="sportmonks",
        )
        late.update(actual_home_goals="0", actual_away_goals="1")

        report = evaluate_prediction_ledger([valid, late])
        history = report["performance_history"]

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["home_team"], "Arsenal")
        self.assertEqual(history[0]["score"], "2-0")
        self.assertEqual(history[0]["actual_outcome"], "home")
        self.assertEqual(history[0]["predicted_outcome"], "home")
        self.assertTrue(history[0]["correct"])
        self.assertIsNotNone(history[0]["brier"])
        self.assertIsNotNone(history[0]["log_loss"])

    def test_snapshot_counts_recompute_timestamp_and_require_serialized_records(self):
        row = self._record()
        row["player_snapshot_before_kickoff"] = True
        row["player_snapshot_at"] = "2026-11-07T13:00:00+00:00"
        report = evaluate_prediction_ledger([row])
        self.assertEqual(report["player_snapshots_pre_kickoff"], 0)
        row["player_snapshot_at"] = "2026-11-07T09:30:00+00:00"
        row["player_snapshot_players_json"] = "[]"
        report = evaluate_prediction_ledger([row])
        self.assertEqual(report["player_snapshots_pre_kickoff"], 0)

    def test_eligibility_audit_explains_each_exclusion_reason(self):
        valid = self._record()
        missing_prediction_time = self._record()
        missing_prediction_time["predicted_at"] = ""
        missing_kickoff = self._record()
        missing_kickoff["kickoff_at"] = ""
        late = self._record(predicted_at="2026-11-07T13:00:00+00:00")
        invalid_probabilities = self._record()
        invalid_probabilities["model_home_win"] = 80
        records = [valid, missing_prediction_time, missing_kickoff, late, invalid_probabilities]

        audit = evaluate_prediction_ledger(records)["eligibility_audit"]

        self.assertEqual(audit["records_total"], 5)
        self.assertEqual(audit["valid_pre_kickoff_records"], 1)
        self.assertEqual(audit["missing_prediction_timestamp"], 1)
        self.assertEqual(audit["missing_kickoff_timestamp"], 1)
        self.assertEqual(audit["at_or_after_kickoff"], 1)
        self.assertEqual(audit["invalid_probabilities"], 1)
        self.assertEqual(
            sum(audit[key] for key in (
                "valid_pre_kickoff_records", "missing_prediction_timestamp",
                "missing_kickoff_timestamp", "at_or_after_kickoff",
                "invalid_probabilities",
            )),
            audit["records_total"],
        )

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
