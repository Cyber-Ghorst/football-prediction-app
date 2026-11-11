import unittest
from unittest.mock import patch

from provider_league_catalogue_audit import audit_highlightly


class HighlightlyCatalogueTermsGateTests(unittest.TestCase):
    @patch("provider_league_catalogue_audit.requests.Session")
    def test_catalogue_audit_skips_before_network_access_without_acknowledgement(self, session):
        result = audit_highlightly(use_allowed=False)
        self.assertEqual(result["status"], "skipped")
        self.assertIn("non-betting-use confirmation", result["reason"])
        session.assert_not_called()


if __name__ == "__main__":
    unittest.main()
