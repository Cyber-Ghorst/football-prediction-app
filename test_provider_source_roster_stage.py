import unittest

from provider_source_roster_stage import build_source_entities


class ProviderSourceRosterStageTests(unittest.TestCase):
    def test_stages_competition_and_observed_teams_without_inferred_team_country(self):
        rows = build_source_entities([{
            "league": {"id": "ger.1", "name": "German Bundesliga",
                       "country": "Germany", "type": "league"},
            "season": {"year": 2026},
            "team_evidence_method": "season_window_fixture_participants",
            "teams": [{
                "id": "10388", "name": "SV Elversberg", "country": None,
                "raw": {"id": "10388", "name": "SV Elversberg", "country": ""},
            }],
        }])
        competition = next(row for row in rows if row["entity_type"] == "competition")
        team = next(row for row in rows if row["entity_type"] == "team")
        self.assertEqual(competition["provider_entity_id"], "ger.1")
        self.assertEqual(competition["country"], "Germany")
        self.assertEqual(team["provider_entity_id"], "10388")
        self.assertIsNone(team["country"])
        self.assertEqual(team["raw_payload"]["competition_provider_ids"], ["ger.1"])
        self.assertFalse(team["raw_payload"]["team_evidence_complete"])
        self.assertNotIn("parent_competition_provider_id", team)

    def test_shared_provider_team_is_one_identity_with_multiple_competition_observations(self):
        rosters = [
            {"league": {"id": "ger.1", "name": "German Bundesliga", "country": "Germany"},
             "teams": [{"id": "same-team", "name": "Shared FC", "country": None}]},
            {"league": {"id": "cup.de", "name": "German Cup", "country": "Germany"},
             "teams": [{"id": "same-team", "name": "Shared FC", "country": None}]},
        ]
        rows = build_source_entities(rosters)
        teams = [row for row in rows if row["entity_type"] == "team"]
        self.assertEqual(len(teams), 1)
        self.assertEqual(
            teams[0]["raw_payload"]["competition_provider_ids"],
            ["cup.de", "ger.1"],
        )


if __name__ == "__main__":
    unittest.main()
