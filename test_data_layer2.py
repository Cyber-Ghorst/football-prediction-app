import unittest
from unittest.mock import Mock

from data_layer2 import _standings_rank_map, collect_team_profile
from form_analyzer import venue_rating


class Layer2NormalizationTests(unittest.TestCase):
    def test_standings_are_normalized_within_competition(self):
        rows = [{
            "league": {
                "standings": [[
                    {"rank": 1, "team": {"id": 10}},
                    {"rank": 2, "team": {"id": 20}},
                    {"rank": 3, "team": {"id": 30}},
                ]]
            }
        }]
        result = _standings_rank_map(rows)
        self.assertEqual(result[10], 100.0)
        self.assertAlmostEqual(result[20], 200.0 / 3)
        self.assertAlmostEqual(result[30], 100.0 / 3)

    def test_venue_rating_uses_latest_five_sixty_percent_weight(self):
        latest_wins = [
            {"venue": "home", "goals_for": 2, "goals_against": 0}
            for _ in range(5)
        ]
        previous_losses = [
            {"venue": "home", "goals_for": 0, "goals_against": 2}
            for _ in range(5)
        ]
        self.assertEqual(venue_rating(latest_wins + previous_losses, "home"), 60.0)
        self.assertEqual(venue_rating(previous_losses + latest_wins, "home"), 40.0)

    def test_venue_rating_keeps_recency_positions_before_venue_filtering(self):
        matches = [
            {"venue": "away", "goals_for": 0, "goals_against": 1},
            {"venue": "home", "goals_for": 2, "goals_against": 0},
            {"venue": "away", "goals_for": 0, "goals_against": 1},
            {"venue": "home", "goals_for": 2, "goals_against": 0},
            {"venue": "away", "goals_for": 0, "goals_against": 1},
            {"venue": "home", "goals_for": 0, "goals_against": 2},
            {"venue": "away", "goals_for": 0, "goals_against": 1},
            {"venue": "home", "goals_for": 0, "goals_against": 2},
            {"venue": "away", "goals_for": 0, "goals_against": 1},
            {"venue": "home", "goals_for": 0, "goals_against": 2},
        ]
        # Home results are two recent wins (weight 0.24) and three older
        # losses (weight 0.24), so the recency-aware venue rating is 50%.
        self.assertEqual(venue_rating(matches, "home"), 50.0)

    def test_history_is_sorted_by_absolute_utc_kickoff_not_timestamp_text(self):
        client = Mock()
        client.last_fixtures.return_value = [
            {
                "fixture": {"id": 1, "date": "2026-11-02T00:30:00+03:00", "status": {"short": "FT"}},
                "teams": {"home": {"id": 1, "name": "A"}, "away": {"id": 2, "name": "B"}},
                "goals": {"home": 1, "away": 0},
            },
            {
                "fixture": {"id": 2, "date": "2026-11-01T23:00:00Z", "status": {"short": "FT"}},
                "teams": {"home": {"id": 1, "name": "A"}, "away": {"id": 3, "name": "C"}},
                "goals": {"home": 2, "away": 0},
            },
        ]
        client.injuries.return_value = []
        client.next_fixture.return_value = None
        result = collect_team_profile(
            client, {"id": 1, "name": "A"}, 39, 2026, [], include_match_statistics=False
        )
        self.assertEqual([row["fixture_id"] for row in result["matches"]], [2, 1])
        self.assertEqual(result["data_quality"]["season_id"], 2026)

    def test_non_final_fixtures_are_excluded(self):
        client = Mock()
        client.last_fixtures.return_value = [
            {
                "fixture": {"id": 1, "date": "2026-11-01T15:00:00+00:00", "status": {"short": "FT"}},
                "teams": {"home": {"id": 1, "name": "A"}, "away": {"id": 2, "name": "B"}},
                "goals": {"home": 2, "away": 1},
            },
            {
                "fixture": {"id": 2, "date": "2026-11-08T15:00:00+00:00", "status": {"short": "NS"}},
                "teams": {"home": {"id": 1, "name": "A"}, "away": {"id": 2, "name": "B"}},
                "goals": {"home": None, "away": None},
            },
        ]
        client.injuries.return_value = []
        client.next_fixture.return_value = None
        profile = collect_team_profile(
            client, {"id": 1, "name": "A"}, 39, 2026, [], include_match_statistics=False
        )
        self.assertEqual(profile["data_quality"]["matches_returned"], 1)
        self.assertEqual(profile["matches"][0]["fixture_id"], 1)


if __name__ == "__main__":
    unittest.main()
