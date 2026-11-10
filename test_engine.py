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

        self.assertEqual(snapshot["schema_version"], "prediction-features-v1")
        self.assertEqual(snapshot["captured_at"], "2026-11-10T10:00:00+00:00")
        self.assertEqual(len(snapshot["teams"]["home"]["recent_matches"]), 10)
        self.assertEqual(snapshot["teams"]["home"]["tactical_compatibility"], 75.0)
        self.assertEqual(snapshot["calculated"]["model_weights"], result["model_weights"])
        self.assertEqual(snapshot["calculated"]["probabilities"], result["probabilities"])
        self.assertEqual(snapshot["recency_policy"], "latest_5_60pct_previous_5_40pct")

    def test_feature_snapshot_preserves_missing_values_as_unknown(self):
        from engine import build_prediction_feature_snapshot

        home = dict(self.teams["Arsenal"])
        away = dict(self.teams["Chelsea"])
        home["player_availability"] = None
        result = predict_match(home, away)
        snapshot = build_prediction_feature_snapshot(home, away, result)
        self.assertIsNone(snapshot["teams"]["home"]["player_availability"])

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
