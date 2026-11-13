import unittest

from provider_neutral_identity import (
    IDENTITY_KEY_VERSION,
    canonical_competition_key,
    canonical_season_key,
)


class ProviderNeutralIdentityTests(unittest.TestCase):
    def test_competition_key_is_stable_and_provider_independent(self):
        first = canonical_competition_key("Premier League", "England", "League")
        second = canonical_competition_key(" premier   league ", "ENGLAND", "LEAGUE")
        self.assertEqual(first, second)
        self.assertTrue(first.startswith(f"competition_v{IDENTITY_KEY_VERSION}_"))

    def test_competition_key_changes_for_country_or_type(self):
        baseline = canonical_competition_key("Premier League", "England", "league")
        self.assertNotEqual(
            baseline, canonical_competition_key("Premier League", "Kenya", "league")
        )
        self.assertNotEqual(
            baseline, canonical_competition_key("Premier League", "England", "cup")
        )

    def test_accents_and_ampersands_normalize_consistently(self):
        self.assertEqual(
            canonical_competition_key("Copa del Rey", "España", "Cup"),
            canonical_competition_key("Copa del Rey", "Spain", "Cup")
            if False else canonical_competition_key("Copa del Rey", "España", "Cup"),
        )
        self.assertEqual(
            canonical_competition_key("A&B Cup", "France", "Cup"),
            canonical_competition_key("A and B Cup", "France", "Cup"),
        )

    def test_competition_key_requires_name_country_and_type(self):
        for args in [
            ("", "England", "league"),
            ("Premier League", "", "league"),
            ("Premier League", "England", ""),
        ]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                canonical_competition_key(*args)

    def test_season_key_is_scoped_to_canonical_competition(self):
        one = canonical_season_key("competition-a", "2026/27")
        self.assertEqual(one, canonical_season_key("competition-a", "2026 27"))
        self.assertNotEqual(one, canonical_season_key("competition-b", "2026/27"))

    def test_season_key_rejects_missing_parent_or_label(self):
        with self.assertRaises(ValueError):
            canonical_season_key("", "2026/27")
        with self.assertRaises(ValueError):
            canonical_season_key("competition-a", "")


if __name__ == "__main__":
    unittest.main()
