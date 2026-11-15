import unittest

from provider_season_roster_audit import _select_highlightly


class ProviderSeasonRosterAuditTests(unittest.TestCase):
    def test_exact_name_and_country_selects_single_highlightly_competition(self):
        rows = [
            {"id": 1, "name": "Bundesliga",
             "country": {"name": "Germany"}},
            {"id": 2, "name": "Bundesliga",
             "country": {"name": "Austria"}},
        ]
        selected, status = _select_highlightly(
            rows, {"name": "Bundesliga", "country": "Germany"},
        )
        self.assertEqual(status, "unique_exact_name_country")
        self.assertEqual(selected["id"], 1)

    def test_ambiguous_world_cup_candidates_are_held(self):
        rows = [
            {"id": 1, "name": "World Cup", "country": {"name": "World"}},
            {"id": 2, "name": "World Cup", "country": {"name": "World"}},
        ]
        selected, status = _select_highlightly(
            rows, {"name": "World Cup", "country": None},
        )
        self.assertIsNone(selected)
        self.assertEqual(status, "ambiguous_competition")

    def test_missing_exact_competition_is_not_guessed(self):
        selected, status = _select_highlightly(
            [{"id": 1, "name": "Bundesliga", "country": {"name": "Germany"}}],
            {"name": "Ligue 1", "country": "France"},
        )
        self.assertIsNone(selected)
        self.assertEqual(status, "not_found")


if __name__ == "__main__":
    unittest.main()
