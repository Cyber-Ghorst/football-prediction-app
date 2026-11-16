import unittest
from unittest.mock import Mock

from provider_roster_collection import (
    collect_highlightly_season_roster,
    collect_highlightly_season_match_participants,
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

    def test_team_record_preserves_explicit_gender_and_type(self):
        from provider_roster_collection import _team_record
        record = _team_record({
            "id": 10, "name": "Team A", "type": "domestic",
            "gender": "male", "country": "Germany",
        })
        self.assertEqual(record["type"], "domestic")
        self.assertEqual(record["gender"], "male")
        self.assertEqual(record["raw"]["gender"], "male")

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
            "date": "2026-11-01T15:00:00Z",
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
        client.fixtures.assert_called_once_with("fra.1", status="all")
        self.assertEqual(result["season_window_fixtures"], 1)
        self.assertEqual([x["id"] for x in result["teams"]], ["club.1", "club.2"])
        self.assertFalse(result["team_evidence_complete"])
        self.assertEqual(result["fixtures_imported"], 0)

    def test_livescore_requires_explicit_season_dates(self):
        with self.assertRaises(ValueError):
            collect_livescore_season_participants(
                Mock(), league={"slug": "fra.1", "name": "Ligue 1", "country": "France"},
                season={"year": 2026}, date_from="", date_to="2027-05-31",
            )


    def test_highlightly_match_participant_fallback_paginates_and_deduplicates(self):
        client = Mock()
        client.last_metadata = {"pagination": {"total_count": 2}}
        client.matches.return_value = [
            {"homeTeam": {"id": 1, "name": "Team A"},
             "awayTeam": {"id": 2, "name": "Team B"}},
            {"homeTeam": {"id": 2, "name": "Team B"},
             "awayTeam": {"id": 3, "name": "Team C"}},
        ]
        result = collect_highlightly_season_match_participants(
            client,
            league={"id": 1635, "name": "World Cup",
                    "country": {"name": "World"}},
            season={"season": 2026},
        )
        client.matches.assert_called_once_with(
            leagueId=1635, season=2026, limit=100, offset=0,
        )
        self.assertEqual([row["id"] for row in result["teams"]], [1, 2, 3])
        self.assertEqual(result["matches_examined"], 2)
        self.assertTrue(result["pagination_complete"])
        self.assertTrue(result["team_evidence_complete"])
        self.assertEqual(result["fixtures_imported"], 0)

    def test_highlightly_match_participant_fallback_requires_season(self):
        with self.assertRaises(ValueError):
            collect_highlightly_season_match_participants(
                Mock(), league={"id": 1635}, season={},
            )
if __name__ == "__main__":
    unittest.main()
