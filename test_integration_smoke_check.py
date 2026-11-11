import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from integration_smoke_check import (
    highlightly_refresh_cooldown_skip_details,
    run_check,
)


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
