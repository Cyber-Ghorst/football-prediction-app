"""Tests for explicit, no-default OpenFooty freshness policy configuration."""
from __future__ import annotations

import math
import unittest

from openfooty_freshness_policy import load_openfooty_freshness_limits


class OpenFootyFreshnessPolicyTests(unittest.TestCase):
    def test_missing_values_produce_no_limits(self):
        self.assertEqual(load_openfooty_freshness_limits({}), {})

    def test_loads_each_explicit_evidence_limit(self):
        settings = {
            "OPENFOOTY_FIXTURE_MAX_AGE_HOURS": "36",
            "OPENFOOTY_AVAILABILITY_MAX_AGE_HOURS": 24,
            "OPENFOOTY_HISTORY_MAX_AGE_HOURS": "48.5",
        }
        self.assertEqual(
            load_openfooty_freshness_limits(settings),
            {"fixture": 36.0, "availability": 24.0, "history": 48.5},
        )

    def test_missing_evidence_class_stays_unspecified(self):
        settings = {"OPENFOOTY_FIXTURE_MAX_AGE_HOURS": "12"}
        self.assertEqual(
            load_openfooty_freshness_limits(settings),
            {"fixture": 12.0},
        )

    def test_environment_source_takes_precedence(self):
        environment = {"OPENFOOTY_HISTORY_MAX_AGE_HOURS": "12"}
        secrets = {"OPENFOOTY_HISTORY_MAX_AGE_HOURS": "24"}
        self.assertEqual(
            load_openfooty_freshness_limits(environment, secrets),
            {"history": 12.0},
        )

    def test_blank_setting_is_not_a_default(self):
        self.assertEqual(
            load_openfooty_freshness_limits(
                {"OPENFOOTY_HISTORY_MAX_AGE_HOURS": "  "}
            ),
            {},
        )

    def test_unavailable_secrets_source_is_ignored(self):
        class MissingSecrets:
            def get(self, key):
                raise RuntimeError("secrets unavailable")

        self.assertEqual(
            load_openfooty_freshness_limits(
                {"OPENFOOTY_FIXTURE_MAX_AGE_HOURS": "6"},
                MissingSecrets(),
            ),
            {"fixture": 6.0},
        )

    def test_rejects_non_positive_non_finite_and_invalid_values(self):
        key = "OPENFOOTY_HISTORY_MAX_AGE_HOURS"
        for value in ("0", "-1", "nan", "inf", "-inf", "not-a-number", True):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, key):
                    load_openfooty_freshness_limits({key: value})


if __name__ == "__main__":
    unittest.main()
