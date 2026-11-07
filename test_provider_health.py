import unittest
from datetime import datetime, timezone, timedelta

from provider_health import (
    assess_api_football_status, assess_freshness, assess_livescore_metadata,
    assess_livescore_competition_coverage, assess_livescore_fixture_freshness,
)


class ProviderHealthTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)

    def test_freshness_uses_domain_specific_limits(self):
        recent = self.now - timedelta(seconds=60)
        self.assertTrue(assess_freshness(recent, "live_scores", now=self.now)["fresh"])
        old_live = self.now - timedelta(seconds=180)
        self.assertFalse(assess_freshness(old_live, "live_scores", now=self.now)["fresh"])
        self.assertTrue(assess_freshness(old_live, "fixtures", now=self.now)["fresh"])

    def test_missing_and_invalid_timestamp_remain_unknown(self):
        for value in (None, "", "not-a-date"):
            result = assess_freshness(value, "fixtures", now=self.now)
            self.assertEqual(result["status"], "unknown")
            self.assertFalse(result["fresh"])

    def test_future_timestamp_is_invalid(self):
        result = assess_freshness(self.now + timedelta(minutes=1), "fixtures", now=self.now)
        self.assertEqual(result["status"], "invalid")

    def test_stale_livescore_sync_blocks_fallback(self):
        payload = {
            "service": {"dataSource": "MongoDB"},
            "coverage": {"competitions": 33},
            "lastSuccessfulSyncAt": (self.now - timedelta(days=2)).isoformat(),
        }
        result = assess_livescore_metadata(payload, now=self.now, domain="fixtures")
        self.assertFalse(result["fallback_eligible"])
        self.assertEqual(result["freshness"]["status"], "stale")

    def test_missing_livescore_sync_blocks_fallback(self):
        result = assess_livescore_metadata(
            {"service": {"dataSource": "MongoDB"}, "coverage": {}}, now=self.now
        )
        self.assertFalse(result["fallback_eligible"])
        self.assertEqual(result["freshness"]["status"], "unknown")

    def test_livescore_competition_requires_fresh_own_sync_timestamp(self):
        fresh = {
            "name": "Premier League", "slug": "eng.1", "active": True,
            "coverage": {"hasData": True, "lastSyncedAt": self.now.isoformat()},
        }
        self.assertTrue(assess_livescore_competition_coverage(fresh, now=self.now)["fallback_eligible"])
        stale = {
            **fresh,
            "coverage": {"hasData": True, "lastSyncedAt": (self.now - timedelta(days=2)).isoformat()},
        }
        self.assertFalse(assess_livescore_competition_coverage(stale, now=self.now)["fallback_eligible"])
        missing = {**fresh, "coverage": {"hasData": True}}
        self.assertFalse(assess_livescore_competition_coverage(missing, now=self.now)["fallback_eligible"])

    def test_livescore_fixture_requires_its_own_update_timestamp(self):
        fresh = assess_livescore_fixture_freshness(
            {"id": "fixture-1", "updatedAt": self.now.isoformat()}, now=self.now
        )
        self.assertTrue(fresh["eligible"])
        missing = assess_livescore_fixture_freshness({"id": "fixture-2"}, now=self.now)
        self.assertFalse(missing["eligible"])
        self.assertEqual(missing["freshness"]["status"], "unknown")

    def test_api_football_status_hides_account_identity_and_calculates_quota(self):
        result = assess_api_football_status({
            "account": {"firstname": "private", "email": "private@example.com"},
            "subscription": {"active": True, "plan": "Free"},
            "requests": {"current": 35, "limit_day": 100},
        })
        self.assertTrue(result["fallback_eligible"])
        self.assertEqual(result["daily_requests_remaining"], 65)
        self.assertNotIn("account", result)

    def test_inactive_api_football_subscription_blocks_fallback(self):
        result = assess_api_football_status({"subscription": {"active": False}})
        self.assertFalse(result["fallback_eligible"])


if __name__ == "__main__":
    unittest.main()
