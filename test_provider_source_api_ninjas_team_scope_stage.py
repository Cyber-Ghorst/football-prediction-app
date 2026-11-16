import unittest

from provider_source_api_ninjas_team_scope_stage import build_source_entities


class APINinjasTeamScopeStageTests(unittest.TestCase):
    def test_stages_only_active_rows_with_explicit_provider_scope(self):
        entities, held = build_source_entities([{
            "league": "laliga",
            "teams": [{
                "team_id": "soccer-real-madrid", "name": "Real Madrid",
                "country": "ES", "team_type": "club", "gender": "men",
                "active": True, "league": "laliga",
            }],
        }])
        self.assertEqual(held, [])
        self.assertEqual(len(entities), 1)
        row = entities[0]
        self.assertEqual(row["country"], "ES")
        self.assertEqual(row["team_type"], "club")
        self.assertEqual(row["gender_scope"], "men")
        self.assertEqual(row["raw_payload"]["country_code_iso3166_alpha2"], "ES")
        self.assertFalse("age_group" in row)
        self.assertFalse("squad_scope" in row)

    def test_holds_missing_country_gender_or_inactive_rows(self):
        entities, held = build_source_entities([{
            "league": "epl",
            "teams": [
                {"team_id": "a", "name": "A", "country": None,
                 "team_type": "club", "gender": "men", "active": True},
                {"team_id": "b", "name": "B", "country": "GB",
                 "team_type": "club", "gender": None, "active": True},
                {"team_id": "c", "name": "C", "country": "GB",
                 "team_type": "club", "gender": "men", "active": False},
            ],
        }])
        self.assertEqual(entities, [])
        self.assertEqual(len(held), 3)

    def test_merges_duplicate_team_ids_across_leagues_without_losing_scope(self):
        entities, held = build_source_entities([
            {"league": "epl", "teams": [{
                "team_id": "soccer-a", "name": "A", "country": "GB",
                "team_type": "club", "gender": "men", "active": True,
            }]},
            {"league": "ucl", "teams": [{
                "team_id": "soccer-a", "name": "A", "country": "GB",
                "team_type": "club", "gender": "men", "active": True,
            }]},
        ])
        self.assertEqual(held, [])
        self.assertEqual(len(entities), 1)
        self.assertEqual(
            entities[0]["raw_payload"]["domestic_league_codes"],
            ["epl", "ucl"],
        )

    def test_holds_conflicting_duplicate_team_scope(self):
        entities, held = build_source_entities([
            {"league": "epl", "teams": [{
                "team_id": "soccer-a", "name": "A", "country": "GB",
                "team_type": "club", "gender": "men", "active": True,
            }]},
            {"league": "wsl", "teams": [{
                "team_id": "soccer-a", "name": "A", "country": "GB",
                "team_type": "club", "gender": "women", "active": True,
            }]},
        ])
        self.assertEqual(entities, [])
        self.assertEqual(held[0]["reason"], "conflicting_duplicate_team_catalogue_records")


if __name__ == "__main__":
    unittest.main()
