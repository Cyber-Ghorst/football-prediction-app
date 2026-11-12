import unittest

from provider_config import PROVIDER_ROLES, provider_readiness


class ProviderRoleConfigTests(unittest.TestCase):
    def test_ranked_provider_roles_are_explicit(self):
        ordered = sorted(PROVIDER_ROLES.items(), key=lambda item: item[1]['rank'])
        self.assertEqual(
            [key for key, _ in ordered],
            [
                'sportmonks', 'highlightly', 'api_football', 'api_ninjas',
                'livescore_football', 'openligadb', 'openfootball',
                'open_matchday', 'bzzoiro', 'openscores', 'football_data_org',
            ],
        )

    def test_livescore_has_scheduled_fixture_and_result_enrichment_domains(self):
        self.assertEqual(
            set(PROVIDER_ROLES['livescore_football']['domains']),
            {'future_fixtures', 'fixtures', 'results', 'standings'},
        )

    def test_only_selected_sources_are_future_fixture_candidates(self):
        future = {
            key for key, role in PROVIDER_ROLES.items()
            if "future_fixtures" in role["domains"]
        }
        self.assertEqual(
            future,
            {"sportmonks", "openligadb", "openfootball", "open_matchday", "livescore_football", "bzzoiro", "football_data_org"},
        )
        self.assertNotIn("future_fixtures", PROVIDER_ROLES["openscores"]["domains"])
        self.assertNotIn("fixtures", PROVIDER_ROLES["openscores"]["domains"])
        self.assertNotIn("future_fixtures", PROVIDER_ROLES["highlightly"]["domains"])
        self.assertNotIn("future_fixtures", PROVIDER_ROLES["api_ninjas"]["domains"])
        self.assertNotIn("future_fixtures", PROVIDER_ROLES["api_football"]["domains"])
        self.assertIn("future_fixtures", PROVIDER_ROLES["livescore_football"]["domains"])

    def test_readiness_reports_current_opt_in_layer2_integrations(self):
        rows = {row["provider_id"]: row for row in provider_readiness()}
        self.assertIn("opt-in missing-score fallback", rows["livescore_football"]["app_integration"])
        self.assertIn("missing-stat", rows["highlightly"]["app_integration"])
        self.assertIn("exact result candidates", rows["api_ninjas"]["app_integration"])
        self.assertIn("active", rows["sportmonks"]["app_integration"])

    def test_readiness_exposes_role_and_credential_status_without_secret_values(self):
        rows = provider_readiness()
        self.assertEqual(len(rows), 11)
        for row in rows:
            self.assertIn('role', row)
            self.assertIn('limitation', row)
            self.assertIn('credential_configured', row)

    def test_free_sources_are_candidate_only_and_bzzoiro_is_the_only_new_keyed_source(self):
        rows = {row["provider_id"]: row for row in provider_readiness()}
        candidates = ("openligadb", "openfootball", "open_matchday", "bzzoiro")
        for provider in candidates:
            self.assertEqual(rows[provider]["adapter"], "implemented")
            self.assertIn("adapter implemented", rows[provider]["app_integration"])
        self.assertFalse(rows["openligadb"]["credential_required"])
        self.assertFalse(rows["openfootball"]["credential_required"])
        self.assertFalse(rows["open_matchday"]["credential_required"])
        self.assertTrue(rows["bzzoiro"]["credential_required"])
        self.assertEqual(rows["livescore_football"]["adapter"], "implemented")
        self.assertIn("scheduled fixtures", rows["livescore_football"]["app_integration"])
        self.assertEqual(rows["bzzoiro"]["credential_name"], "BZZOIRO_API_TOKEN")
        self.assertEqual(rows["openscores"]["role"], "Read-only historical result observations and entity-mapping audit; not a future-fixture source")
        self.assertEqual(rows["openscores"]["credential_name"], "OPENSCORES_API_KEY")
        self.assertIn("not a future-fixture source", rows["openscores"]["app_integration"])\n        self.assertEqual(rows["football_data_org"]["adapter"], "implemented")\n        self.assertTrue(rows["football_data_org"]["credential_required"])\n        self.assertEqual(rows["football_data_org"]["credential_name"], "FOOTBALL_DATA_ORG_API_TOKEN")


if __name__ == '__main__':
    unittest.main()
