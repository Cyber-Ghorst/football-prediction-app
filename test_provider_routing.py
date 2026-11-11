import unittest

from provider_routing import (
    FREE_FIXTURE_CANDIDATES,
    ProviderAssignment,
    ProviderRegistry,
    default_provider_registry,
)


class ProviderRoutingTests(unittest.TestCase):
    def test_multiple_primary_sources_can_share_one_category(self):
        registry = ProviderRegistry([
            ProviderAssignment("sportmonks", "fixtures", "primary", 10),
            ProviderAssignment("api_football", "fixtures", "co_primary", 20),
            ProviderAssignment("api_ninjas", "fixtures", "co_primary", 30),
        ])
        self.assertEqual(registry.primary_sources("fixtures"),
                         ["sportmonks", "api_football", "api_ninjas"])

    def test_competition_scoping_prevents_global_provider_override(self):
        registry = ProviderRegistry([
            ProviderAssignment("sportmonks", "fixtures", "primary"),
            ProviderAssignment("api_ninjas", "fixtures", "co_primary",
                               competitions=("premier league", "la liga")),
        ])
        self.assertEqual(registry.primary_sources("fixtures", "premier league"),
                         ["sportmonks", "api_ninjas"])
        self.assertEqual(registry.primary_sources("fixtures", "bundesliga"),
                         ["sportmonks"])

    def test_roles_are_separate_and_ordered_by_priority(self):
        registry = ProviderRegistry([
            ProviderAssignment("fallback_b", "fixtures", "fallback", 20),
            ProviderAssignment("primary_b", "fixtures", "co_primary", 20),
            ProviderAssignment("primary_a", "fixtures", "primary", 10),
            ProviderAssignment("validator", "fixtures", "validation", 1),
        ])
        result = registry.resolve("fixtures")
        self.assertEqual(result["primary"], ["primary_a"])
        self.assertEqual(result["co_primary"], ["primary_b"])
        self.assertEqual(result["fallback"], ["fallback_b"])
        self.assertEqual(result["validation"], ["validator"])

    def test_openscores_is_not_a_future_fixture_provider(self):
        registry = default_provider_registry()
        self.assertEqual(registry.primary_sources("future_fixtures"), ["sportmonks"])
        self.assertEqual(registry.primary_sources("future_fixtures", "premier league"), ["sportmonks"])
        self.assertNotIn("openscores", registry.primary_sources("fixtures"))
        self.assertNotIn("openscores", registry.primary_sources("future_fixtures"))
        self.assertEqual(registry.resolve("results")["validation"], [])

    def test_free_fixture_candidates_are_registered_but_not_routed(self):
        registry = default_provider_registry()
        self.assertEqual(
            set(FREE_FIXTURE_CANDIDATES),
            {"openligadb", "openfootball", "open_matchday", "thesportsdb", "bzzoiro"},
        )
        self.assertNotIn("worldcup26", FREE_FIXTURE_CANDIDATES)
        self.assertNotIn("livescore_football", registry.primary_sources("future_fixtures"))
        self.assertEqual(registry.primary_sources("future_fixtures"), ["sportmonks"])
        self.assertEqual(registry.primary_sources("future_fixtures", "premier league"), ["sportmonks"])

    def test_api_football_route_is_historical_category_specific(self):
        registry = default_provider_registry()
        self.assertEqual(registry.primary_sources("historical_fixtures", "premier league"),
                         ["api_football"])
        self.assertEqual(registry.primary_sources("fixtures"), ["sportmonks"])

    def test_duplicate_assignment_is_rejected(self):
        with self.assertRaises(ValueError):
            ProviderRegistry([
                ProviderAssignment("sportmonks", "fixtures", "primary"),
                ProviderAssignment("Sportmonks", "Fixtures", "primary"),
            ])

    def test_invalid_role_and_priority_are_rejected(self):
        with self.assertRaises(ValueError):
            ProviderAssignment("x", "fixtures", "dominant")
        with self.assertRaises(ValueError):
            ProviderAssignment("x", "fixtures", "primary", -1)


if __name__ == "__main__":
    unittest.main()
