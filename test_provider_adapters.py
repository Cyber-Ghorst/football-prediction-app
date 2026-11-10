import unittest
from unittest.mock import Mock

from api_football import APIFootballClient, APIFootballError
from api_ninjas import APINinjasClient
from highlightly import HighlightlyClient, HighlightlyError
from sportmonks import SportmonksClient, SportmonksError


class ProviderAdapterTests(unittest.TestCase):
    def test_api_football_unwraps_v3_response_envelope(self):
        client = APIFootballClient(api_key="test-only")
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"errors": [], "response": [{"fixture": {"id": 123}}]}
        response.headers = {}
        response.raise_for_status.return_value = None
        client.session.get = Mock(return_value=response)
        self.assertEqual(client.last_fixtures(10, 2026), [{"fixture": {"id": 123}}])
        self.assertEqual(client.session.headers["x-apisports-key"], "test-only")
        client.close()

    def test_api_football_does_not_expose_authentication_material(self):
        client = APIFootballClient(api_key="secret-do-not-print")
        response = Mock()
        response.status_code = 401
        response.raise_for_status.return_value = None
        client.session.get = Mock(return_value=response)
        with self.assertRaises(APIFootballError) as raised:
            client.leagues(2026)
        self.assertNotIn("secret-do-not-print", str(raised.exception))
        client.close()

    def test_api_ninjas_connection_test_exposes_safe_quota_headers(self):
        client = APINinjasClient(api_key="test-only")
        response = Mock()
        response.status_code = 200
        response.json.return_value = []
        response.headers = {"X-RateLimit-Limit": "1000", "X-RateLimit-Remaining": "975"}
        response.raise_for_status.return_value = None
        client.session.get = Mock(return_value=response)
        self.assertTrue(client.test_connection())
        self.assertEqual(client.last_metadata["requests_remaining"], "975")
        self.assertEqual(client.last_metadata["requests_limit"], "1000")
        self.assertNotIn("test-only", str(client.last_metadata))
        self.assertEqual(client.session.headers["X-Api-Key"], "test-only")
        client.close()

    def test_api_ninjas_includes_danish_superliga_catalogue_slug(self):
        self.assertEqual(len(APINinjasClient.LEAGUES), 74)
        self.assertEqual(
            len({row["id"] for row in APINinjasClient.LEAGUES}), 74
        )
        self.assertIn(
            {"id": "danishsuperliga", "name": "Danish Superliga"},
            APINinjasClient.LEAGUES,
        )

    def test_api_ninjas_upcoming_matches_accepts_date_object(self):
        from datetime import date
        client = APINinjasClient(api_key="test-only")
        client.matches = Mock(return_value=[])
        self.assertEqual(
            client.upcoming_matches(date_from=date(2026, 11, 7), days=1),
            [],
        )
        client.matches.assert_called_once()
        client.close()

    def test_highlightly_connection_test_reports_safe_metadata(self):
        client = HighlightlyClient(api_key="test-only")
        client.leagues = Mock(return_value=[{"id": 1}])
        client.last_metadata = {"http_status": 200, "requests_remaining": "10"}
        result = client.test_connection()
        self.assertEqual(result["transport_status"], "responding")
        self.assertEqual(result["records_returned"], 1)
        self.assertNotIn("test-only", str(result))
        client.close()

    def test_sportmonks_connection_test_reports_safe_metadata(self):
        client = SportmonksClient(api_token="test-only")
        client.leagues = Mock(return_value=[{"id": 8}])
        client.last_metadata = {"http_status": 200, "rate_remaining": "100"}
        result = client.test_connection()
        self.assertEqual(result["transport_status"], "responding")
        self.assertEqual(result["records_returned"], 1)
        self.assertFalse(result["fallback_enabled"])
        self.assertNotIn("test-only", str(result))
        client.close()

    def test_sportmonks_unwraps_data_envelope(self):
        self.assertEqual(SportmonksClient._rows({"data": [{"id": 42}]}), [{"id": 42}])

    def test_sportmonks_flattens_schedule_stages_rounds_and_fixtures(self):
        payload = {
            "data": [{
                "id": 10,
                "rounds": [{
                    "id": 20,
                    "fixtures": [
                        {"id": 100, "starting_at": "2026-08-01 12:00:00"},
                        {"id": 101, "starting_at": "2026-08-02 12:00:00"},
                    ],
                }],
            }],
        }
        fixtures = SportmonksClient._flatten_schedule_fixtures(payload)
        self.assertEqual([row["id"] for row in fixtures], [100, 101])
        self.assertEqual(fixtures[0]["stage_id"], 10)
        self.assertEqual(fixtures[0]["round_id"], 20)

    def test_sportmonks_schedule_duplicate_ids_are_reported(self):
        payload = {"data": [{
            "id": 10,
            "rounds": [{"id": 20, "fixtures": [
                {"id": 100, "starting_at": "2026-08-01 12:00:00"},
                {"id": 100, "starting_at": "2026-08-01 12:00:00"},
                {"id": 101, "starting_at": "2026-08-02 12:00:00"},
            ]}],
        }]}
        fixtures = SportmonksClient._flatten_schedule_fixtures(payload)
        self.assertEqual([row["id"] for row in fixtures], [100, 101])
        self.assertEqual(fixtures[0]["_schedule_duplicate_fixture_ids"], [100])
        self.assertTrue(fixtures[0]["_schedule_duplicate"])
        self.assertFalse(fixtures[1]["_schedule_duplicate"])
        self.assertEqual(fixtures[1]["_schedule_unique_fixture_count"], 2)

    def test_sportmonks_completed_state_accepts_label_without_state_id(self):
        self.assertTrue(SportmonksClient._fixture_is_completed({
            "state": {"short_name": "FT", "name": "Finished"}
        }))
        self.assertTrue(SportmonksClient._fixture_is_completed({"status": "After Extra Time"}))
        self.assertFalse(SportmonksClient._fixture_is_completed({
            "state": {"short_name": "NS", "name": "Not Started"}
        }))
        self.assertTrue(SportmonksClient._fixture_is_completed({
            "state": {"short_name": "FT_PEN", "name": "Full-Time After Penalties"}
        }))
        self.assertFalse(SportmonksClient._fixture_is_completed({
            "state": {"short_name": "PEN", "name": "Penalty Shootout"}
        }))
        self.assertFalse(SportmonksClient._fixture_is_completed({"status": "Penalties"}))

    def test_sportmonks_kickoff_sorting_parses_utc_offsets_and_milliseconds(self):
        older = SportmonksClient._fixture_kickoff_timestamp({
            "starting_at": "2026-10-01T20:00:00+03:00"
        })
        newer = SportmonksClient._fixture_kickoff_timestamp({
            "starting_at": "2026-10-01T18:30:00Z"
        })
        milliseconds = SportmonksClient._fixture_kickoff_timestamp({
            "starting_at_timestamp": 1795282200000
        })
        self.assertLess(older, newer)
        self.assertEqual(milliseconds, 1795282200)

    def test_sportmonks_schedule_endpoint_and_targeted_statistics_enrichment(self):
        client = SportmonksClient(api_token="test-only")
        schedule = {
            "data": [{
                "id": 10,
                "rounds": [{
                    "id": 20,
                    "fixtures": [{
                        "id": 100,
                        "state_id": 5,
                        "starting_at": "2026-08-01 12:00:00",
                        "participants": [{"id": 1}, {"id": 2}],
                        "scores": [],
                    }],
                }],
            }],
        }
        client._get = Mock(side_effect=[
            schedule,
            {"data": [{"id": 100, "statistics": [{"type": {"name": "Shots"}, "data": {"value": 8}}]}]},
        ])
        fixtures = client.fixtures_by_season(123, team_ids=[1, 2])
        self.assertEqual(fixtures[0]["season_id"], 123)
        self.assertTrue(fixtures[0]["collection_fetched_at"])
        self.assertEqual(fixtures[0]["statistics"][0]["data"]["value"], 8)
        self.assertEqual(client._get.call_args_list[0].args[0], "schedules/seasons/123")
        self.assertEqual(client._get.call_args_list[0].args, ("schedules/seasons/123",))
        self.assertEqual(client._get.call_args_list[1].args[0], "fixtures/multi/100")
        self.assertEqual(
            client._get.call_args_list[1].args[1]["include"],
            "participants;scores;state;league;season;statistics.type",
        )
        client.close()

    def test_sportmonks_schedule_enriches_labelled_finished_fixtures_without_state_id(self):
        client = SportmonksClient(api_token="test-only")
        schedule = {"data": [{
            "id": 10,
            "rounds": [{"id": 20, "fixtures": [{
                "id": 101,
                "state": {"short_name": "FT", "name": "Finished"},
                "starting_at": "2026-08-01 12:00:00",
                "participants": [{"id": 1}, {"id": 2}],
                "scores": [],
            }]}],
        }]}
        client._get = Mock(side_effect=[
            schedule,
            {"data": [{"id": 101, "scores": [
                {"participant_id": 1, "score": {"goals": 1}}
            ]}]},
        ])
        fixtures = client.fixtures_by_season(123, team_ids=[1, 2])
        self.assertEqual(client._get.call_count, 2)
        self.assertEqual(fixtures[0]["season_id"], 123)
        self.assertEqual(fixtures[0]["scores"][0]["score"]["goals"], 1)
        client.close()

    def test_sportmonks_schedule_skips_statistics_when_disabled(self):
        client = SportmonksClient(api_token="test-only")
        client._get = Mock(return_value={"data": []})
        self.assertEqual(client.fixtures_by_season(123, include_statistics=False), [])
        client._get.assert_called_once_with("schedules/seasons/123")
        client.close()

    def test_sportmonks_paginates_complete_season_collections(self):
        client = SportmonksClient(api_token="test-only")
        client._get = Mock(side_effect=[
            {"data": [{"id": 1}], "pagination": {"has_more": True}},
            {"data": [{"id": 2}], "pagination": {"has_more": False}},
        ])
        self.assertEqual(client.available_seasons(), [{"id": 1}, {"id": 2}])
        self.assertEqual(client._get.call_count, 2)
        client.close()

    def test_sportmonks_rejects_incomplete_page_without_pagination_metadata(self):
        client = SportmonksClient(api_token="test-only")
        client._get = Mock(return_value={
            "data": [{"id": i} for i in range(50)]
        })
        with self.assertRaises(SportmonksError):
            client.available_seasons()
        client.close()

    def test_sportmonks_auth_error_does_not_expose_token(self):
        client = SportmonksClient(api_token="secret-token")
        response = Mock()
        response.status_code = 403
        response.headers = {}
        response.raise_for_status.return_value = None
        client.session.get = Mock(return_value=response)
        with self.assertRaises(SportmonksError) as raised:
            client.leagues()
        self.assertNotIn("secret-token", str(raised.exception))
        client.close()

    def test_highlightly_matches_reports_data_envelope_metadata(self):
        client = HighlightlyClient(api_key="test-only")
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"data": [{"id": 1}], "pagination": {"hasMore": False}}
        response.headers = {"x-ratelimit-requests-remaining": "9"}
        response.raise_for_status.return_value = None
        client.session.get = Mock(return_value=response)
        self.assertEqual(client.matches(limit=1), [{"id": 1}])
        self.assertEqual(client.last_metadata["rows_envelope"], "data_list")
        self.assertEqual(client.last_metadata["extracted_rows_count"], 1)
        self.assertEqual(client.last_metadata["response_top_level_keys"], ["data", "pagination"])
        self.assertEqual(client.last_metadata["requests_remaining"], "9")
        self.assertNotIn("test-only", str(client.last_metadata))
        client.close()

    def test_highlightly_matches_reports_unrecognized_response_envelope(self):
        client = HighlightlyClient(api_key="test-only")
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"data": {"matches": [{"id": 1}]}}
        response.headers = {}
        response.raise_for_status.return_value = None
        client.session.get = Mock(return_value=response)
        self.assertEqual(client.matches(limit=1), [])
        self.assertEqual(client.last_metadata["rows_envelope"], "unrecognized")
        self.assertEqual(client.last_metadata["response_data_type"], "dict")
        self.assertEqual(client.last_metadata["extracted_rows_count"], 0)
        client.close()

    def test_highlightly_matches_reports_top_level_array_envelope(self):
        client = HighlightlyClient(api_key="test-only")
        response = Mock()
        response.status_code = 200
        response.json.return_value = [{"id": 1}]
        response.headers = {}
        response.raise_for_status.return_value = None
        client.session.get = Mock(return_value=response)
        self.assertEqual(client.matches(limit=1), [{"id": 1}])
        self.assertEqual(client.last_metadata["rows_envelope"], "top_level_list")
        self.assertEqual(client.last_metadata["extracted_rows_count"], 1)
        client.close()

    def test_highlightly_unwraps_paginated_data(self):
        self.assertEqual(
            HighlightlyClient._rows({"data": [{"id": 1}], "pagination": {}, "plan": {}}),
            [{"id": 1}],
        )

    def test_highlightly_preserves_plain_array_responses(self):
        self.assertEqual(HighlightlyClient._rows([{"id": 1}]), [{"id": 1}])

    def test_highlightly_player_and_team_statistics_use_documented_paths(self):
        client = HighlightlyClient(api_key="test-only")
        response = Mock()
        response.status_code = 200
        response.json.return_value = [{"id": 7}]
        response.headers = {}
        response.raise_for_status.return_value = None
        client.session.get = Mock(return_value=response)
        self.assertEqual(client.player_statistics(7), [{"id": 7}])
        self.assertEqual(client.session.get.call_args_list[-1].args[0],
                         "https://soccer.highlightly.net/players/7/statistics")
        self.assertEqual(client.team_statistics(11, fromDate="2026-01-01"),
                         [{"id": 7}])
        self.assertEqual(client.session.get.call_args_list[-1].args[0],
                         "https://soccer.highlightly.net/teams/statistics/11")
        self.assertEqual(client.session.get.call_args_list[-1].kwargs["params"],
                         {"fromDate": "2026-01-01"})
        client.close()

    def test_highlightly_matches_exposes_pagination_metadata(self):
        client = HighlightlyClient(api_key="test-only")
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "data": [{"id": 123}],
            "pagination": {"totalCount": 251, "offset": 100, "limit": 100},
            "plan": {"tier": "BASIC", "message": "test"},
        }
        response.headers = {}
        response.raise_for_status.return_value = None
        client.session.get = Mock(return_value=response)
        self.assertEqual(client.matches(leagueName="Premier League", offset=100), [{"id": 123}])
        self.assertEqual(
            client.last_metadata["pagination"],
            {"total_count": 251, "offset": 100, "limit": 100},
        )
        client.close()


if __name__ == "__main__":
    unittest.main()
