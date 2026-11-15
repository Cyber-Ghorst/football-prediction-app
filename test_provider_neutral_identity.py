import unittest

from provider_neutral_identity import (
    IDENTITY_KEY_VERSION,
    canonical_competition_key,
    canonical_season_key,
    canonical_team_key,
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
            canonical_competition_key("Copa del Réy", "Spain", "Cup"),
            canonical_competition_key("Copa del Rey", "Spain", "Cup"),
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

    def test_team_key_is_stable_and_scope_aware(self):
        first = canonical_team_key(
            "Manchester United", "England", "club", "men", "senior", "first team"
        )
        second = canonical_team_key(
            " manchester   united ", "ENGLAND", "CLUB", "MEN", "SENIOR", "FIRST-TEAM"
        )
        self.assertEqual(first, second)
        self.assertTrue(first.startswith(f"team_v{IDENTITY_KEY_VERSION}_"))

    def test_team_key_separates_club_national_gender_age_and_squad_scope(self):
        baseline = canonical_team_key(
            "United", "England", "club", "men", "senior", "first team"
        )
        variants = [
            ("United", "England", "national", "men", "senior", "first team"),
            ("United", "England", "club", "women", "senior", "first team"),
            ("United", "England", "club", "men", "u21", "first team"),
            ("United", "England", "club", "men", "senior", "reserve"),
            ("United", "Scotland", "club", "men", "senior", "first team"),
        ]
        for args in variants:
            with self.subTest(args=args):
                self.assertNotEqual(baseline, canonical_team_key(*args))

    def test_team_key_requires_every_identity_scope_dimension(self):
        baseline = ["United", "England", "club", "men", "senior", "first team"]
        for index in range(len(baseline)):
            args = list(baseline)
            args[index] = ""
            with self.subTest(index=index), self.assertRaises(ValueError):
                canonical_team_key(*args)

    def test_identity_keys_reject_unknown_placeholder_dimensions(self):
        competition = ["Premier League", "England", "league"]
        for index in range(3):
            args = list(competition)
            args[index] = "unknown"
            with self.subTest(kind="competition", index=index), self.assertRaises(ValueError):
                canonical_competition_key(*args)

        for placeholder in ("unknown", "N/A", "unspecified", "TBD", "not applicable"):
            with self.subTest(kind="season", placeholder=placeholder), self.assertRaises(ValueError):
                canonical_season_key("competition-a", placeholder)

        team = ["United", "England", "club", "men", "senior", "first team"]
        for index in (0, 1, 3, 4, 5):
            args = list(team)
            args[index] = "unknown"
            with self.subTest(kind="team", index=index), self.assertRaises(ValueError):
                canonical_team_key(*args)

    def test_team_key_rejects_unverified_team_type(self):
        with self.assertRaises(ValueError):
            canonical_team_key(
                "United", "England", "unknown", "men", "senior", "first team"
            )


if __name__ == "__main__":
    unittest.main()
