import unittest
from copy import deepcopy

from livescore_layer2 import (
    apply_livescore_verified_result_fallback_to_profiles,
    collect_livescore_verified_result_fallback,
)


class LiveScoreLayer2FallbackTests(unittest.TestCase):
    def test_collection_is_disabled_without_calling_provider(self):
        client = type("Client", (), {
            "meta": lambda self: self.fail("historical-only provider must not be queried"),
            "leagues": lambda self, **kwargs: self.fail("historical-only provider must not be queried"),
            "fixtures": lambda self, *args, **kwargs: self.fail("historical-only provider must not be queried"),
        })()
        report = collect_livescore_verified_result_fallback(
            client,
            source_competition={"id": 8, "name": "Premier League"},
            sportmonks_fixtures=[{"id": 500}],
            selected_team_ids={10, 20},
            competition_key="premier-league",
            season=2026,
            season_id=2026,
        )
        self.assertEqual(report["status"], "disabled")
        self.assertEqual(report["verified_matches"], [])
        self.assertIn("HTTP 400", report["reason"])

    def test_apply_is_a_noop_and_preserves_profiles(self):
        profiles = [
            {"id": 10, "name": "Coventry", "matches": [], "tactical_evidence": {"source": "primary"}},
            {"id": 20, "name": "Fulham", "matches": [], "tactical_evidence": {"source": "primary"}},
        ]
        before = deepcopy(profiles)
        result = apply_livescore_verified_result_fallback_to_profiles(
            profiles, [{"score_source_provider": "livescore_football"}]
        )
        self.assertEqual(result["status"], "disabled")
        self.assertEqual(result["profiles_updated"], 0)
        self.assertEqual(profiles, before)


if __name__ == "__main__":
    unittest.main()
