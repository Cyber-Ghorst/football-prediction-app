import unittest
from unittest.mock import Mock

from provider_roster_collection import (
    collect_highlightly_season_roster,
    collect_livescore_season_participants,
)


class ProviderRosterCollectionTests(unittest.TestCase):
    def test_highlightly_collects_only_standings_team_ids(self):
        client = Mock()
        client._get.return_value = {
            "groups": [{
                "name": "League",
                "standings": [
                    {"position": 1, "team": {"id": 10, "name": "Team A"}},
                    {"position": 2, "team": {"id": 20, "name": "Team B"}},
                    {"position": 3, "team": {"name": "No ID"}},
                ],
            }],
        }
        result = collect_highlightly_season_roster(
            client,
            league={"id": 52695, "name": "Ligue 1",
                    "country": {"code": "FR", "name": "France"}},
            season={"season": 2026},
        )
        client._get.assert_called_once_with(
            "standings", {"leagueId": 52695, "season": 2026}
        )
        self.assertEqual([x["id"] for x in result["teams"]], [10, 20])
        self.assertTrue(result["team_evidence_complete"])
        self.assertEqual(result["fixtures_imported"], 0)

    def test_highlightly_rejects_missing_country(self):
        with self.assertRaises(ValueError):
            collect_highlightly_season_roster(
                Mock(), league={"id": 1, "name": "League", "country": None},
                season={"season": 2026},
            )

    def test_livescore_collects_fixture_participants_as_incomplete_evidence(self):
        client = Mock()
        client.fixtures.return_value = [{
            "id": "fixture-1",
            "competitions": [{
                "competitors": [
                    {"id": "club.1", "team": {"id": "club.1", "name": "Home FC"},
                     "homeAway": "home"},
                    {"id": "club.2", "team": {"id": "club.2", "name": "Away FC"},
                     "homeAway": "away"},
                ],
            }],
        }]
        result = collect_livescore_season_participants(
            client,
            league={"slug": "fra.1", "name": "Ligue 1", "country": "France"},
            season={"year": 2026},
            date_from="2026-08-01",
            date_to="2027-05-31",
        )
        client.fixtures.assert_called_once_with(
            "fra.1", status="all", date_from="2026-08-01", date_to="2027-05-31"
        )
        self.assertEqual([x["id"] for x in result["teams"]], ["club.1", "club.2"])
        self.assertFalse(result["team_evidence_complete"])
        self.assertEqual(result["fixtures_imported"], 0)

    def test_livescore_requires_explicit_season_dates(self):
        with self.assertRaises(ValueError):
            collect_livescore_season_participants(
                Mock(), league={"slug": "fra.1", "name": "Ligue 1", "country": "France"},
                season={"year": 2026}, date_from="", date_to="2027-05-31",
            )


if __name__ == "__main__":
    unittest.main()
