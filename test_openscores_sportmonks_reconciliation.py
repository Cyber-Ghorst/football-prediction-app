import unittest

from openscores_sportmonks_reconciliation import (
    find_unique_sportmonks_league,
    find_unique_sportmonks_season,
    unique_team_crosswalks,
)


class OpenScoresSportmonksReconciliationTests(unittest.TestCase):
    def test_league_mapping_requires_exact_name_and_country(self):
        result = find_unique_sportmonks_league(
            {"id": 2, "name": "Premier League", "country_code": "ENG"},
            [
                {"id": 8, "name": "Premier League", "country": {"name": "England"}},
                {"id": 564, "name": "La Liga", "country": {"name": "Spain"}},
            ],
        )
        self.assertEqual(result["status"], "unique_exact_name_country_match")
        self.assertEqual(result["league"]["id"], 8)

    def test_league_country_mismatch_is_rejected(self):
        result = find_unique_sportmonks_league(
            {"id": 2, "name": "Premier League", "country_code": "ENG"},
            [{"id": 999, "name": "Premier League", "country": {"name": "Scotland"}}],
        )
        self.assertEqual(result["status"], "no_exact_name_country_match")

    def test_ambiguous_exact_league_candidates_are_not_selected(self):
        result = find_unique_sportmonks_league(
            {"id": 2, "name": "Premier League", "country_code": "ENG"},
            [
                {"id": 8, "name": "Premier League", "country": {"name": "England"}},
                {"id": 9, "name": "Premier League", "country": {"name": "England"}},
            ],
        )
        self.assertEqual(result["status"], "ambiguous_exact_name_country_match")
        self.assertIsNone(result["league"])

    def test_season_mapping_requires_same_league_and_year_pair(self):
        result = find_unique_sportmonks_season(
            {"id": 2, "name": "Premier League 2025/2026"},
            [
                {"id": 28083, "league_id": 8, "name": "2026/2027"},
                {"id": 28082, "league_id": 8, "name": "2025/2026"},
                {"id": 38082, "league_id": 9, "name": "2025/2026"},
            ],
            8,
        )
        self.assertEqual(result["status"], "unique_exact_league_year_match")
        self.assertEqual(result["season"]["id"], 28082)

    def test_season_year_mismatch_is_not_cross_mapped(self):
        result = find_unique_sportmonks_season(
            {"id": 2, "name": "Premier League 2025/2026"},
            [{"id": 28083, "league_id": 8, "name": "2026/2027"}],
            8,
        )
        self.assertEqual(result["status"], "no_matching_league_year")

    def test_team_mapping_requires_one_exact_name_in_matched_roster(self):
        mappings = unique_team_crosswalks(
            [
                {"provider_team_id": "os-1", "name": "Arsenal"},
                {"provider_team_id": "os-2", "name": "United"},
                {"provider_team_id": "os-3", "name": "Unknown FC"},
            ],
            [
                {"id": 19, "name": "Arsenal"},
                {"id": 20, "name": "United"},
                {"id": 21, "name": "United"},
            ],
        )
        self.assertEqual(len(mappings), 1)
        self.assertEqual(mappings[0]["provider_entity_id"], "os-1")
        self.assertEqual(mappings[0]["canonical_entity_id"], "sportmonks:19")


if __name__ == "__main__":
    unittest.main()
