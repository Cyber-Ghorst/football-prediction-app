import unittest

from provider_entity_crosswalk import extract_provider_entities_from_observations


class CompetitionTypeExtractionTests(unittest.TestCase):
    def test_extracts_only_explicit_competition_type(self):
        rows = extract_provider_entities_from_observations("bzzoiro", [{
            "competition_key": "premier",
            "competition_name": "Premier League",
            "season_key": "2026",
            "season_name": "2026",
            "home_team_key": "h1",
            "home_team_name": "Home FC",
            "away_team_key": "a1",
            "away_team_name": "Away FC",
            "raw_payload": {
                "league": {"type": "LEAGUE"},
            },
        }])
        self.assertEqual(rows["leagues"][0]["competition_type"], "LEAGUE")

    def test_does_not_infer_type_when_provider_omits_it(self):
        rows = extract_provider_entities_from_observations("openligadb", [{
            "competition_key": "bl1",
            "competition_name": "Bundesliga",
            "season_key": "2026",
            "season_name": "2026",
        }])
        self.assertIsNone(rows["leagues"][0]["competition_type"])


if __name__ == "__main__":
    unittest.main()
