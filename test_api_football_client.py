import unittest
from unittest.mock import Mock

from api_football import APIFootballClient, APIFootballError


class APIFootballSafeErrorTests(unittest.TestCase):
    def test_provider_error_details_are_preserved_without_secrets(self):
        client = APIFootballClient(api_key="private-api-key")
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "errors": {
                "date": "The requested date parameter is not available.",
                "token": "private-api-key",
            },
            "response": [],
        }
        response.raise_for_status.return_value = None
        client.session.get = Mock(return_value=response)

        with self.assertRaises(APIFootballError) as caught:
            client._request("fixtures", {"date": "2026-11-11"})

        message = str(caught.exception)
        self.assertIn("date", message)
        self.assertIn("not available", message)
        self.assertNotIn("private-api-key", message)
        self.assertNotIn("token", message)
        client.close()


if __name__ == "__main__":
    unittest.main()
