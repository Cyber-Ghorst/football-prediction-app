import unittest

from streamlit.testing.v1 import AppTest


class AppDefaultSettingsTests(unittest.TestCase):
    def test_optional_recent_result_corroboration_is_disabled_by_default(self):
        app = AppTest.from_file("app.py", default_timeout=90)
        app.run(timeout=90)

        self.assertFalse(app.exception)
        checkbox = next(
            (
                item for item in app.checkbox
                if item.label == "Cross-check recent results with Highlightly and API Ninjas"
            ),
            None,
        )
        self.assertIsNone(
            checkbox,
            "Restricted-provider controls should be hidden until permitted-use acknowledgements are configured.",
        )


if __name__ == "__main__":
    unittest.main()
