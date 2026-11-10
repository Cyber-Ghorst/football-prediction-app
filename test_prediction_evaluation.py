import unittest
from prediction_evaluation import (
    build_availability_snapshot, build_prediction_record,
    evaluate_prediction_ledger, merge_prediction_records, outcome_from_score,
)


class PredictionEvaluationTests(unittest.TestCase):
    def _record(self, **overrides):
        args = dict(
            competition="Premier League", country="England", season=2026,
            home_team="Arsenal", away_team="Chelsea", fixture_id="fixture-1", fixture_provider="sportmonks",
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

    def _verify_score(self, row, home_goals, away_goals):
        row.update(
            actual_home_goals=home_goals,
            actual_away_goals=away_goals,
            actual_result_provider="sportmonks",
            actual_result_fixture_id=str(row["fixture_id"]),
            actual_result_verified_at="2026-11-07T14:00:00+00:00",
            actual_result_verification="exact_fixture_team_competition_season_and_score",
        )
        return row

    def _availability_profile(self, team_id, name, fixture_id="fixture-1"):
        return {
            "name": name,
            "availability": {
                "source": "sportmonks",
                "fixture_id": fixture_id,
                "team_id": team_id,
                "season_id": 2026,
                "roster_complete": True,
                "sidelined_feed_available": True,
                "reported_sidelined_count": 0,
                "squad_players": [{
                    "player_id": team_id * 100,
                    "player_name": f"{name} Player",
                    "status": "available",
                    "importance": 100,
                    "minutes_played": 900,
                    "minutes_evidence_method": "sportmonks_minutes_played_type_119",
                }],
            },
            "player_availability_assessment": {"status": "scored", "score": 100.0},
        }

    def test_availability_snapshot_requires_exact_fixture_team_and_season(self):
        snapshot = build_availability_snapshot(
            home_profile=self._availability_profile(10, "Arsenal"),
            away_profile=self._availability_profile(20, "Chelsea"),
            fixture_id="fixture-1", season_id=2026,
            home_team_id=10, away_team_id=20,
            captured_at="2026-11-07T09:30:00+00:00",
        )
        self.assertEqual(snapshot["status"], "complete")
        self.assertEqual(snapshot["complete_teams"], 2)
        self.assertEqual(len(snapshot["players"]), 2)

        mismatched = build_availability_snapshot(
            home_profile=self._availability_profile(10, "Arsenal"),
            away_profile=self._availability_profile(20, "Chelsea", fixture_id="other-fixture"),
            fixture_id="fixture-1", season_id=2026,
            home_team_id=10, away_team_id=20,
            captured_at="2026-11-07T09:30:00+00:00",
        )
        self.assertEqual(mismatched["status"], "partial")
        self.assertEqual(mismatched["complete_teams"], 1)

    def test_complete_availability_snapshot_is_audited_only_before_kickoff(self):
        snapshot = build_availability_snapshot(
            home_profile=self._availability_profile(10, "Arsenal"),
            away_profile=self._availability_profile(20, "Chelsea"),
            fixture_id="fixture-1", season_id=2026,
            home_team_id=10, away_team_id=20,
            captured_at="2026-11-07T09:30:00+00:00",
        )
        row = self._record(availability_snapshot=snapshot)
        self.assertTrue(row["availability_snapshot_before_kickoff"])
        self.assertEqual(row["availability_snapshot_players_count"], 2)
        self.assertEqual(row["availability_snapshot_status"], "complete")

        late_snapshot = dict(snapshot)
        late_snapshot["captured_at"] = "2026-11-07T13:00:00+00:00"
        late = self._record(availability_snapshot=late_snapshot)
        self.assertFalse(late["availability_snapshot_before_kickoff"])

    def test_evaluation_counts_only_complete_pre_kickoff_availability_snapshots(self):
        complete = build_availability_snapshot(
            home_profile=self._availability_profile(10, "Arsenal"),
            away_profile=self._availability_profile(20, "Chelsea"),
            fixture_id="fixture-1", season_id=2026,
            home_team_id=10, away_team_id=20,
            captured_at="2026-11-07T09:30:00+00:00",
        )
        row = self._record(availability_snapshot=complete)
        self._verify_score(row, "2", "0")

        partial = build_availability_snapshot(
            home_profile=self._availability_profile(10, "Arsenal"),
            away_profile=self._availability_profile(20, "Chelsea", fixture_id="other"),
            fixture_id="fixture-1", season_id=2026,
            home_team_id=10, away_team_id=20,
            captured_at="2026-11-07T09:30:00+00:00",
        )
        other = self._record(
            home_team="Liverpool", away_team="Everton",
            fixture_id="fixture-2", availability_snapshot=partial,
        )
        self._verify_score(other, "1", "0")
        report = evaluate_prediction_ledger([row, other])
        self.assertEqual(report["availability_snapshots_pre_kickoff"], 1)
        self.assertEqual(
            report["availability_snapshot_coverage_by_competition"]["Premier League"],
            1,
        )

    def test_feature_snapshot_is_serialized_and_marked_pre_kickoff(self):
        import json

        features = {
            "schema_version": "prediction-features-v1",
            "captured_at": "2026-11-07T10:00:00+00:00",
            "teams": {"home": {"recent_matches": [{"goals_for": 2}]}, "away": {}},
            "calculated": {"model_weights": {"recent_form": 0.2}},
        }
        row = self._record(feature_snapshot=features)
        self.assertEqual(row["feature_snapshot_schema_version"], "prediction-features-v1")
        self.assertTrue(row["feature_snapshot_before_kickoff"])
        self.assertEqual(json.loads(row["feature_snapshot_json"]), features)

        late_features = dict(features, captured_at="2026-11-07T13:00:00+00:00")
        late = self._record(feature_snapshot=late_features)
        self.assertFalse(late["feature_snapshot_before_kickoff"])

    def test_feature_snapshot_is_immutable_when_same_record_is_merged(self):
        original = self._record(feature_snapshot={
            "schema_version": "prediction-features-v1",
            "captured_at": "2026-11-07T10:00:00+00:00",
            "calculated": {"home_rating": 61.0},
        })
        incoming = dict(original)
        incoming["feature_snapshot_json"] = '{"schema_version":"tampered"}'
        incoming["feature_snapshot_schema_version"] = "tampered"
        incoming["feature_snapshot_at"] = "2026-11-07T11:00:00+00:00"
        merged = merge_prediction_records([original], [incoming])[0]
        self.assertEqual(merged["feature_snapshot_json"], original["feature_snapshot_json"])
        self.assertEqual(merged["feature_snapshot_schema_version"], "prediction-features-v1")
        self.assertEqual(merged["feature_snapshot_at"], "2026-11-07T10:00:00+00:00")

    def test_non_finite_feature_snapshot_values_are_rejected(self):
        with self.assertRaises(ValueError):
            self._record(feature_snapshot={
                "schema_version": "prediction-features-v1",
                "captured_at": "2026-11-07T10:00:00+00:00",
                "invalid": float("nan"),
            })

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
        self._verify_score(row, "2", "0")
        report = evaluate_prediction_ledger([row])
        self.assertEqual(report["model"]["matches"], 1)
        self.assertEqual(report["opta_same_fixtures"]["matches"], 1)
        self.assertEqual(report["opta_comparable_fixtures"], 1)
        self.assertEqual(report["model_metrics_by_competition"]["Premier League"]["matches"], 1)
        self.assertGreater(report["model"]["accuracy_pct"], 0)

    def test_late_predictions_are_not_scored(self):
        row = self._record(predicted_at="2026-11-07T13:00:00+00:00")
        self._verify_score(row, "2", "0")
        report = evaluate_prediction_ledger([row])
        self.assertEqual(report["completed_pre_match_predictions"], 0)

    def test_evaluator_recomputes_pre_kickoff_status_instead_of_trusting_csv_flag(self):
        row = self._record()
        row["prediction_before_kickoff"] = True
        row["predicted_at"] = "2026-11-07T13:00:00+00:00"
        self._verify_score(row, "2", "0")
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
        self._verify_score(earlier, "2", "0")
        self._verify_score(later, "2", "0")
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
        self._verify_score(valid, "2", "0")
        late = self._record(
            home_team="Liverpool", away_team="Everton",
            predicted_at="2026-11-07T13:00:00+00:00",
            fixture_id="fixture-2", fixture_provider="sportmonks",
        )
        self._verify_score(late, "0", "1")

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

    def test_manual_or_unverified_scores_are_not_included_in_metrics(self):
        row = self._record()
        row.update(actual_home_goals="2", actual_away_goals="0")
        report = evaluate_prediction_ledger([row])
        self.assertEqual(report["completed_pre_match_predictions"], 0)
        self.assertEqual(report["unverified_score_records"], 1)
        self.assertEqual(report["model"]["matches"], 0)
        self.assertEqual(report["eligibility_audit"]["scores_present_but_unverified"], 1)

    def test_verified_score_must_match_the_saved_fixture_identity(self):
        row = self._record()
        self._verify_score(row, "2", "0")
        row["actual_result_fixture_id"] = "different-fixture"
        report = evaluate_prediction_ledger([row])
        self.assertEqual(report["completed_pre_match_predictions"], 0)
        self.assertEqual(report["unverified_score_records"], 1)

    def test_invalid_probability_sum_is_rejected(self):
        with self.assertRaises(ValueError):
            self._record(probabilities={"home_win": 60, "draw": 20, "away_win": 10})

    def test_opta_captured_after_kickoff_is_excluded(self):
        row = self._record(opta_captured_at="2026-11-07T13:00:00+00:00")
        self._verify_score(row, "2", "0")
        report = evaluate_prediction_ledger([row])
        self.assertEqual(report["opta_comparable_fixtures"], 0)

    def test_missing_opta_is_not_scored_or_penalized(self):
        row = self._record(opta_probabilities=None)
        self._verify_score(row, "0", "0")
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

    def test_top_outcome_calibration_uses_only_verified_pre_match_scores(self):
        valid = self._record()
        self._verify_score(valid, "2", "0")
        unverified = self._record(home_team="Liverpool", away_team="Everton", fixture_id="fixture-2")
        unverified.update(actual_home_goals="2", actual_away_goals="0")
        late = self._record(home_team="Chelsea", away_team="Arsenal", fixture_id="fixture-3",
                            predicted_at="2026-11-07T13:00:00+00:00")
        self._verify_score(late, "2", "0")

        report = evaluate_prediction_ledger([valid, unverified, late])
        calibration = report["top_outcome_calibration"]

        self.assertEqual(calibration["matches"], 1)
        self.assertEqual(report["confidence_bucket_hit_rate"], calibration["bins"])
        sixty_bucket = next(b for b in calibration["bins"] if b["confidence_bucket"] == "60–70%")
        self.assertEqual(sixty_bucket["matches"], 1)
        self.assertEqual(sixty_bucket["mean_confidence_pct"], 60.0)
        self.assertEqual(sixty_bucket["observed_hit_rate_pct"], 100.0)
        self.assertEqual(sixty_bucket["sample_status"], "sparse")

    def test_calibration_bins_handle_empty_and_boundary_confidence(self):
        from prediction_evaluation import _top_outcome_calibration

        empty = _top_outcome_calibration([])
        self.assertEqual(empty["matches"], 0)
        self.assertTrue(all(row["matches"] == 0 for row in empty["bins"]))

        rows = []
        for index, confidence in enumerate((40, 50, 60, 70, 80, 90, 100)):
            row = {
                "model_home_win": confidence,
                "model_draw": (100 - confidence) / 2,
                "model_away_win": (100 - confidence) / 2,
                "actual_home_goals": 1,
                "actual_away_goals": 0,
            }
            rows.append(row)
        calibration = _top_outcome_calibration(rows)
        self.assertEqual(calibration["matches"], 7)
        self.assertEqual([b["matches"] for b in calibration["bins"]], [0, 1, 1, 1, 1, 1, 2])


    def test_additional_markets_are_stored_and_scored_only_on_verified_results(self):
        row = self._record(probabilities={
            "home_win": 60, "draw": 25, "away_win": 15,
            "over_1_5": 80, "over_2_5": 40, "btts_yes": 60,
        })
        self._verify_score(row, "2", "0")
        unverified = self._record(
            home_team="Liverpool", away_team="Everton", fixture_id="fixture-2",
            probabilities={
                "home_win": 50, "draw": 30, "away_win": 20,
                "over_1_5": 90, "over_2_5": 80, "btts_yes": 70,
            },
        )
        unverified.update(actual_home_goals="3", actual_away_goals="2")

        report = evaluate_prediction_ledger([row, unverified])
        self.assertEqual(row["model_over_1_5"], 80.0)
        self.assertEqual(row["model_over_2_5"], 40.0)
        self.assertEqual(row["model_btts_yes"], 60.0)
        self.assertEqual(report["market_metrics"]["over_1_5"]["matches"], 1)
        self.assertEqual(report["market_metrics"]["over_1_5"]["accuracy_pct"], 100.0)
        self.assertEqual(report["market_metrics"]["over_2_5"]["accuracy_pct"], 100.0)
        self.assertEqual(report["market_metrics"]["btts_yes"]["accuracy_pct"], 0.0)

    def test_invalid_additional_market_probabilities_are_not_saved(self):
        row = self._record(probabilities={
            "home_win": 60, "draw": 25, "away_win": 15,
            "over_1_5": 120, "over_2_5": float("nan"), "btts_yes": -1,
        })
        self.assertEqual(row["model_over_1_5"], "")
        self.assertEqual(row["model_over_2_5"], "")
        self.assertEqual(row["model_btts_yes"], "")



    def test_evaluation_sample_is_not_validated_with_one_verified_fixture(self):
        row = self._record()
        self._verify_score(row, "2", "0")
        report = evaluate_prediction_ledger([row])
        assessment = report["evaluation_sample_assessment"]
        self.assertEqual(assessment["status"], "insufficient_sample")
        self.assertEqual(assessment["verified_unique_fixtures"], 1)
        self.assertIn("highly provisional", assessment["message"])
        self.assertIn("do not claim", assessment["message"])

    def test_evaluation_sample_threshold_is_explicit_and_metrics_remain_descriptive(self):
        records = []
        for index in range(30):
            row = self._record(
                fixture_id=f"fixture-{index}",
                home_team=f"Home {index}",
                away_team=f"Away {index}",
            )
            row["kickoff_at"] = f"2026-11-{(index % 27) + 1:02d}T12:00:00+00:00"
            row["predicted_at"] = f"2026-11-{(index % 27) + 1:02d}T10:00:00+00:00"
            self._verify_score(row, "2", "0")
            records.append(row)
        assessment = evaluate_prediction_ledger(records)["evaluation_sample_assessment"]
        self.assertEqual(assessment["status"], "descriptive_sample")
        self.assertEqual(assessment["verified_unique_fixtures"], 30)
        self.assertIn("does not establish calibration", assessment["message"])

    def test_evaluation_sample_without_verified_scores_is_not_measurable(self):
        report = evaluate_prediction_ledger([self._record()])
        assessment = report["evaluation_sample_assessment"]
        self.assertEqual(assessment["status"], "no_verified_results")
        self.assertEqual(assessment["verified_unique_fixtures"], 0)

if __name__ == "__main__":
    unittest.main()
