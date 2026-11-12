import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from free_fixture_adapters import FreeFixtureProviderError
from football_data_org_adapter import FootballDataOrgAdapter


NOW = datetime.now(timezone.utc)


class FootballDataOrgAdapterTests(unittest.TestCase):
    def make_payload(self, status="TIMED"):
        kickoff = (NOW + timedelta(days=2)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return {
            "matches": [{
                "id": 987654,
                "utcDate": kickoff,
                "status": status,
                "competition": {
                    "id": 2021, "name": "Premier League", "code": "PL",
                    "area": {"id": 2072, "name": "England", "code": "ENG"},
                },
                "season": {
                    "id": 2283, "startDate": "2026-08-01",
                    "endDate": "2027-05-31", "currentMatchday": 12,
                },
                "homeTeam": {"id": 57, "name": "Arsenal FC", "shortName": "Arsenal", "tla": "ARS"},
                "awayTeam": {"id": 61, "name": "Chelsea FC", "shortName": "Chelsea", "tla": "CHE"},
            }],
            "resultSet": {"count": 1},
        }

    def test_token_is_required_and_never_in_error_text(self):
        with self.assertRaisesRegex(FreeFixtureProviderError, "FOOTBALL_DATA_ORG_API_TOKEN"):
            FootballDataOrgAdapter(token="")
        client = FootballDataOrgAdapter(token="secret-token")
        client.close()

    def test_matches_normalizes_ids_names_and_utc_kickoff(self):
        client = FootballDataOrgAdapter(token="test-token")
        client._get_json = Mock(return_value=self.make_payload())
        rows = client.matches("2026-11-12", "2026-11-20", competitions=["PL"])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertTrue(row["eligible_for_review"])
        self.assertEqual(row["provider"], "football_data_org")
        self.assertEqual(row["provider_fixture_id"], "987654")
        self.assertEqual(row["competition_key"], "2021")
        self.assertEqual(row["competition_name"], "Premier League")
        self.assertEqual(row["season_key"], "2283")
        self.assertEqual(row["home_team_key"], "57")
        self.assertEqual(row["away_team_key"], "61")
        self.assertEqual(row["home_team_name"], "Arsenal FC")
        self.assertEqual(row["away_team_name"], "Chelsea FC")
        self.assertTrue(row["kickoff_utc"].endswith("Z"))
        self.assertEqual(row["status"], "scheduled")
        self.assertEqual(row["raw_payload"]["status"], "TIMED")
        self.assertEqual(row["raw_payload"]["competition"]["area"]["name"], "England")
        params = client._get_json.call_args.args[1]
        self.assertEqual(params["competitions"], "PL")
        self.assertNotIn("status", params)
        client.close()

    def test_non_scheduled_status_is_excluded(self):
        client = FootballDataOrgAdapter(token="test-token")
        client._get_json = Mock(return_value=self.make_payload(status="POSTPONED"))
        row = client.matches("2026-11-12", "2026-11-20")[0]
        self.assertFalse(row["eligible_for_review"])
        self.assertEqual(row["exclusion_reason"], "not_scheduled")
        client.close()

    def test_invalid_date_ranges_fail_closed(self):
        client = FootballDataOrgAdapter(token="test-token")
        with self.assertRaisesRegex(ValueError, "valid YYYY-MM-DD"):
            client.matches("2026-13-01", "2026-11-20")
        with self.assertRaisesRegex(ValueError, "31 calendar days"):
            client.matches("2026-01-01", "2026-02-02")
        with self.assertRaisesRegex(ValueError, "not be earlier"):
            client.matches("2026-11-20", "2026-11-12")
        client.close()

    def test_pagination_is_bounded_and_stops_on_short_page(self):
        client = FootballDataOrgAdapter(token="test-token")
        client._get_json = Mock(return_value=self.make_payload())
        client.matches("2026-11-12", "2026-11-20", max_pages=3, page_size=10)
        self.assertEqual(client._get_json.call_count, 1)
        self.assertEqual(client._get_json.call_args.args[1]["page"], 1)
        client.close()

    def test_competition_catalogue_requires_expected_shape(self):
        client = FootballDataOrgAdapter(token="test-token")
        client._get_json = Mock(return_value={"competitions": [
            {"id": 2021, "name": "Premier League", "code": "PL"}
        ]})
        self.assertEqual(client.competitions()[0]["code"], "PL")
        client._get_json = Mock(return_value={"items": []})
        with self.assertRaisesRegex(FreeFixtureProviderError, "competitions array"):
            client.competitions()
        client.close()


if __name__ == "__main__":
    unittest.main()
