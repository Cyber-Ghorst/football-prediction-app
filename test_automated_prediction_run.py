import unittest

from automated_prediction_run import resolve_option


class AutomatedPredictionRunTests(unittest.TestCase):
    def test_exact_display_option_is_preferred(self):
        self.assertEqual(
            resolve_option(["Premier League — England", "La Liga — Spain"], "Premier League — England", "competition"),
            "Premier League — England",
        )

    def test_unique_name_prefix_resolves_display_label(self):
        self.assertEqual(
            resolve_option(["Premier League — England", "La Liga — Spain"], "Premier League", "competition"),
            "Premier League — England",
        )

    def test_ambiguous_name_requires_full_display_label(self):
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            resolve_option(["Premier League — England", "Premier League — India"], "Premier League", "competition")

    def test_missing_option_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "was not returned"):
            resolve_option(["Premier League — England"], "Bundesliga", "competition")

    def test_empty_selection_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "required"):
            resolve_option(["Arsenal", "Chelsea"], "", "home team")


if __name__ == "__main__":
    unittest.main()
