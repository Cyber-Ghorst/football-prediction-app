import unittest
from unittest.mock import Mock, patch

from openscores import OpenScoresClient, OpenScoresError


class FakeResponse:
    def __init__(self, payload=None, status_code=200, headers=None, text=""):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "application/json"}
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(response=Mock(status_code=self.status_code))


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.headers = {}
        self.last_request = None
        self.closed = False

    def post(self, url, **kwargs):
        self.last_request = (url, kwargs)
        return self.response

    def close(self):
        self.closed = True


class OpenScoresClientTests(unittest.TestCase):
    def test_requires_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("streamlit.secrets", {}, create=True):
                with self.assertRaisesRegex(OpenScoresError, "OPENSCORES_API_KEY"):
                    OpenScoresClient()

    def test_calls_documented_mcp_tool_and_keeps_provenance(self):
        response = FakeResponse(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"content": [{"type": "text", "text": '[{"id": 7, "name": "Premier League"}]'}]},
            }
        )
        session = FakeSession(response)
        client = OpenScoresClient(api_key="  osk_live_test  ", session=session)
        result = client.list_leagues()

        self.assertEqual(session.headers["Authorization"], "Bearer osk_live_test")
        self.assertEqual(session.last_request[0], OpenScoresClient.ENDPOINT)
        self.assertFalse(session.last_request[1]["allow_redirects"])
        self.assertEqual(session.last_request[1]["json"]["params"]["name"], "list_leagues")
        self.assertEqual(result["provider"], "openscores")
        self.assertIn("openscores.ai", result["attribution"])
        self.assertEqual(result["data"][0]["name"], "Premier League")
        client.close()
        self.assertTrue(session.closed)

    def test_passes_exact_fixture_id_to_tool(self):
        response = FakeResponse(
            {"jsonrpc": "2.0", "id": 1, "result": {"structuredContent": {"id": 1872}}}
        )
        session = FakeSession(response)
        client = OpenScoresClient(api_key="test", session=session)
        result = client.get_fixture(1872)
        self.assertEqual(session.last_request[1]["json"]["params"], {
            "name": "get_fixture", "arguments": {"fixture_id": 1872}
        })
        self.assertEqual(result["data"]["id"], 1872)

    def test_rejects_authentication_failure_without_leaking_key(self):
        session = FakeSession(FakeResponse(status_code=401))
        client = OpenScoresClient(api_key="secret-key", session=session)
        with self.assertRaisesRegex(OpenScoresError, "authentication/access failed"):
            client.list_leagues()
        self.assertNotIn("secret-key", str(client.last_metadata))
    
    def test_rate_limit_is_reported_without_automatic_retry(self):
        session = FakeSession(FakeResponse(status_code=429, headers={
            "Content-Type": "application/json", "Retry-After": "30"
        }))
        client = OpenScoresClient(api_key="test", session=session)
        with self.assertRaisesRegex(OpenScoresError, "rate limit"):
            client.list_leagues()
        self.assertEqual(client.last_metadata["retry_after"], "30")

    def test_json_rpc_error_is_reported(self):
        session = FakeSession(FakeResponse({
            "jsonrpc": "2.0", "id": 1,
            "error": {"code": -32602, "message": "invalid arguments"}
        }))
        client = OpenScoresClient(api_key="test", session=session)
        with self.assertRaisesRegex(OpenScoresError, "invalid arguments"):
            client.list_leagues()

    def test_connection_reports_returned_league_count(self):
        response = FakeResponse({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"content": [{
                "type": "text",
                "text": '[{"id": 1, "name": "Premier League"}, {"id": 2, "name": "La Liga"}]'
            }]}
        })
        client = OpenScoresClient(api_key="test", session=FakeSession(response))
        status = client.test_connection()
        self.assertEqual(status["status"], "connected")
        self.assertEqual(status["league_count_returned"], 2)
        self.assertEqual(status["provider"], "openscores")
        self.assertIn("retrieved_at_utc", status)

    def test_parses_streamable_http_event_stream(self):
        response = FakeResponse(
            headers={"Content-Type": "text/event-stream"},
            text='event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"structuredContent":{"ok":true}}}\n\n',
        )
        session = FakeSession(response)
        client = OpenScoresClient(api_key="test", session=session)
        self.assertEqual(client.list_leagues()["data"], {"ok": True})


if __name__ == "__main__":
    unittest.main()
