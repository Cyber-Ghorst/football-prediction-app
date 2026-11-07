import unittest
from unittest.mock import Mock

from livescore_football import LiveScoreFootballClient, LiveScoreFootballError


class LiveScoreFootballAdapterTests(unittest.TestCase):
    def make_client(self, payload):
        session = Mock()
        response = Mock()
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        session.get.return_value = response
        session.headers = {}
        return LiveScoreFootballClient(
            base_url="https://example.test", session=session
        ), session

    def test_leagues_reads_documented_leagues_envelope(self):
        client, session = self.make_client({"leagues": [{"slug": "eng.1"}]})
        self.assertEqual(client.leagues(), [{"slug": "eng.1"}])
        args, kwargs = session.get.call_args
        self.assertEqual(args[0], "https://example.test/get/soccer/leagues")
        self.assertEqual(kwargs["params"], {"kind": "club", "available": "true"})

    def test_fixtures_reads_documented_events_envelope(self):
        client, _ = self.make_client({
            "events": [{"id": "match-1"}], "pageCount": 1
        })
        self.assertEqual(client.fixtures("eng.1"), [{"id": "match-1"}])

    def test_team_fixtures_filters_competitors_by_source_id(self):
        client, _ = self.make_client({
            "events": [
                {"id": "one", "competitions": [{"competitors": [{"id": "10"}]}]},
                {"id": "two", "competitions": [{"competitors": [{"id": "20"}]}]},
            ],
            "pageCount": 1,
        })
        self.assertEqual(
            [x["id"] for x in client.team_fixtures("eng.1", 10)], ["one"]
        )

    def test_bad_fixtures_envelope_fails_closed(self):
        client, _ = self.make_client({"data": []})
        with self.assertRaises(LiveScoreFootballError):
            client.fixtures("eng.1")


if __name__ == "__main__":
    unittest.main()
