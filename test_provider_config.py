import unittest

from provider_config import PROVIDER_ROLES, provider_readiness


class ProviderRoleConfigTests(unittest.TestCase):
    def test_ranked_provider_roles_are_explicit(self):
        ordered = sorted(PROVIDER_ROLES.items(), key=lambda item: item[1]['rank'])
        self.assertEqual([key for key, _ in ordered], ['sportmonks', 'highlightly', 'api_football', 'api_ninjas', 'livescore_football'])

    def test_livescore_is_limited_to_fixtures_results_and_standings(self):
        self.assertEqual(set(PROVIDER_ROLES['livescore_football']['domains']), {'fixtures', 'results', 'standings'})

    def test_readiness_exposes_role_and_credential_status_without_secret_values(self):
        rows = provider_readiness()
        self.assertEqual(len(rows), 5)
        for row in rows:
            self.assertIn('role', row)
            self.assertIn('limitation', row)
            self.assertIn('credential_configured', row)


if __name__ == '__main__':
    unittest.main()
