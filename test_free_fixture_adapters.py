import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from free_fixture_adapters import (
    BzzoiroAdapter,
    OpenFootballAdapter,
    OpenLigaDBAdapter,
    OpenMatchdayAdapter,
    eligible_observations,
)


NOW = datetime.now(timezone.utc)


class Response:
    def __init__(self, payload=None, text=None):
        self._payload = payload
        self.text = text or ""
    def raise_for_status(self):
        return None
    def json(self):
        return self._payload


class FreeFixtureAdapterTests(unittest.TestCase):
    def test_openligadb_maps_documented_utc_match_fields(self):
        row = {
            "matchID": 42,
            "matchDateTimeUTC": (NOW + timedelta(days=1)).replace(tzinfo=None).isoformat(),
            "leagueName": "Bundesliga",
            "leagueSeason": 2026,
            "matchStatus": "scheduled",
            "team1": {"teamId": 1, "teamName": "Home FC"},
            "team2": {"teamId": 2, "teamName": "Away FC"},
        }
        client = OpenLigaDBAdapter()
        client._get_json = Mock(return_value=[row])
        result = client.matches("bl1", 2026)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["eligible_for_review"])
        self.assertEqual(result[0]["provider_fixture_id"], "42")
        self.assertEqual(result[0]["home_team_key"], "1")
        self.assertTrue(result[0]["kickoff_utc"].endswith("Z"))
        self.assertIn("/getmatchdata/bl1/2026", client._get_json.call_args.args[0])
        client.close()

    def test_openfootball_accepts_explicit_timezone_and_rejects_naive_time(self):
        good = {
            "date": (NOW + timedelta(days=2)).date().isoformat(),
            "time": "18:30:00+00:00",
            "team1": "Home FC", "team2": "Away FC",
        }
        bad = {
            "date": (NOW + timedelta(days=2)).date().isoformat(),
            "time": "18:30:00",
            "team1": "Other Home", "team2": "Other Away",
        }
        client = OpenFootballAdapter()
        client._get_json = Mock(return_value={"matches": [good, bad]})
        rows = client.season("eng.1.json", "Premier League")
        self.assertTrue(rows[0]["eligible_for_review"])
        self.assertEqual(rows[1]["exclusion_reason"], "kickoff_missing_timezone_or_precision")
        self.assertTrue(rows[0]["provider_fixture_id"].startswith("openfootball:dataset:"))
        client.close()

    def test_openfootball_date_only_is_never_prediction_ready(self):
        client = OpenFootballAdapter()
        client._get_json = Mock(return_value={"matches": [{
            "date": (NOW + timedelta(days=2)).date().isoformat(),
            "team1": "Home FC", "team2": "Away FC",
        }]})
        row = client.season("eng.1.json", "Premier League")[0]
        self.assertFalse(row["eligible_for_review"])
        self.assertIsNone(row["kickoff_utc"])
        client.close()

    def test_openmatchday_fixed_offset_time_is_not_guessed(self):
        client = OpenMatchdayAdapter()
        client._get_text = Mock(return_value=(
            "date,time,home_team,away_team,competition,season\n"
            f"{(NOW + timedelta(days=2)).date().isoformat()},19:00,Home FC,Away FC,League,2026\n"
        ))
        row = client.season_csv(
            "https://raw.githubusercontent.com/oladeeayo/open-matchday/main/fixtures_2026.csv",
            competition="League", season="2026",
        )[0]
        self.assertFalse(row["eligible_for_review"])
        self.assertEqual(row["exclusion_reason"], "kickoff_missing_timezone_or_precision")
        self.assertIn("non-commercial-only", row["licence"])
        client.close()

    def test_bzzoiro_requires_token_and_explicit_endpoint(self):
        with self.assertRaisesRegex(Exception, "BZZOIRO_API_TOKEN"):
            BzzoiroAdapter(token=None, endpoint="https://example.test/fixtures")
        with self.assertRaisesRegex(Exception, "documented BSD API host"):
            BzzoiroAdapter(token="test-token", endpoint="https://example.test/events/")

    def test_bzzoiro_parses_utc_upcoming_payload_without_exposing_token(self):
        client = BzzoiroAdapter(token="secret")
        client._get_json = Mock(return_value={"results": [{
            "id": 99,
            "league_id": 10,
            "season_id": 2026,
            "home_team": {"id": 1, "name": "Home FC"},
            "away_team": {"id": 2, "name": "Away FC"},
            "event_date": (NOW + timedelta(days=1)).isoformat(),
            "status": "upcoming",
        }]})
        row = client.upcoming()[0]
        self.assertTrue(row["eligible_for_review"])
        self.assertEqual(row["provider_fixture_id"], "99")
        self.assertNotIn("secret", str(row))
        self.assertEqual(client._get_json.call_args.kwargs["headers"]["Authorization"], "Token secret")
        self.assertEqual(client._get_json.call_args.args[0], BzzoiroAdapter.BASE_URL)
        self.assertEqual(client._get_json.call_args.kwargs["params"]["status"], "upcoming")
        client.close()

    def test_only_explicitly_eligible_observations_are_selected(self):
        rows = [
            {"eligible_for_review": True, "provider_fixture_id": "a"},
            {"eligible_for_review": False, "provider_fixture_id": "b"},
        ]
        self.assertEqual(eligible_observations(rows), [rows[0]])


if __name__ == "__main__":
    unittest.main()
