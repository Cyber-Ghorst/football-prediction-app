import unittest
from provider_season_provenance import (
    explicit_season_label, is_verified_2026_27_snapshot, season_match,
)

class ProviderSeasonProvenanceTests(unittest.TestCase):
    def test_explicit_2026_and_2026_27_labels_normalize(self):
        self.assertEqual(explicit_season_label({"catalogue_reference_season":2026}), "2026/27")
        self.assertEqual(explicit_season_label({"season_label":"2026/27"}), "2026/27")
    def test_missing_season_is_not_inferred_from_method(self):
        self.assertIsNone(explicit_season_label({"team_evidence_method":"league_season_standings"}))
    def test_mismatched_seasons_are_rejected(self):
        self.assertEqual(season_match({"season_label":"2026/27"},{"season_label":"2024"})[3],
                         "held_mismatched_season")
    def test_matching_2026_27_seasons_pass(self):
        self.assertTrue(season_match({"season_label":"2026/27"},{"season_label":"2026"})[0])

    def test_only_persisted_matching_2026_27_snapshots_are_verified(self):
        self.assertTrue(is_verified_2026_27_snapshot({
            "season_match_verified": True,
            "target_season_label": "2026/27",
            "api_ninjas_season_label": "2026/27",
        }))
        self.assertFalse(is_verified_2026_27_snapshot({
            "season_match_verified": True,
            "target_season_label": "2026/27",
            "api_ninjas_season_label": None,
        }))
        self.assertFalse(is_verified_2026_27_snapshot({
            "season_match_verified": False,
            "target_season_label": "2026/27",
            "api_ninjas_season_label": "2026/27",
        }))

if __name__ == "__main__":
    unittest.main()
