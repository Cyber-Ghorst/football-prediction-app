import unittest

from provider_source_api_football_roster_stage import (
    build_source_entities,
    _select_competition,
)


class APIFootballSourceRosterStageTests(unittest.TestCase):
    def test_builds_competition_scoped_season_and_explicit_team_scope(self):
        rows = build_source_entities([{
            "league": {"id": 39, "name": "Premier League", "type": "League"},
            "country": {"name": "England"},
            "seasons": [{"year": 2026, "start": "2026-08-01", "end": "2027-05-31"}],
            "teams": [
                {"team": {"id": 42, "name": "Arsenal", "country": "England",
                          "national": False}},
                {"team": {"id": 99, "name": "England", "country": "England",
                          "national": True}},
            ],
        }])
        competition = next(row for row in rows if row["entity_type"] == "competition")
        season = next(row for row in rows if row["entity_type"] == "season")
        teams = {row["provider_entity_id"]: row for row in rows if row["entity_type"] == "team"}
        self.assertEqual(competition["competition_type"], "League")
        self.assertEqual(competition["country"], "England")
        self.assertEqual(season["provider_entity_id"], "39:2026")
        self.assertEqual(season["parent_competition_provider_id"], "39")
        self.assertEqual(
            season["raw_payload"]["provider_native_parent_competition_id"], "39"
        )
        self.assertEqual(
            season["raw_payload"]["provider_native_season_year"], 2026
        )
        self.assertEqual(teams["42"]["team_type"], "club")
        self.assertEqual(teams["99"]["team_type"], "national_team")
        self.assertFalse(teams["42"]["raw_payload"]["team_evidence_complete"])

    def test_missing_national_flag_does_not_infer_team_type(self):
        rows = build_source_entities([{
            "league": {"id": 61, "name": "Ligue 1", "type": "League"},
            "country": {"name": "France"},
            "seasons": [{"year": 2026}],
            "teams": [{"team": {"id": 1, "name": "Example FC", "country": None}}],
        }])
        team = next(row for row in rows if row["entity_type"] == "team")
        self.assertIsNone(team["country"])
        self.assertIsNone(team["team_type"])

    def test_competition_selection_requires_exact_name_and_country(self):
        rows = [
            {"league": {"id": 1, "name": "Bundesliga"},
             "country": {"name": "Germany"}},
            {"league": {"id": 2, "name": "Bundesliga"},
             "country": {"name": "Austria"}},
        ]
        selected, status = _select_competition(
            rows, {"name": "Bundesliga", "country": "Germany"},
        )
        self.assertEqual(status, "unique_exact_name_country")
        self.assertEqual(selected["league"]["id"], 1)
        selected, status = _select_competition(
            rows + [{"league": {"id": 3, "name": "Bundesliga"},
                     "country": {"name": "Germany"}}],
            {"name": "Bundesliga", "country": "Germany"},
        )
        self.assertIsNone(selected)
        self.assertEqual(status, "ambiguous_exact_name_country")


if __name__ == "__main__":
    unittest.main()
