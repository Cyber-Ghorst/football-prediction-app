"""Tests for kickoff evidence quality classification."""

import unittest

from priority_a_provider_observation_audit import _kickoff_quality


class KickoffQualityTests(unittest.TestCase):
    def test_timezone_aware_kickoff_is_valid(self):
        self.assertEqual(_kickoff_quality("2026-11-21T15:00:00Z"), "valid_timezone_aware")

    def test_naive_datetime_is_not_assumed_to_be_utc(self):
        self.assertEqual(_kickoff_quality("2026-11-21T15:00:00"), "invalid_or_timezone_naive")

    def test_missing_kickoff_is_distinguished(self):
        self.assertEqual(_kickoff_quality(None), "missing")

    def test_malformed_kickoff_is_invalid(self):
        self.assertEqual(_kickoff_quality("next Saturday"), "invalid_or_timezone_naive")


if __name__ == "__main__":
    unittest.main()
