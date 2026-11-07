import unittest

from canonical_data import canonicalize_api_ninjas_match, match_identity
from sportmonks_canonical import canonicalize_sportmonks_fixture


class SportmonksCanonicalTests(unittest.TestCase):
    def fixture(self):
        return {
            "id": 12345, "season_id": 987, "starting_at": "2026-11-07T15:00:00Z",
            "state_id": 5, "participants": [
                {"id": 100, "name": "Arsenal", "meta": {"location": "home"}},
                {"id": 200, "name": "Chelsea", "meta": {"location": "away"}},
            ],
            "scores": [
                {"participant_id": 100, "description": "CURRENT", "score": {"goals": 2}},
                {"participant_id": 200, "description": "CURRENT", "score": {"goals": 1}},
            ],
        }

    def test_normalizes_participants_state_and_current_scores(self):
        result = canonicalize_sportmonks_fixture(
            self.fixture(), competition_key="eng-premier-league", season=2026
        )
        self.assertEqual(result["status"], "finished")
        self.assertEqual((result["home_score"], result["away_score"]), (2, 1))
        self.assertEqual(result["source_ids"]["sportmonks"], "12345")

    def test_identity_matches_other_provider_without_comparing_ids(self):
        sm = canonicalize_sportmonks_fixture(
            self.fixture(), competition_key="eng-premier-league", season=2026
        )
        ninjas = canonicalize_api_ninjas_match({
            "game_id": "ninjas-123", "season": 2026,
            "start_time": "2026-11-07T15:02:00Z", "status": "final",
            "home_team": {"team_id": "ars", "name": "Arsenal"},
            "away_team": {"team_id": "che", "name": "Chelsea"},
            "home_score": 2, "away_score": 1,
        }, competition_key="eng-premier-league")
        self.assertTrue(match_identity(sm, ninjas))
        self.assertNotEqual(sm["source_ids"]["sportmonks"], ninjas["source_ids"]["api_ninjas"])

    def test_missing_participant_or_kickoff_fails_closed(self):
        bad = self.fixture()
        bad["participants"] = bad["participants"][:1]
        with self.assertRaises(ValueError):
            canonicalize_sportmonks_fixture(bad, competition_key="eng-premier-league", season=2026)


if __name__ == "__main__":
    unittest.main()
