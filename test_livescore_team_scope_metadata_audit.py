import unittest

from livescore_team_scope_metadata_audit import build_scope_report, _competition_slugs


class LiveScoreTeamScopeMetadataAuditTests(unittest.TestCase):
    def test_competition_slugs_are_read_only_provider_observations(self):
        self.assertEqual(
            _competition_slugs({"competition_provider_ids": ["ger.1", "fra.1"]}),
            {"ger.1", "fra.1"},
        )
        self.assertEqual(_competition_slugs({"competition_country": "Germany"}), set())

    def test_exact_id_join_exposes_country_and_club_endpoint_scope(self):
        rows = [
            {"provider_entity_id": "101", "name": "Example FC",
             "raw_payload": {"competition_provider_ids": ["ger.1"]}},
            {"provider_entity_id": "102", "name": "Missing FC",
             "raw_payload": {"competition_provider_ids": ["ger.1"]}},
        ]
        catalogues = {
            "ger.1": {
                "status": "ok",
                "clubs": [
                    {"id": "101", "name": "Example FC", "country": "Germany",
                     "catalogSource": "club-catalog"}
                ],
                "meta": {"dedicatedCatalogCount": 1, "matchSnapshotFallback": True},
            },
            "fra.1": {"status": "ok", "clubs": [], "meta": {}},
        }
        report = build_scope_report(rows, catalogues)
        germany = report["competitions"][0]
        self.assertEqual(germany["exact_provider_id_matches"], 1)
        self.assertEqual(germany["country_value_counts"], {"Germany": 1})
        self.assertEqual(germany["catalog_source_counts"], {"club-catalog": 1})
        self.assertEqual(germany["unmatched_teams"][0]["status"],
                         "no_exact_id_match_in_club_catalogue")
        self.assertEqual(germany["team_type_evidence"]["value"], "club")
        self.assertIn("not a senior/first-team or gender claim",
                      germany["team_type_evidence"]["scope"])
        self.assertFalse(report["database_writes"])
        self.assertEqual(report["provider_links_created"], 0)

    def test_empty_country_is_not_inferred_from_competition(self):
        report = build_scope_report(
            [{"provider_entity_id": "201", "name": "Example",
              "raw_payload": {"competition_provider_ids": ["fra.1"]}}],
            {"fra.1": {"status": "ok", "clubs": [
                {"id": "201", "name": "Example", "country": "", "catalogSource": "match-snapshot"}
            ], "meta": {}}},
        )
        france = report["competitions"][1]
        self.assertEqual(france["country_value_counts"], {})
        self.assertEqual(france["matched_teams"][0]["country"], None)
        self.assertEqual(france["catalog_source_counts"], {"match-snapshot": 1})


if __name__ == "__main__":
    unittest.main()
