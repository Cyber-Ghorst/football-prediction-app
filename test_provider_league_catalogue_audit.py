import unittest

from provider_league_catalogue_audit import audit_livescore


class ProviderLeagueCatalogueAuditTests(unittest.TestCase):
    def test_livescore_is_reported_as_historical_worldcup_only(self):
        report = audit_livescore()
        self.assertEqual(report["status"], "historical_only")
        self.assertFalse(report["future_fixture_eligible"])
        self.assertEqual(report["documented_matches"], 104)
        self.assertEqual(report["documented_teams"], 48)
        self.assertEqual(report["documented_historical_endpoint"], "/get/games")
        self.assertEqual(report["authentication_required"], "JWT")
        self.assertIn("HTTP 400", report["reason"])


if __name__ == "__main__":
    unittest.main()
