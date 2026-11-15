import unittest

from provider_neutral_repository import (
    build_provider_neutral_audit,
    normalize_repository_rows,
    split_provider_identity,
)


class ProviderNeutralRepositoryTests(unittest.TestCase):
    def test_namespaced_ids_keep_provider_and_provider_native_id(self):
        identity = split_provider_identity("highlightly:134391", "Highlightly")
        self.assertEqual(identity["provider"], "highlightly")
        self.assertEqual(identity["provider_entity_id"], "134391")
        self.assertEqual(identity["identity_status"], "namespaced_source_identity")

    def test_provider_prefix_mismatch_is_reported_not_rewritten(self):
        identity = split_provider_identity("sportmonks:8", "highlightly")
        self.assertEqual(identity["identity_status"], "provider_prefix_mismatch")
        self.assertEqual(identity["legacy_repository_id"], "sportmonks:8")

    def test_legacy_unprefixed_id_is_preserved_as_source_identity(self):
        identity = split_provider_identity("ger.1", "livescore_football")
        self.assertEqual(identity["provider_entity_id"], "ger.1")
        self.assertEqual(identity["identity_status"], "legacy_unprefixed")

    def test_fixture_references_are_normalized_without_canonical_ids(self):
        raw = {
            "fixtures": [{
                "fixture_id": "sportmonks:123",
                "season_id": "sportmonks:2026",
                "league_id": "sportmonks:8",
                "home_team_id": "sportmonks:31",
                "away_team_id": "sportmonks:32",
                "source_provider": "sportmonks",
                "starting_at": "2026-11-20T18:00:00Z",
            }]
        }
        normalized = normalize_repository_rows(raw)["fixtures"][0]
        self.assertEqual(normalized["source_identity"]["provider_entity_id"], "123")
        self.assertEqual(normalized["home_team_source_identity"]["provider_entity_id"], "31")
        self.assertEqual(normalized["away_team_source_identity"]["provider_entity_id"], "32")
        self.assertNotIn("canonical_entity_id", normalized)

    def test_audit_is_read_only_and_counts_each_provider_independently(self):
        raw = {
            "leagues": [
                {"league_id": "sportmonks:8", "source_provider": "sportmonks", "name": "Premier League"},
                {"league_id": "highlightly:67162", "source_provider": "highlightly", "name": "Bundesliga"},
            ],
            "teams": [
                {"team_id": "highlightly:134391", "source_provider": "highlightly", "name": "Bayern Munich"},
            ],
        }
        report = build_provider_neutral_audit(raw, [
            {"provider": "sportmonks"}, {"provider": "highlightly"},
        ])
        self.assertTrue(report["read_only"])
        self.assertEqual(report["writes_performed"], 0)
        self.assertEqual(report["application_owned_canonical_ids_assigned"], 0)
        self.assertEqual(report["normalized_entity_counts"]["leagues"], 2)
        self.assertEqual(report["provider_entity_counts"]["highlightly"]["teams"], 1)
        self.assertEqual(report["existing_approved_link_counts"]["sportmonks"], 1)
        self.assertEqual(report["invalid_source_identity_count"], 0)


if __name__ == "__main__":
    unittest.main()
