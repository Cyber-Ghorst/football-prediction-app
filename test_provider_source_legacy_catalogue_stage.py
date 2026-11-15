import unittest

from provider_source_legacy_catalogue_stage import extract_legacy_catalogue_entities


class LegacyCatalogueSourceStageTests(unittest.TestCase):
    def test_extracts_only_competition_season_and_team_provider_ids(self):
        rows = extract_legacy_catalogue_entities(
            [{
                "league_id": "sportmonks:8", "name": "Premier League",
                "country": "England", "competition_type": "league",
                "source_provider": "sportmonks",
            }],
            [{
                "season_id": "sportmonks:28083", "league_id": "sportmonks:8",
                "name": "2026/2027", "start_date": "2026-08-01",
                "end_date": "2027-05-31", "source_provider": "sportmonks",
            }],
            [{
                "team_id": "sportmonks:14", "name": "Arsenal",
                "country": "England", "source_provider": "sportmonks",
            }],
        )
        self.assertEqual([row["entity_type"] for row in rows],
                         ["competition", "season", "team"])
        self.assertEqual(rows[0]["provider_entity_id"], "8")
        self.assertEqual(rows[1]["provider_entity_id"], "28083")
        self.assertEqual(rows[1]["parent_competition_provider_id"], "8")
        self.assertEqual(rows[2]["provider_entity_id"], "14")
        self.assertEqual(rows[2]["raw_payload"]["team_scope_evidence"],
                         "not enriched by this migration")

    def test_rejects_unprefixed_or_wrong_provider_legacy_ids(self):
        with self.assertRaisesRegex(ValueError, "valid Sportmonks namespace"):
            extract_legacy_catalogue_entities(
                [{"league_id": "highlightly:8", "name": "Premier League"}],
                [], [],
            )
        with self.assertRaisesRegex(ValueError, "valid Sportmonks namespace"):
            extract_legacy_catalogue_entities(
                [], [{"season_id": "28083", "league_id": "sportmonks:8", "name": "2026/27"}], [],
            )

    def test_never_extracts_fixtures_or_statistics(self):
        rows = extract_legacy_catalogue_entities([], [], [])
        self.assertEqual(rows, [])
        self.assertTrue(all(row["entity_type"] in {"competition", "season", "team"} for row in rows))


if __name__ == "__main__":
    unittest.main()
