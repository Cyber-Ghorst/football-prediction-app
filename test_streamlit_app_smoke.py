"""Streamlit application boot smoke test without external provider credentials."""
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from sportmonks import SportmonksClient, SportmonksError


class StreamlitApplicationSmokeTests(unittest.TestCase):
    def test_app_imports_and_stops_cleanly_when_primary_provider_is_unconfigured(self):
        # Force the no-credential path deterministically; this test must never
        # make live provider requests or depend on CI secrets.
        with patch.object(
            SportmonksClient,
            "__init__",
            side_effect=SportmonksError(
                "Sportmonks token missing. Configure SPORTMONKS_API_TOKEN in Streamlit Secrets."
            ),
        ):
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
