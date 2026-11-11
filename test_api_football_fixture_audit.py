import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from api_football_fixture_audit import build_api_football_fixture_audit


NOW = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)


def fixture(fid, kickoff, *, status="NS", league_id=39, season=2026,
            home_id=10, away_id=20):
    return {
        "fixture": {"id": fid, "date": kickoff, "status": {"short": status}},
        "league": {"id": league_id, "name": f"League {league_id}", "country": "England", "season": season},
        "teams": {
            "home": {"id": home_id, "name": "Home FC"},
            "away": {"id": away_id, "name": "Away FC"},
        },
    }


class APIFootballFixtureAuditTests(unittest.TestCase):
    def test_audit_counts_only_future_scheduled_fully_identified_fixtures(self):
        client = MagicMock()
        client.__enter__.return_value = client
        client.status.return_value = {
            "requests": {"current": 12, "limit_day": 100},
            "subscription": {"plan": "Test"},
        }
        fixtures_by_date = {
            "2026-11-11": [
                fixture(1, "2026-11-11T13:00:00+00:00"),
                fixture(3, "2026-11-11T11:00:00Z"),
            ],
            "2026-11-12": [
                fixture(2, "2026-11-12T15:00:00Z", league_id=140, home_id=11, away_id=21),
            ],
            "2026-11-13": [fixture(4, "2026-11-13T15:00:00Z", status="FT")],
            "2026-11-14": [fixture(5, "2026-11-14T15:00:00Z", away_id=None)],
            "2026-11-15": [fixture(6, "2026-11-15T15:00:00Z", status="TBD")],
        }
        def query_date(day, timezone="UTC"):
            client.last_fixture_request_count = 1
            return fixtures_by_date.get(day, [])
        client.fixtures_by_date.side_effect = query_date
        report = build_api_football_fixture_audit(
            client_factory=lambda: client, now=NOW,
        )
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["future_fixture_count"], 3)
        self.assertEqual(report["rejected_fixture_counts"]["kickoff_time_not_confirmed"], 1)
        self.assertEqual(report["prediction_ready_fixture_count"], 2)
        self.assertEqual(report["daily_fixture_counts_utc"]["2026-11-11"], 1)
        self.assertEqual(report["daily_fixture_counts_utc"]["2026-11-12"], 1)
        self.assertEqual(report["rejected_fixture_counts"]["outside_rolling_window"], 1)
        self.assertEqual(report["rejected_fixture_counts"]["not_scheduled"], 1)
        self.assertEqual(report["rejected_fixture_counts"]["missing_competition_season_or_team_identity"], 1)
        self.assertEqual(report["requests_made"], 8)
        self.assertEqual(report["subscription_plan"], "Test")
        self.assertEqual(report["writes"]["prediction_ledger_writes"], 0)

    def test_quota_exhaustion_stops_before_fixture_request(self):
        client = MagicMock()
        client.__enter__.return_value = client
        client.status.return_value = {"requests": {"current": 100, "limit_day": 100}}
        report = build_api_football_fixture_audit(
            client_factory=lambda: client, now=NOW,
        )
        self.assertEqual(report["status"], "quota_exhausted")
        client.fixtures_by_date.assert_not_called()

    def test_insufficient_quota_stops_before_date_queries(self):
        client = MagicMock()
        client.__enter__.return_value = client
        client.status.return_value = {"requests": {"current": 93, "limit_day": 100}}
        report = build_api_football_fixture_audit(
            client_factory=lambda: client, now=NOW,
        )
        self.assertEqual(report["status"], "quota_insufficient")
        client.fixtures_by_date.assert_not_called()


    def test_partial_boundary_date_is_reported_but_not_targeted(self):
        client = MagicMock()
        client.__enter__.return_value = client
        client.status.return_value = {"requests": {"current": 1, "limit_day": 100}}
        def query_date(day, timezone="UTC", max_pages=20):
            client.last_fixture_request_count = 1
            if day == "2026-11-18":
                return [fixture(1, "2026-11-18T10:00:00+00:00")]
            return []
        client.fixtures_by_date.side_effect = query_date
        report = build_api_football_fixture_audit(
            client_factory=lambda: client, now=NOW,
        )
        self.assertIn("2026-11-18", report["partial_boundary_days_utc"])
        self.assertEqual(report["daily_fixture_counts_utc"]["2026-11-18"], 1)
        self.assertNotIn("2026-11-18", report["daily_target_shortfalls_utc"])

    def test_naive_now_is_rejected(self):
        client = MagicMock()
        with self.assertRaises(ValueError):
            build_api_football_fixture_audit(
                client_factory=lambda: client,
                now=datetime(2026, 11, 11, 12, 0),
            )
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
