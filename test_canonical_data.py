import unittest

from canonical_data import (
    MatchNormalizationError, canonicalize_api_football_fixture,
    canonicalize_livescore_event, match_identity, merge_source_ids,
)


class CanonicalMatchTests(unittest.TestCase):
    def livescore(self):
        return {
            "id": "ls-900",
            "status": {"type": {"state": "post", "completed": True}},
            "competitions": [{
                "date": "2026-11-07T15:00:00Z",
                "competitors": [
                    {"id": "ls-team-1", "homeAway": "home", "score": "2",
                     "team": {"id": "ls-team-1", "name": "Arsenal FC"}},
                    {"id": "ls-team-2", "homeAway": "away", "score": "1",
                     "team": {"id": "ls-team-2", "name": "Chelsea"}},
                ],
            }],
        }

    def api_fixture(self):
        return {
            "fixture": {"id": 771, "date": "2026-11-07T15:02:00+00:00",
                        "status": {"short": "FT"}},
            "teams": {"home": {"id": 42, "name": "Arsenal"},
                      "away": {"id": 49, "name": "Chelsea FC"}},
            "goals": {"home": 2, "away": 1},
        }

    def test_live_score_normalizes_nested_competitors_and_score(self):
        result = canonicalize_livescore_event(
            self.livescore(), competition_key="eng-premier-league", season=2026
        )
        self.assertEqual(result["status"], "finished")
        self.assertEqual(result["home_score"], 2)
        self.assertEqual(result["home"]["source_ids"]["livescore_football"], "ls-team-1")

    def test_api_football_normalizes_fixture_shape(self):
        result = canonicalize_api_football_fixture(
            self.api_fixture(), competition_key="eng-premier-league", season=2026
        )
        self.assertEqual(result["source_ids"]["api_football"], "771")
        self.assertEqual(result["away_score"], 1)

    def test_match_identity_uses_competition_season_teams_and_kickoff_not_ids(self):
        left = canonicalize_livescore_event(
            self.livescore(), competition_key="eng-premier-league", season=2026
        )
        right = canonicalize_api_football_fixture(
            self.api_fixture(), competition_key="eng-premier-league", season=2026
        )
        self.assertTrue(match_identity(left, right, team_aliases={
            "Arsenal FC": "Arsenal", "Chelsea FC": "Chelsea"
        }))
        self.assertNotEqual(
            left["source_ids"]["livescore_football"],
            right["source_ids"]["api_football"],
        )

    def test_competition_or_season_mismatch_prevents_join(self):
        left = canonicalize_livescore_event(
            self.livescore(), competition_key="eng-premier-league", season=2026
        )
        right = canonicalize_api_football_fixture(
            self.api_fixture(), competition_key="esp-la-liga", season=2026
        )
        self.assertFalse(match_identity(left, right))
        right["competition_key"] = "eng-premier-league"
        right["season"] = 2025
        self.assertFalse(match_identity(left, right))

    def test_home_away_swap_prevents_join(self):
        left = canonicalize_livescore_event(
            self.livescore(), competition_key="eng-premier-league", season=2026
        )
        right = canonicalize_api_football_fixture(
            self.api_fixture(), competition_key="eng-premier-league", season=2026
        )
        right["home"], right["away"] = right["away"], right["home"]
        self.assertFalse(match_identity(left, right))

    def test_missing_kickoff_fails_closed(self):
        with self.assertRaises(MatchNormalizationError):
            canonicalize_api_football_fixture(
                {"fixture": {}, "teams": {}, "goals": {}},
                competition_key="eng-premier-league", season=2026
            )

    def test_source_ids_are_namespaced(self):
        left = canonicalize_livescore_event(
            self.livescore(), competition_key="eng-premier-league", season=2026
        )
        right = canonicalize_api_football_fixture(
            self.api_fixture(), competition_key="eng-premier-league", season=2026
        )
        ids = merge_source_ids(left, right)
        self.assertEqual(ids["livescore_football"], "ls-900")
        self.assertEqual(ids["api_football"], "771")
        self.assertEqual(ids["home.livescore_football"], "ls-team-1")
        self.assertEqual(ids["home.api_football"], "42")


if __name__ == "__main__":
    unittest.main()
