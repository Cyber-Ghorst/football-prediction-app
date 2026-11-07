import unittest
from unittest.mock import Mock

from data_layer2 import _standings_rank_map, collect_team_profile


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
        self.assertEqual(result[20], 200.0 / 3)
        self.assertAlmostEqual(result[30], 100.0 / 3)

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
