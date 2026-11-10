import unittest
from openscores_connection_check import run_check


class FakeClient:
    def __init__(self, result=None, error=None):
        self.result = result or {}
        self.error = error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def test_connection(self):
        if self.error:
            raise self.error
        return self.result


class OpenScoresAutonomousCheckTests(unittest.TestCase):
    def test_success_reports_response_shape_and_league_count(self):
        client = FakeClient({
            "status": "connected",
            "league_count_returned": 6,
            "league_collection_found": True,
            "league_collection_path": "items",
            "response_shape": {"root_type": "dict", "root_keys": ["items"]},
            "retrieved_at_utc": "2026-11-10T12:00:00+00:00",
        })
        report = run_check(lambda: client)
        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["authenticated"])
        self.assertEqual(report["league_count_returned"], 6)
        self.assertTrue(report["league_collection_found"])
        self.assertEqual(report["league_collection_path"], "items")
        self.assertEqual(report["response_shape"]["root_type"], "dict")
        self.assertTrue(report["read_only"])
        self.assertFalse(report["prediction_ledger_touched"])
        self.assertFalse(report["fixtures_imported"])

    def test_failure_reports_only_exception_type_not_message(self):
        client = FakeClient(error=RuntimeError("secret-bearing provider detail"))
        report = run_check(lambda: client)
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["error_type"], "RuntimeError")
        self.assertNotIn("secret-bearing", str(report))


if __name__ == "__main__":
    unittest.main()
