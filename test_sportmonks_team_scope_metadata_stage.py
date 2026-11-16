import unittest

from sportmonks_team_scope_metadata_stage import build_scope_updates


class SportmonksTeamScopeMetadataStageTests(unittest.TestCase):
    def test_uses_exact_country_mapping_and_preserves_provider_type_gender(self):
        rows = [{
            "provider_entity_id": "1",
            "country": None,
            "team_type": None,
            "gender_scope": None,
            "raw_payload": {"raw_payload": {
                "country_id": 32, "type": "domestic", "gender": "male"
            }},
        }]
        updates, held = build_scope_updates(rows, {"32": "Spain"})
        self.assertEqual(held, [])
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["country"], "Spain")
        self.assertEqual(updates[0]["team_type"], "domestic")
        self.assertEqual(updates[0]["gender_scope"], "male")
        self.assertFalse(updates[0]["already_matching"])

    def test_does_not_use_competition_country_or_unresolved_country_id(self):
        rows = [{
            "provider_entity_id": "1",
            "country": None,
            "team_type": None,
            "gender_scope": None,
            "raw_payload": {"raw_payload": {
                "country_id": 32, "type": "domestic", "gender": "male"
            }},
        }]
        updates, held = build_scope_updates(rows, {})
        self.assertEqual(updates, [])
        self.assertEqual(held[0]["reason"], "country_id_not_exactly_resolved")

    def test_conflicting_structured_values_are_held(self):
        rows = [{
            "provider_entity_id": "1",
            "country": "Italy",
            "team_type": "national",
            "gender_scope": "female",
            "raw_payload": {"raw_payload": {
                "country_id": 32, "type": "domestic", "gender": "male"
            }},
        }]
        updates, held = build_scope_updates(rows, {"32": "Spain"})
        self.assertEqual(updates, [])
        self.assertEqual(held[0]["reason"],
                         "existing_structured_scope_conflicts_with_provider_evidence")

    def test_existing_exact_values_are_not_rewritten(self):
        rows = [{
            "provider_entity_id": "1",
            "country": "Spain",
            "team_type": "domestic",
            "gender_scope": "male",
            "raw_payload": {"raw_payload": {
                "country_id": 32, "type": "domestic", "gender": "male"
            }},
        }]
        updates, held = build_scope_updates(rows, {"32": "Spain"})
        self.assertEqual(held, [])
        self.assertTrue(updates[0]["already_matching"])


if __name__ == "__main__":
    unittest.main()
