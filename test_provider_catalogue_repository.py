import unittest

from provider_catalogue_repository import (
    provider_entity_id,
    prepare_provider_catalogue,
)


class ProviderCatalogueRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.league = {
            "id": 52695, "name": "Ligue 1", "countryName": "France",
            "type": "league",
        }
        self.season = {
            "id": 2026, "league_id": 52695, "name": "2026",
            "startDate": "2026-08-01", "endDate": "2027-05-31",
        }
        self.teams = [
            {"id": 1, "name": "Paris FC"},
            {"id": 2, "name": "Olympique Lyonnais"},
            {"id": 2, "name": "Duplicate provider row"},
            {"name": "Missing ID"},
        ]

    def test_provider_ids_are_namespaced(self):
        self.assertEqual(provider_entity_id("Highlightly", 52695), "highlightly:52695")
        self.assertNotEqual(provider_entity_id("highlightly", 8),
                            provider_entity_id("sportmonks", 8))

    def test_catalogue_is_prepared_without_cross_provider_promotion(self):
        result = prepare_provider_catalogue(
            "highlightly", league=self.league, season=self.season, teams=self.teams,
        )
        self.assertEqual(result["league"]["league_id"], "highlightly:52695")
        self.assertEqual(result["season"]["season_id"], "highlightly:2026")
        self.assertEqual(result["season"]["league_id"], "highlightly:52695")
        self.assertEqual([row["team_id"] for row in result["teams"]],
                         ["highlightly:1", "highlightly:2"])
        self.assertIsNone(result["teams"][0]["country"])
        self.assertEqual(result["fixtures_imported"], 0)
        self.assertEqual(result["cross_provider_links_created"], 0)

    def test_wrong_season_parent_is_rejected(self):
        season = dict(self.season, league_id=999)
        with self.assertRaises(ValueError):
            prepare_provider_catalogue(
                "highlightly", league=self.league, season=season, teams=self.teams,
            )

    def test_missing_country_is_rejected_instead_of_assumed(self):
        league = dict(self.league, countryName=None)
        with self.assertRaises(ValueError):
            prepare_provider_catalogue(
                "highlightly", league=league, season=self.season, teams=self.teams,
            )

    def test_provider_ids_never_collide_between_sources(self):
        a = prepare_provider_catalogue(
            "highlightly", league=self.league, season=self.season, teams=self.teams,
        )
        b = prepare_provider_catalogue(
            "sportmonks", league=dict(self.league, id=52695),
            season=self.season, teams=self.teams,
        )
        self.assertNotEqual(a["league"]["league_id"], b["league"]["league_id"])
        self.assertNotEqual(a["teams"][0]["team_id"], b["teams"][0]["team_id"])

    def test_international_scope_must_be_explicit(self):
        league = dict(self.league, countryName="World")
        result = prepare_provider_catalogue(
            "highlightly", league=league, season=self.season, teams=self.teams,
        )
        self.assertEqual(result["league"]["country"], "World")


if __name__ == "__main__":
    unittest.main()
