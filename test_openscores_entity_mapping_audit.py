import unittest

from openscores_entity_mapping_audit import build_entity_mapping_candidates


class OpenScoresEntityMappingAuditTests(unittest.TestCase):
    def test_season_source_metadata_preserves_date_and_current_flags(self):
        from openscores_entity_mapping_audit import _season_metadata
        result = _season_metadata(
            {"id": 9, "name": "2026/2027", "start_date": "2026-08-01",
             "end_date": "2027-05-31", "is_current": True}
        )
        self.assertEqual(result["id"], "9")
        self.assertEqual(result["name"], "2026/2027")
        self.assertTrue(result["is_current"])

    def test_payload_inventory_reports_paths_without_values(self):
        from openscores_entity_mapping_audit import _key_inventory, _source_id_keys
        payloads = [{"source_ids": {"flashscore": "secret-id"}, "home_team": {"id": 12}}]
        self.assertEqual(_key_inventory(payloads), ["home_team", "home_team.id", "source_ids", "source_ids.flashscore"])
        self.assertEqual(_source_id_keys(payloads), ["flashscore"])
        self.assertNotIn("secret-id", str(_key_inventory(payloads)))

    def test_unique_name_candidates_are_review_only(self):
        result = build_entity_mapping_candidates(
            leagues=[{"id": "os-league", "name": "Premier League", "country": "England", "country_code": "GB"}],
            seasons_by_league={"os-league": [{"id": "os-season", "name": "2026/2027",
                                              "starting_at": "2026-08-01", "ending_at": "2027-05-31", "is_current": True}]},
            observed_teams=[{"provider_team_id": "os-team", "name": "Arsenal", "observation_count": 3}],
            canonical_leagues=[{"id": "sm-league", "name": "Premier League",
                                 "country": "England", "source_provider": "sportmonks"}],
            canonical_seasons=[{"id": "sm-season", "league_id": "sm-league", "name": "2026/2027",
                                "start_date": "2026-08-01", "end_date": "2027-05-31"}],
            canonical_teams=[{"id": "sm-team", "name": "Arsenal", "country": "England",
                              "source_provider": "sportmonks"}],
        )
        self.assertEqual(result["leagues"][0]["status"], "unique_name_candidate_requires_review")
        self.assertEqual(result["seasons"][0]["status"], "unique_candidate_requires_review")
        self.assertEqual(result["teams"][0]["status"], "unique_name_candidate_requires_review")
        self.assertEqual(result["leagues"][0]["country_code"], "GB")
        self.assertTrue(result["seasons"][0]["is_current"])
        self.assertEqual(result["seasons"][0]["starting_at"], "2026-08-01")
        self.assertFalse(result["leagues"][0]["automatic_mapping_created"])
        self.assertFalse(result["seasons"][0]["automatic_mapping_created"])
        self.assertFalse(result["teams"][0]["automatic_mapping_created"])

    def test_country_mismatch_blocks_competition_candidate(self):
        result = build_entity_mapping_candidates(
            leagues=[{"id": "os", "name": "Premier League", "country": "England"}],
            seasons_by_league={"os": [{"id": "season", "name": "2026"}]},
            observed_teams=[],
            canonical_leagues=[{"id": "wrong", "name": "Premier League", "country": "Scotland"}],
            canonical_seasons=[], canonical_teams=[],
        )
        self.assertEqual(result["leagues"][0]["status"], "no_name_candidate")
        self.assertEqual(result["seasons"][0]["status"], "blocked_until_league_mapping")


    def test_missing_country_surfaces_name_candidate_but_blocks_season(self):
        result = build_entity_mapping_candidates(
            leagues=[{"id": "os", "name": "Premier League"}],
            seasons_by_league={"os": [{"id": "season", "name": "2026/2027"}]},
            observed_teams=[],
            canonical_leagues=[{"id": "sm", "name": "Premier League", "country": "England"}],
            canonical_seasons=[{"id": "sm-season", "league_id": "sm", "name": "2026/2027"}],
            canonical_teams=[],
        )
        self.assertEqual(
            result["leagues"][0]["status"],
            "unique_name_candidate_requires_country_review",
        )
        self.assertEqual(result["seasons"][0]["status"], "blocked_until_league_mapping")
        self.assertFalse(result["leagues"][0]["automatic_mapping_created"])

    def test_ambiguous_team_names_are_not_selected(self):
        result = build_entity_mapping_candidates(
            leagues=[], seasons_by_league={},
            observed_teams=[{"provider_team_id": "os", "name": "United"}],
            canonical_leagues=[], canonical_seasons=[],
            canonical_teams=[
                {"id": "a", "name": "United", "country": "England"},
                {"id": "b", "name": "United", "country": "Spain"},
            ],
        )
        self.assertEqual(result["teams"][0]["status"], "ambiguous_name_candidates")
        self.assertEqual(len(result["teams"][0]["candidates"]), 2)


if __name__ == "__main__":
    unittest.main()
