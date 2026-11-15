import unittest

from provider_team_scope_evidence_audit import (
    build_team_scope_evidence_audit,
    extract_team_scope_evidence,
)


class ProviderTeamScopeEvidenceAuditTests(unittest.TestCase):
    def test_extracts_explicit_provider_fields_without_promoting_them(self):
        row = {
            "provider": "api_football",
            "provider_entity_id": "42",
            "name": "Example FC",
            "country": "England",
            "team_type": "club",
            "raw_payload": {
                "team_national_flag_from_provider": False,
                "raw_team": {
                    "national": False,
                    "country": "England",
                    "gender": "women",
                    "age_group": "U21",
                    "squad_scope": "reserve",
                },
            },
        }
        result = extract_team_scope_evidence(row)
        fields = {item["field"] for item in result["raw_provider_scope_candidates"]}
        self.assertTrue({"country", "team_type", "gender_scope", "age_group", "squad_scope"} <= fields)
        self.assertEqual(result["structured_scope_fields"], {"country": "England", "team_type": "club"})
        self.assertIn("not inferred or approved", result["interpretation"])

    def test_false_boolean_is_preserved_as_explicit_evidence(self):
        result = extract_team_scope_evidence({
            "provider": "api_football",
            "provider_entity_id": "42",
            "raw_payload": {"raw_team": {"national": False}},
        })
        self.assertIn(
            {"field": "team_type", "path": "raw_payload.raw_team.national", "value": False},
            result["raw_provider_scope_candidates"],
        )

    def test_missing_country_is_not_inferred_from_competition_context(self):
        result = extract_team_scope_evidence({
            "provider": "livescore_football",
            "provider_entity_id": "ger.1:team-1",
            "name": "Example",
            "raw_payload": {
                "competition_country": "Germany",
                "competition_provider_ids": ["ger.1"],
                "raw_team": {},
            },
        })
        self.assertNotIn("country", result["structured_scope_fields"])
        self.assertNotIn("country", {x["field"] for x in result["raw_provider_scope_candidates"]})

    def test_report_counts_each_provider_without_creating_identities(self):
        report = build_team_scope_evidence_audit([
            {"provider": "sportmonks", "provider_entity_id": "1", "raw_payload": {"raw_team": {"country": "Italy"}}},
            {"provider": "api_football", "provider_entity_id": "2", "team_type": "club", "raw_payload": {"raw_team": {"national": False}}},
        ])
        self.assertTrue(report["read_only"])
        self.assertEqual(report["canonical_ids_assigned"], 0)
        self.assertEqual(report["provider_links_created"], 0)
        self.assertEqual(report["team_rows_examined"], 2)
        self.assertEqual(report["providers"]["sportmonks"]["team_rows"], 1)
        self.assertEqual(report["providers"]["api_football"]["structured_scope_field_counts"]["team_type"], 1)


if __name__ == "__main__":
    unittest.main()
