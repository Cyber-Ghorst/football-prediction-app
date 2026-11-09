import unittest

from tactical_evidence import (
    build_league_reference_statistics,
    build_tactical_evidence_profile,
)
from tvd import run_tvd


class AutomaticTacticalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.matches = []
        for index in range(10):
            self.matches.append({
                "statistics": {
                    "Successful Headers": 2 + index,
                    "Accurate Crosses": 3 + index,
                    "Successful Dribbles": 4 + index,
                    "Key Passes": 1 + index,
                    "Shots Insidebox": 5 + index,
                },
                "opponent_statistics": {
                    "Successful Headers": 1 + index,
                    "Accurate Crosses": 2 + index,
                    "Successful Dribbles": 3 + index,
                    "Key Passes": 2 + index,
                    "Shots Insidebox": 4 + index,
                },
            })
        reference_rows = []
        for value in range(40):
            reference_rows.append({
                "Successful Headers": value,
                "Accurate Crosses": value,
                "Successful Dribbles": value,
                "Key Passes": value,
                "Shots Insidebox": value,
            })
        self.reference = build_league_reference_statistics(reference_rows)

    def test_profiles_use_only_supported_observations(self):
        profile = build_tactical_evidence_profile(
            self.matches, self.reference, "Team A"
        )
        self.assertIsNotNone(profile["weapons"]["aerial_threat"])
        self.assertIsNotNone(profile["weapons"]["wing_threat"])
        self.assertIsNotNone(profile["vulnerabilities"]["central_penetration"])
        self.assertIsNone(profile["weapons"]["counterattack_threat"])
        self.assertEqual(profile["evidence_metadata"]["available_dimensions"], 3)

    def test_automatic_tvd_uses_separate_four_dimension_scale(self):
        a = build_tactical_evidence_profile(self.matches, self.reference, "A")
        b = build_tactical_evidence_profile(self.matches, self.reference, "B")
        result = run_tvd(a, b, automatic=True)
        self.assertEqual(result["analysis_mode"], "automatic_statistical_evidence")
        self.assertEqual(result["team_a_attacks_b"]["data_coverage"], 75.0)
        self.assertIsNotNone(result["team_a_attacks_b"]["compatibility_score"])

    def test_insufficient_observations_are_not_imputed(self):
        profile = build_tactical_evidence_profile(
            self.matches[:4], self.reference, "Team A"
        )
        self.assertIsNone(profile["weapons"]["aerial_threat"])
        self.assertIsNone(profile["vulnerabilities"]["wide_defending"])


if __name__ == "__main__":
    unittest.main()
