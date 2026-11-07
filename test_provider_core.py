import unittest
from datetime import datetime, timedelta, timezone

from provider_core import Observation, resolve_field, match_identity_key


NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


class ProviderCoreTests(unittest.TestCase):
    def obs(self, provider, value, **kwargs):
        return Observation(provider=provider, value=value, fetched_at=NOW, **kwargs)

    def test_verified_livescore_primary_wins_without_averaging_conflicts(self):
        result = resolve_field("results", [
            self.obs("api_ninjas", {"home": 2, "away": 1}),
            self.obs("livescore_football", {"home": 1, "away": 1}),
        ], now=NOW, livescore_verified=True)
        self.assertEqual(result.value, {"home": 1, "away": 1})
        self.assertEqual(result.provider, "livescore_football")
        self.assertEqual(result.status, "conflict")
        self.assertEqual(result.conflicting_providers, ("api_ninjas",))

    def test_unverified_livescore_is_never_selected(self):
        result = resolve_field("results", [
            self.obs("livescore_football", {"home": 1, "away": 1}),
            self.obs("api_ninjas", {"home": 2, "away": 1}),
        ], now=NOW)
        self.assertEqual(result.provider, "api_ninjas")
        self.assertEqual(result.value, {"home": 2, "away": 1})

    def test_livescore_not_allowed_for_statistics_even_if_verified(self):
        result = resolve_field("statistics", [
            self.obs("livescore_football", 80),
            self.obs("api_football", 12),
        ], now=NOW, livescore_verified=True)
        self.assertEqual(result.provider, "api_football")
        self.assertEqual(result.value, 12)

    def test_agreement_is_reported_as_corroborated(self):
        result = resolve_field("standings", [
            self.obs("api_ninjas", 1),
            self.obs("highlightly", 1),
        ], now=NOW)
        self.assertEqual(result.value, 1)
        self.assertEqual(result.status, "corroborated")
        self.assertEqual(result.corroborating_providers, ("api_ninjas",))

    def test_statistics_use_sportmonks_priority_when_validated(self):
        result = resolve_field("statistics", [
            self.obs("highlightly", 14),
            self.obs("api_football", 12),
            self.obs("sportmonks", 13),
        ], now=NOW)
        self.assertEqual(result.value, 13)
        self.assertEqual(result.provider, "sportmonks")
        self.assertEqual(result.status, "conflict")

    def test_current_season_domains_prioritize_sportmonks(self):
        for domain in ("fixtures", "results", "standings"):
            result = resolve_field(domain, [
                self.obs("api_ninjas", "secondary"),
                self.obs("highlightly", "corroboration"),
                self.obs("api_football", "historical"),
                self.obs("sportmonks", "current-season"),
            ], now=NOW)
            self.assertEqual(result.provider, "sportmonks")

    def test_invalid_null_and_stale_values_are_excluded(self):
        result = resolve_field("results", [
            self.obs("api_ninjas", None),
            Observation("highlightly", 3, NOW - timedelta(days=4)),
            Observation("api_football", 2, NOW, valid=False),
        ], now=NOW, max_age_seconds=3600)
        self.assertIsNone(result.value)
        self.assertEqual(result.status, "unknown")

    def test_unknown_provider_is_not_used(self):
        result = resolve_field("results", [self.obs("unknown_source", 4)], now=NOW)
        self.assertIsNone(result.value)

    def test_fixture_kickoff_equivalent_iso_formats_are_corroborated(self):
        result = resolve_field("fixtures", [
            self.obs("sportmonks", "2026-10-31 15:00:00"),
            self.obs("api_ninjas", "2026-10-31T15:00:00+00:00"),
        ], now=NOW)
        self.assertEqual(result.value, "2026-10-31 15:00:00")
        self.assertEqual(result.provider, "sportmonks")
        self.assertEqual(result.status, "corroborated")
        self.assertEqual(result.corroborating_providers, ("api_ninjas",))
        self.assertEqual(result.conflicting_providers, ())

    def test_fixture_kickoff_timezone_offsets_compare_as_same_instant(self):
        result = resolve_field("fixtures", [
            self.obs("sportmonks", "2026-10-31T18:00:00+03:00"),
            self.obs("api_ninjas", "2026-10-31T15:00:00Z"),
        ], now=NOW)
        self.assertEqual(result.status, "corroborated")

    def test_fixture_kickoff_real_time_difference_remains_conflict(self):
        result = resolve_field("fixtures", [
            self.obs("sportmonks", "2026-10-31T15:00:00Z"),
            self.obs("api_ninjas", "2026-10-31T16:00:00Z"),
        ], now=NOW)
        self.assertEqual(result.status, "conflict")
        self.assertEqual(result.conflicting_providers, ("api_ninjas",))

    def test_non_fixture_strings_are_not_datetime_coerced(self):
        result = resolve_field("results", [
            self.obs("sportmonks", "2026-10-31 15:00:00"),
            self.obs("api_ninjas", "2026-10-31T15:00:00+00:00"),
        ], now=NOW)
        self.assertEqual(result.status, "conflict")

    def test_match_identity_normalizes_team_names_and_timezone(self):
        a = match_identity_key("EPL", 2026, "2026-11-07T15:00:30Z", "Arsenal FC", "Chelsea")
        b = match_identity_key("epl", "2026", "2026-11-07T15:00:00+00:00", "arsenal-fc", "Chelsea")
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
