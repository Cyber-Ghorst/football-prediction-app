import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from independent_provider_refresh import refresh_independent_data_providers


class IndependentProviderRefreshTests(unittest.TestCase):
    def test_missing_token_skips_without_discovery_registration_or_writes(self):
        report = refresh_independent_data_providers(
            "provider-db", now=datetime(2026, 11, 12, tzinfo=timezone.utc)
        )
        self.assertEqual(report["provider_group"], "independent_data")
        self.assertEqual(report["providers"]["football_data_org"]["status"], "skipped")
        self.assertEqual(report["canonical_fixture_writes"], 0)
        self.assertEqual(report["prediction_ledger_writes"], 0)

    @patch("independent_provider_refresh.collect_football_data_org_observations")
    def test_collects_independent_observations_without_canonical_writes(self, collect):
        collect.return_value = {
            "archived": True, "observation_count": 12,
            "eligible_for_review_count": 10,
        }
        report = refresh_independent_data_providers(
            "provider-db",
            token="test-token",
            now=datetime(2026, 11, 12, tzinfo=timezone.utc),
        )
        collect.assert_called_once_with(
            "provider-db",
            date_from="2026-11-12",
            date_to="2026-11-19",
            api_token="test-token",
        )
        self.assertEqual(report["provider_group"], "independent_data")
        self.assertEqual(report["providers"]["football_data_org"]["status"], "ok")
        self.assertEqual(report["providers"]["football_data_org"]["observation_count"], 12)
        self.assertEqual(report["canonical_fixture_writes"], 0)
        self.assertEqual(report["prediction_ledger_writes"], 0)

    def test_requires_database_url(self):
        with self.assertRaisesRegex(ValueError, "PROVIDER_DATABASE_URL"):
            refresh_independent_data_providers("")


if __name__ == "__main__":
    unittest.main()
