import unittest
from openscores_connection_check import run_check


class FakeClient:
    def __init__(self, error=None):
        self.error = error
        self.calls = []
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): return False
    def list_leagues(self):
        self.calls.append("leagues")
        if self.error: raise self.error
        return {"data": {"items": [{"id": 10, "name": "Premier League"}]}}
    @staticmethod
    def _league_collection(data):
        rows = data.get("items") if isinstance(data, dict) else None
        return rows, "items" if rows is not None else None
    def list_seasons(self, league_id):
        self.calls.append(("seasons", league_id))
        return {"data": {"seasons": [{"id": 2026, "name": "2025/26"}]}}
    def list_fixtures(self, **filters):
        self.calls.append(("fixtures", filters))
        return {"data": {"items": [{"id": 55, "starting_at": "2026-11-12T19:00:00Z",
                                  "participants": [{"id": 1, "name": "A"},
                                                   {"id": 2, "name": "B"}]}]}}


class OpenScoresAutonomousCheckTests(unittest.TestCase):
    def test_success_probes_leagues_seasons_and_fixture_shape_read_only(self):
        client = FakeClient()
        report = run_check(lambda: client)
        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["authenticated"])
        self.assertEqual(report["league_count_returned"], 1)
        self.assertEqual(report["season_count_sampled"], 1)
        self.assertEqual(report["fixture_count_sampled"], 1)
        self.assertEqual(report["requests_attempted"], 3)
        self.assertIn("participants", report["fixture_response_shape"]["first_record_keys"])
        self.assertTrue(report["read_only"])
        self.assertFalse(report["prediction_ledger_touched"])
        self.assertFalse(report["fixtures_imported"])

    def test_failure_reports_only_exception_type_not_message(self):
        report = run_check(lambda: FakeClient(RuntimeError("secret-bearing provider detail")))
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["error_type"], "RuntimeError")
        self.assertNotIn("secret-bearing", str(report))


if __name__ == "__main__":
    unittest.main()
