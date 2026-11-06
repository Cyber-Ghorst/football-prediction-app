import unittest
from tvd import run_tvd
from engine import predict_match
import json


def full_profile(name, weakness=70, weapon=80):
    return {
        "name": name,
        "vulnerabilities": {
            key: {"score": weakness, "confidence": 90}
            for key in ["space_behind", "press_resistance", "aerial_defence",
                        "transition_recovery", "central_compactness",
                        "wide_defending", "central_penetration"]
        },
        "weapons": {
            key: {"score": weapon, "confidence": 90}
            for key in ["pace_through_balls", "pressing_intensity", "aerial_threat",
                        "counterattack_threat", "midfield_overloads", "wing_threat",
                        "between_lines_threat"]
        },
    }


class TacticalVulnerabilityTests(unittest.TestCase):
    def test_both_directions_are_calculated(self):
        a, b = full_profile("A"), full_profile("B")
        result = run_tvd(a, b)
        self.assertAlmostEqual(result["team_a_attacks_b"]["compatibility_score"], 56.0, places=1)
        self.assertAlmostEqual(result["team_b_attacks_a"]["compatibility_score"], 56.0, places=1)
        self.assertEqual(result["stronger_tactical_matchup"], "EVEN")

    def test_missing_data_is_not_imputed(self):
        result = run_tvd({"name": "A"}, {"name": "B"})
        self.assertIsNone(result["team_a_attacks_b"]["compatibility_score"])
        self.assertEqual(result["team_a_attacks_b"]["missing_pairings"], 7)

    def test_partial_data_reports_coverage(self):
        a, b = full_profile("A"), full_profile("B")
        b["vulnerabilities"] = {"space_behind": {"score": 80, "confidence": 100}}
        a["weapons"] = {"pace_through_balls": {"score": 90, "confidence": 100}}
        result = run_tvd(a, b)["team_a_attacks_b"]
        self.assertEqual(result["compatibility_score"], 72.0)
        self.assertEqual(result["data_coverage"], 16.0)
        self.assertEqual(result["missing_pairings"], 6)

    def test_invalid_score_is_rejected(self):
        a, b = full_profile("A"), full_profile("B")
        b["vulnerabilities"]["space_behind"]["score"] = 101
        with self.assertRaises(ValueError):
            run_tvd(a, b)

    def test_tvd_override_flows_into_layer1(self):
        with open("sample_teams.json", encoding="utf-8") as f:
            teams = json.load(f)
        result = predict_match(
            teams["Arsenal"], teams["Chelsea"],
            tactical_compatibility={"home": 90, "away": 20}
        )
        self.assertEqual(result["tactical_compatibility_used"], {"home": 90.0, "away": 20.0})


if __name__ == "__main__":
    unittest.main()
