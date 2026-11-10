"""Streamlit application boot smoke test without external provider credentials."""
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from sportmonks import SportmonksClient, SportmonksError


class StreamlitApplicationSmokeTests(unittest.TestCase):
    def test_tipmaster_dashboard_contains_refresh_and_persistence_diagnostics(self):
        source = Path("app.py").read_text(encoding="utf-8")
        for expected in (
            'st.button("Refresh TipMaster benchmark now"',
            'd1.metric("Stored benchmark records"',
            '"Neon persistence"',
            'd3.metric("Feed refresh"',
            '"Last refresh attempt:',
            '"Latest feed counts:',
            'TipMaster feed refresh failed',
        ):
            self.assertIn(expected, source)

    def test_app_imports_and_stops_cleanly_when_primary_provider_is_unconfigured(self):
        # Force the no-credential path deterministically; this test must never
        # make live provider requests or depend on CI secrets.
        with patch.object(
            SportmonksClient,
            "__init__",
            side_effect=SportmonksError(
                "Sportmonks token missing. Configure SPORTMONKS_API_TOKEN in Streamlit Secrets."
            ),
        ), patch("app.fetch_tipmaster_consensus", return_value={"matches": [], "counts": {}}):
            app = AppTest.from_file("app.py").run(timeout=60)

        self.assertEqual(
            len(app.exception),
            0,
            msg="The Streamlit app raised an uncaught exception during startup.",
        )
        self.assertTrue(
            any(
                "Sportmonks competition discovery failed" in str(item.value)
                for item in app.error
            ),
            msg="The app did not surface the expected controlled provider-configuration message.",
        )
        labels = {item.label: item.value for item in app.checkbox}
        self.assertFalse(labels.get("Use exact verified results to fill missing recent history", True))
        self.assertFalse(labels.get("Use fresh LiveScoreFootball to fill missing Sportmonks results", True))
        self.assertFalse(labels.get("Use Highlightly to fill missing match statistics", True))
        self.assertFalse(labels.get("Use Highlightly lineups when Sportmonks lineups are missing", True))


if __name__ == "__main__":
    unittest.main()
