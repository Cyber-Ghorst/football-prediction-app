import unittest

from competition_registry import (
    build_discovered_competition_registry,
    validate_explicit_competition_crosswalk,
)


class CompetitionRegistryTests(unittest.TestCase):
    def setUp(self):
        self.leagues = [
            {"id": 8, "name": "Premier League", "country": {"name": "England"}},
            {"id": 9, "name": "Premier League", "country": {"name": "Kenya"}},
        ]
        self.seasons = [
            {"id": 100, "league_id": 8, "name": "2026/2027", "is_current": True},
            {"id": 101, "league_id": 9, "name": "2026", "is_current": True},
            {"id": 102, "league_id": 999, "name": "2026"},
            {"id": 100, "league_id": 8, "name": "2026/2027"},
        ]

    def test_discovery_registers_exact_provider_league_season_pairs(self):
        rows = build_discovered_competition_registry(
            self.leagues, self.seasons, provider="Sportmonks"
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            {(row["provider_competition_id"], row["provider_season_id"]) for row in rows},
            {("8", "100"), ("9", "101")},
        )
        self.assertTrue(all(row["registration_status"] == "registered" for row in rows))
        self.assertTrue(all(row["crosswalk_status"] == "unmapped" for row in rows))
        self.assertTrue(all(row["prediction_ready"] is False for row in rows))

    def test_orphan_season_and_duplicate_pair_are_not_registered_twice(self):
        rows = build_discovered_competition_registry(
            self.leagues, self.seasons, provider="sportmonks"
        )
        self.assertEqual(len(rows), 2)
        self.assertFalse(any(row["provider_competition_id"] == "999" for row in rows))

    def test_ambiguous_duplicate_provider_competition_id_is_rejected(self):
        leagues = self.leagues + [
            {"id": 8, "name": "Different Competition", "country": {"name": "England"}}
        ]
        rows = build_discovered_competition_registry(
            leagues, self.seasons, provider="sportmonks"
        )
        self.assertFalse(any(row["provider_competition_id"] == "8" for row in rows))

    def test_provider_ids_are_namespaced_and_do_not_auto_crosswalk(self):
        left = {
            "provider": "sportmonks", "provider_competition_id": "8",
            "provider_season_id": "100", "competition_name": "Premier League",
            "country": "England", "season_name": "2026/2027",
        }
        right = {
            "provider": "highlightly", "provider_competition_id": "8",
            "provider_season_id": "100", "competition_name": "Premier League",
            "country": "England", "season_name": "2026/2027",
        }
        result = validate_explicit_competition_crosswalk(left, right)
        self.assertTrue(result["candidate"])
        self.assertFalse(result["verified"])
        self.assertEqual(result["status"], "candidate_requires_explicit_verification")

    def test_country_or_season_mismatch_rejects_crosswalk_candidate(self):
        left = {
            "competition_name": "Premier League", "country": "England",
            "season_name": "2026/2027",
        }
        right = {
            "competition_name": "Premier League", "country": "Kenya",
            "season_name": "2026/2027",
        }
        self.assertFalse(validate_explicit_competition_crosswalk(left, right)["candidate"])

    def test_invalid_provider_is_rejected(self):
        with self.assertRaises(ValueError):
            build_discovered_competition_registry([], [], provider=" ")


if __name__ == "__main__":
    unittest.main()
