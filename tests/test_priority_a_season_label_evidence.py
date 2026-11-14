"""Tests for season-label evidence parsing in the read-only Priority A audit."""

import unittest

from priority_a_provider_observation_audit import _season_label_year_evidence


class SeasonLabelEvidenceTests(unittest.TestCase):
    def test_two_digit_european_season_label(self):
        self.assertEqual(
            _season_label_year_evidence("Bundesliga 26/27"),
            {
                "label": "Bundesliga 26/27",
                "start_year": 2026,
                "end_year": 2027,
                "normalized_season": "2026/2027",
                "format": "two_digit_season_range",
            },
        )

    def test_four_digit_start_year_with_two_digit_end(self):
        result = _season_label_year_evidence("2026-27")
        self.assertEqual((result["start_year"], result["end_year"]), (2026, 2027))

    def test_calendar_year_is_not_given_an_end_year(self):
        result = _season_label_year_evidence("2026")
        self.assertEqual((result["start_year"], result["end_year"]), (2026, None))

    def test_date_is_not_mistaken_for_a_season_range(self):
        self.assertIsNone(_season_label_year_evidence("2026-08-28"))

    def test_unparseable_label_returns_none(self):
        self.assertIsNone(_season_label_year_evidence("Current season"))


if __name__ == "__main__":
    unittest.main()
