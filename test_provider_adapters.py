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

    def test_api_ninjas_connection_test_uses_supported_date_alias(self):
        client = APINinjasClient(api_key="test-only")
        response = Mock()
        response.status_code = 200
        response.json.return_value = []
        response.raise_for_status.return_value = None
        client.session.get = Mock(return_value=response)
        self.assertTrue(client.test_connection())
        client.close()

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

    def test_highlightly_unwraps_paginated_data(self):
        self.assertEqual(
            HighlightlyClient._rows({"data": [{"id": 1}], "pagination": {}, "plan": {}}),
            [{"id": 1}],
        )

    def test_highlightly_preserves_plain_array_responses(self):
        self.assertEqual(HighlightlyClient._rows([{"id": 1}]), [{"id": 1}])


if __name__ == "__main__":
    unittest.main()
