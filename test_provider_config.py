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
                'open_matchday', 'worldcup26', 'bzzoiro',
            ],
        )

    def test_livescore_is_limited_to_fixtures_results_and_standings(self):
        self.assertEqual(set(PROVIDER_ROLES['livescore_football']['domains']), {'fixtures', 'results', 'standings'})

    def test_readiness_reports_current_opt_in_layer2_integrations(self):
        rows = {row["provider_id"]: row for row in provider_readiness()}
        self.assertIn("opt-in missing-score fallback", rows["livescore_football"]["app_integration"])
        self.assertIn("missing-stat", rows["highlightly"]["app_integration"])
        self.assertIn("exact result candidates", rows["api_ninjas"]["app_integration"])
        self.assertIn("active", rows["sportmonks"]["app_integration"])

    def test_readiness_exposes_role_and_credential_status_without_secret_values(self):
        rows = provider_readiness()
        self.assertEqual(len(rows), 10)
        for row in rows:
            self.assertIn('role', row)
            self.assertIn('limitation', row)
            self.assertIn('credential_configured', row)

    def test_free_sources_are_candidate_only_and_bzzoiro_is_the_only_new_keyed_source(self):
        rows = {row["provider_id"]: row for row in provider_readiness()}
        candidates = ("openligadb", "openfootball", "open_matchday", "worldcup26", "bzzoiro")
        for provider in candidates:
            self.assertEqual(rows[provider]["adapter"], "candidate_only_not_implemented")
            self.assertIn("candidate registered only", rows[provider]["app_integration"])
        self.assertFalse(rows["openligadb"]["credential_required"])
        self.assertFalse(rows["openfootball"]["credential_required"])
        self.assertFalse(rows["open_matchday"]["credential_required"])
        self.assertFalse(rows["worldcup26"]["credential_required"])
        self.assertTrue(rows["bzzoiro"]["credential_required"])
        self.assertEqual(rows["bzzoiro"]["credential_name"], "BZZOIRO_API_TOKEN")


if __name__ == '__main__':
    unittest.main()
