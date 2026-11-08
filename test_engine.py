import unittest
from engine import predict_match
import json

class PredictionEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open("sample_teams.json", encoding="utf-8") as f:
            cls.teams = json.load(f)

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

if __name__ == "__main__":
    unittest.main()
