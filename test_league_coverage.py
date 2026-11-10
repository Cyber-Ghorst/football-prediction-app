import unittest

from league_coverage import build_league_coverage_dashboard


class LeagueCoverageDashboardTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {
                "identity_key": "sportmonks|8|100",
                "provider": "sportmonks",
                "competition_name": "Premier League",
                "country": "England",
                "season_name": "2026/2027",
                "season_start": "2026-08-01",
                "prediction_ready": False,
                "readiness_reason": "Independent identity and data-quality validation required.",
            },
            {
                "identity_key": "sportmonks|9|101",
                "provider": "sportmonks",
                "competition_name": "National League",
                "country": "Kenya",
                "season_name": "2026",
                "prediction_ready": True,
            },
            {
                "identity_key": "highlightly|3|44",
                "provider": "highlightly",
                "competition_name": "Example Cup",
                "country": "Example",
                "season_name": "2026",
                "prediction_ready": False,
            },
        ]
        self.providers = [
            {"provider_id": "sportmonks", "adapter": "implemented", "credential_configured": True},
            {"provider_id": "highlightly", "adapter": "implemented", "credential_configured": False},
        ]

    def test_classifies_discovered_supported_incomplete_and_ready(self):
        report = build_league_coverage_dashboard(self.records, self.providers)
        self.assertEqual(report["summary"]["discovered"], 3)
        self.assertEqual(report["summary"]["supported"], 2)
        self.assertEqual(report["summary"]["incomplete"], 1)
        self.assertEqual(report["summary"]["prediction_ready"], 1)
        rows = {row["identity_key"]: row for row in report["competitions"]}
        self.assertEqual(rows["sportmonks|8|100"]["coverage_status"], "incomplete")
        self.assertEqual(rows["sportmonks|9|101"]["coverage_status"], "prediction_ready")
        self.assertEqual(rows["highlightly|3|44"]["coverage_status"], "discovered_credential_unconfirmed")

    def test_discovery_never_promotes_prediction_readiness(self):
        report = build_league_coverage_dashboard(
            [self.records[0]], [{"provider_id": "sportmonks", "adapter": "implemented", "credential_configured": True}]
        )
        row = report["competitions"][0]
        self.assertFalse(row["prediction_ready"])
        self.assertTrue(row["incomplete"])

    def test_unconfigured_provider_is_discovered_only(self):
        report = build_league_coverage_dashboard([self.records[0]], [])
        row = report["competitions"][0]
        self.assertEqual(row["coverage_status"], "discovered_only")
        self.assertFalse(row["supported"])

    def test_duplicate_identity_is_counted_once(self):
        report = build_league_coverage_dashboard(
            self.records[:1] * 2, self.providers
        )
        self.assertEqual(report["summary"]["discovered"], 1)

    def test_empty_registry_returns_zero_counts(self):
        report = build_league_coverage_dashboard([], self.providers)
        self.assertEqual(report["summary"]["discovered"], 0)
        self.assertEqual(report["summary"]["prediction_ready"], 0)


if __name__ == "__main__":
    unittest.main()
