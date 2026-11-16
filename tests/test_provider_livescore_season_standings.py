import unittest

from provider_roster_collection import collect_livescore_season_standings


class LiveScoreSeasonStandingsTests(unittest.TestCase):
    def setUp(self):
        self.league = {"slug": "ger.1", "name": "German Bundesliga", "country": "Germany"}
        self.payload = {
            "season": {"year": 2026, "name": "2026/27"},
            "standings": [{"team": {"id": "1", "name": "Example FC"}}],
        }

    def test_explicit_returned_season_admits_roster_and_preserves_provenance(self):
        class Client:
            def standings(self, league, season=None):
                self.assertEqual(league, "ger.1")
                self.assertEqual(season, 2026)
                return self.payload

        result = collect_livescore_season_standings(
            Client(), league=self.league, season_year=2026,
            retrieved_at="2026-11-16T12:00:00+00:00",
        )
        self.assertTrue(result["team_evidence_complete"])
        self.assertEqual(result["teams"][0]["id"], "1")
        self.assertEqual(result["provider_payload"], self.payload)
        self.assertEqual(result["source_endpoint"], "/get/soccer/ger.1/standings")
        self.assertEqual(result["source_retrieved_at"], "2026-11-16T12:00:00+00:00")

    def test_missing_or_mismatched_returned_season_is_held(self):
        for season in (None, {"year": 2025, "name": "2025/26"},
                       {"year": 2026, "name": "2026"}):
            payload = {"standings": self.payload["standings"]}
            if season is not None:
                payload["season"] = season

            class Client:
                def standings(self, league, season=None):
                    return payload

            result = collect_livescore_season_standings(
                Client(), league=self.league, season_year=2026, retrieved_at="now",
            )
            self.assertFalse(result["team_evidence_complete"])
            self.assertEqual(result["teams"], [])

    def test_duplicate_ids_and_names_are_held(self):
        payload = {
            "season": {"year": 2026, "name": "2026/27"},
            "standings": [
                {"team": {"id": "1", "name": "Example FC"}},
                {"team": {"id": "1", "name": "Different FC"}},
            ],
        }

        class Client:
            def standings(self, league, season=None):
                return payload

        result = collect_livescore_season_standings(
            Client(), league=self.league, season_year=2026, retrieved_at="now",
        )
        self.assertFalse(result["team_evidence_complete"])
        self.assertTrue(result["duplicate_team_ids"])

    def test_api_error_does_not_create_roster(self):
        class Client:
            def standings(self, league, season=None):
                raise RuntimeError("provider unavailable")

        with self.assertRaises(RuntimeError):
            collect_livescore_season_standings(
                Client(), league=self.league, season_year=2026, retrieved_at="now",
            )


if __name__ == "__main__":
    unittest.main()
