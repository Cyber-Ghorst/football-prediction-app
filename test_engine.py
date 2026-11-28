import unittest
from engine import predict_match
import json

class PredictionEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open("sample_teams.json", encoding="utf-8") as f:
            cls.teams = json.load(f)

    def test_feature_snapshot_captures_inputs_and_model_calculations(self):
        from engine import build_prediction_feature_snapshot

        home = dict(self.teams["Arsenal"])
        away = dict(self.teams["Chelsea"])
        result = predict_match(home, away, tactical_compatibility={"home": 75})
        snapshot = build_prediction_feature_snapshot(
            home, away, result,
            tactical_compatibility={"home": 75},
            captured_at="2026-11-10T10:00:00+00:00",
        )

        self.assertEqual(snapshot["schema_version"], "prediction-features-v2")
        self.assertEqual(snapshot["captured_at"], "2026-11-10T10:00:00+00:00")
        self.assertEqual(len(snapshot["teams"]["home"]["recent_matches"]), 10)
        self.assertEqual(snapshot["teams"]["home"]["recent_matches"][0]["observations"]["goals_for"]["status"], "observed")
        self.assertEqual(snapshot["teams"]["home"]["tactical_compatibility"]["value"], 75.0)
        self.assertEqual(snapshot["teams"]["home"]["tactical_compatibility"]["status"], "observed")
        self.assertEqual(snapshot["calculated"]["model_weights"], result["model_weights"])
        self.assertEqual(snapshot["calculated"]["probabilities"], result["probabilities"])
        self.assertEqual(snapshot["recency_policy"], "latest_5_60pct_previous_5_40pct")

    def test_feature_snapshot_preserves_missing_values_as_unknown(self):
        from engine import build_prediction_feature_snapshot

        home = dict(self.teams["Arsenal"])
        away = dict(self.teams["Chelsea"])
        home["player_availability"] = None
        snapshot = build_prediction_feature_snapshot(home, away, {})
        self.assertEqual(snapshot["teams"]["home"]["player_availability"]["status"], "missing")


    def test_feature_snapshot_v2_retains_match_identity_and_source_provenance(self):
        from engine import build_prediction_feature_snapshot

        home = dict(self.teams["Arsenal"])
        away = dict(self.teams["Chelsea"])
        home["matches"] = [dict(match) for match in home["matches"]]
        home["matches"][0].update({
            "fixture_id": "fixture-123",
            "date": "2026-11-20T17:00:00+00:00",
            "venue": "home",
            "source_provider": "provider-x",
            "provider_updated_at": "2026-11-20T18:00:00+00:00",
            "collection_fetched_at": "2026-11-20T18:05:00+00:00",
            "source_fixture_id": "upstream-456",
        })
        result = predict_match(home, away)
        snapshot = build_prediction_feature_snapshot(home, away, result)
        match = snapshot["teams"]["home"]["recent_matches"][0]
        self.assertEqual(match["identity"]["fixture_id"], "fixture-123")
        self.assertEqual(match["identity"]["kickoff_at"], "2026-11-20T17:00:00+00:00")
        self.assertEqual(match["identity"]["venue"], "home")
        self.assertEqual(match["source_provenance"]["source_provider"], "provider-x")
        self.assertEqual(match["source_provenance"]["source_fixture_id"], "upstream-456")
        self.assertEqual(match["source_provenance"]["provider_updated_at"], "2026-11-20T18:00:00+00:00")

    def test_feature_snapshot_v2_distinguishes_invalid_from_missing(self):
        from engine import build_prediction_feature_snapshot

        home = dict(self.teams["Arsenal"])
        away = dict(self.teams["Chelsea"])
        home["matches"] = [dict(match) for match in home["matches"]]
        home["matches"][0]["opponent_strength"] = "not-a-number"
        snapshot = build_prediction_feature_snapshot(home, away, {})
        observation = snapshot["teams"]["home"]["recent_matches"][0]["observations"]["opponent_strength"]
        self.assertEqual(observation["status"], "invalid")
        self.assertEqual(observation["raw_value"], "not-a-number")
        self.assertEqual(snapshot["provenance_contract"]["missing_and_invalid_distinguished"], True)

    def test_feature_snapshot_v2_records_target_fixture_context(self):
        from engine import build_prediction_feature_snapshot

        snapshot = build_prediction_feature_snapshot(
            self.teams["Arsenal"], self.teams["Chelsea"], {},
            fixture_context={"id": 987, "starting_at": "2026-12-01T19:00:00Z", "home_team_id": 1},
        )
        self.assertEqual(snapshot["target_fixture"]["id"], 987)
        self.assertEqual(snapshot["target_fixture"]["identity_status"], "identified")


    def test_strict_readiness_accepts_complete_profiles(self):
        from engine import build_prediction_component_readiness
        report = build_prediction_component_readiness(self.teams["Arsenal"], self.teams["Chelsea"])
        self.assertTrue(report["eligible"])
        self.assertEqual(report["policy_version"], "strict-component-readiness-v1")
        self.assertFalse(report["weights_redistributed"])

    def test_strict_readiness_blocks_missing_top_level_and_tactical_components(self):
        from engine import build_prediction_component_readiness
        home, away = dict(self.teams["Arsenal"]), dict(self.teams["Chelsea"])
        home["player_availability"] = None
        away["tactical_compatibility"] = None
        report = build_prediction_component_readiness(home, away)
        self.assertFalse(report["eligible"])
        self.assertIn("player_availability", report["teams"]["home"]["missing_components"])
        self.assertIn("tactical_compatibility", report["teams"]["away"]["missing_tactical_subcomponents"])

    def test_standard_prediction_is_blocked_when_required_component_is_missing(self):
        home = dict(self.teams["Arsenal"])
        home["player_availability"] = None
        with self.assertRaisesRegex(ValueError, "strict readiness policy"):
            predict_match(home, self.teams["Chelsea"])

    def test_probabilities_sum_to_approximately_100(self):
        r = predict_match(self.teams["Arsenal"], self.teams["Chelsea"])
        p = r["probabilities"]
        self.assertAlmostEqual(p["home_win"] + p["draw"] + p["away_win"], 100.0, delta=0.2)

    def test_scoreline_list_has_five_entries(self):
        r = predict_match(self.teams["Liverpool"], self.teams["Manchester City"])
        self.assertEqual(len(r["most_likely_scores"]), 5)

    def test_rejects_insufficient_history(self):
        bad = dict(self.teams["Arsenal"])
        bad["matches"] = bad["matches"][:3]
        with self.assertRaises(ValueError):
            predict_match(bad, self.teams["Chelsea"])

    def test_rejects_malformed_match_record(self):
        bad = dict(self.teams["Arsenal"])
        bad["matches"] = [None] + bad["matches"][1:]
        with self.assertRaisesRegex(ValueError, "matches\\[0\\].*malformed"):
            predict_match(bad, self.teams["Chelsea"])

    def test_rejects_malformed_required_goal_value(self):
        bad = dict(self.teams["Arsenal"])
        bad["matches"] = [dict(match) for match in bad["matches"]]
        bad["matches"][0]["goals_for"] = "not-a-number"
        with self.assertRaisesRegex(ValueError, "goals_for.*malformed"):
            predict_match(bad, self.teams["Chelsea"])

    def test_rejects_non_finite_goal_value(self):
        bad = dict(self.teams["Arsenal"])
        bad["matches"] = [dict(match) for match in bad["matches"]]
        bad["matches"][0]["goals_against"] = float("nan")
        with self.assertRaisesRegex(ValueError, "goals_against.*non-finite"):
            predict_match(bad, self.teams["Chelsea"])

    def test_rejects_out_of_range_optional_component(self):
        bad = dict(self.teams["Arsenal"])
        bad["player_availability"] = 101
        with self.assertRaisesRegex(ValueError, "player_availability.*out of range"):
            predict_match(bad, self.teams["Chelsea"])

    def test_rejects_invalid_opponent_strength(self):
        bad = dict(self.teams["Arsenal"])
        bad["matches"] = [dict(match) for match in bad["matches"]]
        bad["matches"][2]["opponent_strength"] = -1
        with self.assertRaisesRegex(ValueError, "opponent_strength.*out of range"):
            predict_match(bad, self.teams["Chelsea"])

    def test_rejects_invalid_tactical_compatibility_override(self):
        with self.assertRaisesRegex(ValueError, "tactical_compatibility.home.*out of range"):
            predict_match(self.teams["Arsenal"], self.teams["Chelsea"],
                          tactical_compatibility={"home": 120})

    def test_optional_missing_components_remain_missing(self):
        from engine import _team_components

        profile = dict(self.teams["Arsenal"])
        profile["player_availability"] = None
        profile["home_rating"] = None
        components = _team_components(profile, "home_rating")
        self.assertNotIn("player_availability", components)
        self.assertNotIn("home_away", components)

    def test_most_likely_outcome_labels(self):
        from engine import most_likely_outcome
        home = most_likely_outcome({"home_win": 48, "draw": 27, "away_win": 25}, "Brighton", "Fulham")
        draw = most_likely_outcome({"home_win": 24, "draw": 52, "away_win": 24}, "Brighton", "Fulham")
        away = most_likely_outcome({"home_win": 20, "draw": 25, "away_win": 55}, "Brighton", "Fulham")
        tie = most_likely_outcome({"home_win": 40, "draw": 40, "away_win": 20}, "Brighton", "Fulham")
        self.assertEqual(home["label"], "Predicted winner: Brighton")
        self.assertEqual(draw["label"], "Most likely outcome: Draw")
        self.assertEqual(away["label"], "Predicted winner: Fulham")
        self.assertEqual(tie["label"], "No single most likely outcome (tied probabilities)")
    def test_agreed_model_weights_are_preserved_and_sum_to_one(self):
        from engine import WEIGHTS, TACTICAL_WEIGHTS

        self.assertEqual(WEIGHTS, {
            "recent_form": 0.20,
            "goals_scored": 0.10,
            "goals_conceded": 0.10,
            "home_away": 0.10,
            "strength_of_schedule": 0.15,
            "player_availability": 0.05,
            "tactical": 0.30,
        })
        self.assertAlmostEqual(sum(WEIGHTS.values()), 1.0)
        self.assertEqual(TACTICAL_WEIGHTS, {
            "playing_style": 0.06,
            "defensive_structure": 0.07,
            "attacking_approach": 0.07,
            "tactical_compatibility": 0.10,
        })
        self.assertAlmostEqual(sum(TACTICAL_WEIGHTS.values()), 0.30)

    def test_recent_five_matches_carry_sixty_percent_weight(self):
        from engine import _weighted_recent

        self.assertAlmostEqual(_weighted_recent([100] * 5 + [0] * 5), 60.0)
        self.assertAlmostEqual(_weighted_recent([0] * 5 + [100] * 5), 40.0)

    def test_optional_recency_weights_keep_original_indices_when_recent_values_are_missing(self):
        from engine import _weighted_optional

        # Only original match positions 1, 3 and 5 are present.
        # Positions 1 and 3 remain in the latest-five group; position 5 does not.
        self.assertAlmostEqual(_weighted_optional([None, 10, None, 30, None, 50]), 27.5)

    def test_optional_recency_weights_keep_original_indices_when_older_values_are_missing(self):
        from engine import _weighted_optional

        values = [10, 20, 30, 40, 50, None, 70, None, 90, None]
        expected = (10 * 1.5 + 20 * 1.5 + 30 * 1.5 + 40 * 1.5
                    + 50 * 1.5 + 70 + 90) / 9.5
        self.assertAlmostEqual(_weighted_optional(values), expected)

    def test_optional_recency_returns_none_when_all_observations_are_missing(self):
        from engine import _weighted_optional

        self.assertIsNone(_weighted_optional([None] * 10))

    def test_partial_tactical_inputs_are_renormalized_without_imputation(self):
        from engine import _tactical_rating

        score, known = _tactical_rating({
            "playing_style": 60,
            "attacking_approach": 80,
            "defensive_structure": None,
        }, None)
        expected = (60 * 0.06 + 80 * 0.07) / (0.06 + 0.07)
        self.assertAlmostEqual(score, expected)
        self.assertEqual(set(known), {"playing_style", "attacking_approach"})

    def test_tactical_compatibility_override_changes_model_ratings(self):
        high_home = predict_match(
            self.teams["Arsenal"], self.teams["Chelsea"],
            tactical_compatibility={"home": 90, "away": 20},
        )
        high_away = predict_match(
            self.teams["Arsenal"], self.teams["Chelsea"],
            tactical_compatibility={"home": 20, "away": 90},
        )
        self.assertGreater(high_home["home_rating"], high_away["home_rating"])
        self.assertGreater(high_away["away_rating"], high_home["away_rating"])
        self.assertNotEqual(high_home["probabilities"], high_away["probabilities"])



if __name__ == "__main__":
    unittest.main()
