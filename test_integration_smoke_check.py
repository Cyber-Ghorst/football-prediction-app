import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from integration_smoke_check import (
    api_football_account_probe,
    api_ninjas_use_skip_details,
    highlightly_refresh_cooldown_skip_details,
    highlightly_use_skip_details,
    run_check,
)


class ProviderUseAcknowledgementTests(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_highlightly_probe_is_skipped_without_both_acknowledgements(self):
        details = highlightly_use_skip_details()
        self.assertEqual(details["reason"], "provider_use_not_confirmed")
        self.assertIn("HIGHLIGHTLY_NON_BETTING_USE_CONFIRMED", details["required_acknowledgements"])

    @patch.dict(
        "os.environ",
        {
            "FREE_FIXTURE_TERMS_ACK_HIGHLIGHTLY": "true",
            "HIGHLIGHTLY_NON_BETTING_USE_CONFIRMED": "true",
        },
        clear=True,
    )
    def test_highlightly_probe_can_run_after_both_acknowledgements(self):
        details = highlightly_use_skip_details()
        self.assertNotEqual(
            (details or {}).get("reason"),
            "provider_use_not_confirmed",
        )

    @patch.dict("os.environ", {}, clear=True)
    def test_api_ninjas_probe_is_skipped_without_noncommercial_acknowledgement(self):
        details = api_ninjas_use_skip_details()
        self.assertEqual(details["reason"], "free_plan_noncommercial_use_not_confirmed")
        self.assertIn("FREE_FIXTURE_NONCOMMERCIAL_ACK_API_NINJAS", details["required_acknowledgements"])

    def test_run_check_does_not_call_provider_when_use_is_not_acknowledged(self):
        callback = Mock()
        result = run_check(
            "highlightly", True, callback,
            skip_details={"reason": "provider_use_not_confirmed"},
        )
        self.assertEqual(result["status"], "skipped")
        callback.assert_not_called()


class APIFootballAccountProbeTests(unittest.TestCase):
    def test_status_probe_returns_only_plan_and_quota_metadata(self):
        client = Mock()
        client.status.return_value = {
            "response": {
                "account": {"email": "private@example.com", "firstname": "Private"},
                "subscription": {"plan": "Pro", "active": True},
                "requests": {"current": 23, "limit_day": 7500},
            }
        }
        client.leagues.return_value = [{"league": {"id": 1}}, {"league": {"id": 2}}]

        result = api_football_account_probe(client)

        self.assertEqual(result["leagues_returned"], 2)
        self.assertEqual(result["subscription_plan"], "Pro")
        self.assertTrue(result["subscription_active"])
        self.assertEqual(result["requests_used_today"], 23)
        self.assertEqual(result["requests_limit_per_day"], 7500)
        self.assertTrue(result["status_endpoint_quota_exempt"])
        self.assertNotIn("email", str(result))
        self.assertNotIn("Private", str(result))
        client.close.assert_called_once()


class HighlightlyCooldownSmokeCheckTests(unittest.TestCase):
    def test_refresh_cooldown_skips_redundant_live_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "provider-refresh.json"
            report_path.write_text(json.dumps({
                "providers": {
                    "highlightly": {
                        "skipped": "refresh_cooldown",
                        "cooldown_hours": 23,
                        "last_successful_snapshot_at": "2026-11-11T09:37:08+00:00",
                    }
                }
            }), encoding="utf-8")
            details = highlightly_refresh_cooldown_skip_details(report_path)
        self.assertEqual(details["reason"], "provider_refresh_cooldown_active")
        self.assertEqual(details["cooldown_hours"], 23)

    def test_no_skip_when_provider_refresh_is_not_in_cooldown(self):
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "provider-refresh.json"
            report_path.write_text(json.dumps({
                "providers": {"highlightly": {"skipped": None}}
            }), encoding="utf-8")
            self.assertIsNone(highlightly_refresh_cooldown_skip_details(report_path))

    def test_skip_details_prevent_provider_request(self):
        callback = Mock(side_effect=AssertionError("probe must not run"))
        result = run_check(
            "highlightly",
            True,
            callback,
            skip_details={"reason": "provider_refresh_cooldown_active"},
        )
        callback.assert_not_called()
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "provider_refresh_cooldown_active")


if __name__ == "__main__":
    unittest.main()
