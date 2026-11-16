import unittest

from provider_roster_collection import collect_livescore_season_standings


class LiveScoreSeasonStandingsTests(unittest.TestCase):
    def setUp(self):
        self.league = {"slug": "ger.1", "name": "German Bundesliga", "country": "Germany"}
        self.payload = {
            "id": "720",
            "name": "German Bundesliga",
            "abbreviation": "Bundesliga",
            "season": 2026,
            "children": [{
                "id": "1",
                "name": "2026-27 German Bundesliga",
                "abbreviation": "2026-27 German Bundesliga",
                "standings": {
                    "season": 2026,
                    "entries": [{"team": {"id": "132", "name": "Bayern Munich"}}],
                },
            }],
        }

    def test_nested_returned_season_admits_roster_and_preserves_provenance(self):
        payload = self.payload

        class Client:
            def standings(self, league, season=None):
                if league != "ger.1" or season != 2026:
                    raise AssertionError("unexpected standings request")
                return payload

        result = collect_livescore_season_standings(
            Client(), league=self.league, season_year=2026,
            retrieved_at="2026-11-16T12:00:00+00:00",
        )
        self.assertTrue(result["team_evidence_complete"])
        self.assertEqual(result["status"], "collected")
        self.assertEqual(result["teams"][0]["id"], "132")
        self.assertEqual(result["teams"][0]["name"], "Bayern Munich")
        self.assertEqual(result["provider_payload"], self.payload)
        self.assertEqual(result["source_endpoint"], "/get/soccer/ger.1/standings")
        self.assertEqual(result["source_retrieved_at"], "2026-11-16T12:00:00+00:00")
        self.assertEqual(result["provider_returned_season"]["standings_season"], 2026)

    def test_missing_or_mismatched_returned_season_is_held(self):
        cases = []
        missing_top = dict(self.payload)
        missing_top.pop("season")
        cases.append(missing_top)
        wrong_top = {**self.payload, "season": 2025}
        cases.append(wrong_top)
        wrong_child_year = {
            **self.payload,
            "children": [{
                **self.payload["children"][0],
                "name": "2025-26 German Bundesliga",
                "standings": {"season": 2025, "entries": self.payload["children"][0]["standings"]["entries"]},
            }],
        }
        cases.append(wrong_child_year)
        wrong_child_label = {
            **self.payload,
            "children": [{
                **self.payload["children"][0],
                "name": "German Bundesliga",
                "abbreviation": "German Bundesliga",
                "standings": self.payload["children"][0]["standings"],
            }],
        }
        cases.append(wrong_child_label)

        for payload in cases:
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
            **self.payload,
            "children": [{
                **self.payload["children"][0],
                "standings": {
                    "season": 2026,
                    "entries": [
                        {"team": {"id": "132", "name": "Bayern Munich"}},
                        {"team": {"id": "132", "name": "Different FC"}},
                    ],
                },
            }],
        }

        class Client:
            def standings(self, league, season=None):
                return payload

        result = collect_livescore_season_standings(
            Client(), league=self.league, season_year=2026, retrieved_at="now",
        )
        self.assertFalse(result["team_evidence_complete"])
        self.assertEqual(result["teams"], [])
        self.assertTrue(result["duplicate_team_ids"])

    def test_multiple_matching_season_children_are_held_as_ambiguous(self):
        payload = {
            **self.payload,
            "children": self.payload["children"] * 2,
        }

        class Client:
            def standings(self, league, season=None):
                return payload

        result = collect_livescore_season_standings(
            Client(), league=self.league, season_year=2026, retrieved_at="now",
        )
        self.assertFalse(result["team_evidence_complete"])
        self.assertEqual(result["status"], "held_ambiguous_returned_season")

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
