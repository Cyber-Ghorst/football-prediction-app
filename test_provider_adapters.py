import unittest
from unittest.mock import Mock

from api_football import APIFootballClient, APIFootballError
from highlightly import HighlightlyClient, HighlightlyError


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

    def test_highlightly_unwraps_paginated_data(self):
        self.assertEqual(
            HighlightlyClient._rows({"data": [{"id": 1}], "pagination": {}, "plan": {}}),
            [{"id": 1}],
        )

    def test_highlightly_preserves_plain_array_responses(self):
        self.assertEqual(HighlightlyClient._rows([{"id": 1}]), [{"id": 1}])


if __name__ == "__main__":
    unittest.main()
