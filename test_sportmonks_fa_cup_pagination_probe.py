import unittest

from sportmonks_fa_cup_pagination_probe import (
    inspect_response,
    inspect_season_include,
    run_probe,
)


class FakeClient:
    def __init__(self):
        self.responses = [
            {"data": [{"id": i} for i in range(25)], "pagination": {"per_page": 25, "current_page": 1, "has_more": True}},
            {"data": [{"id": i} for i in range(25, 40)], "pagination": {"per_page": 25, "current_page": 2, "has_more": False}},
            {"data": [{"id": i} for i in range(50)], "pagination": {"per_page": 50, "current_page": 1, "has_more": True}},
            {"data": [{"id": i} for i in range(50)], "pagination": {"per_page": 50, "current_page": 2, "has_more": True}},
            {"data": [{"id": i} for i in range(50)], "pagination": {}},
            {"data": [{"id": i} for i in reversed(range(50))], "pagination": {}},
            {"data": {"id": 28020, "league_id": 24, "teams": [{"id": i} for i in range(699)]}},
        ]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def _get(self, _path, _params):
        return self.responses.pop(0)


class PaginationProbeTests(unittest.TestCase):
    def test_inspect_response_keeps_only_ids_and_safe_pagination_fields(self):
        result = inspect_response({
            "data": [{"id": 1, "name": "Example Club"}],
            "pagination": {"current_page": 1, "has_more": False, "secret": "never"},
            "meta": {"irrelevant": True},
        })
        self.assertEqual(result["team_ids"], ["1"])
        self.assertEqual(result["pagination"]["current_page"], 1)
        self.assertNotIn("secret", str(result))
        self.assertNotIn("Example Club", str(result))

    def test_season_include_records_only_ids_and_counts(self):
        result = inspect_season_include({
            "data": {
                "id": 28020,
                "league_id": 24,
                "teams": [{"id": 1, "name": "Private Team Name"}],
            }
        })
        self.assertEqual(result["season_id_returned"], "28020")
        self.assertEqual(result["league_id_returned"], "24")
        self.assertEqual(result["teams_count"], 1)
        self.assertEqual(result["team_ids"], ["1"])
        self.assertNotIn("Private Team Name", str(result))

    def test_probe_compares_pagination_order_and_season_include_without_database(self):
        report = run_probe(client_factory=FakeClient)
        self.assertTrue(report["success"])
        self.assertTrue(report["read_only"])
        self.assertFalse(report["database_accessed"])
        self.assertEqual(report["requests_made"], 7)
        self.assertTrue(report["comparisons"]["order_asc_desc_same_id_set"])
        self.assertEqual(report["comparisons"]["direct_page_1_count"], 50)
        self.assertEqual(report["comparisons"]["season_include_team_count"], 699)
        self.assertTrue(report["comparisons"]["direct_page_1_vs_season_include_same_id_set"] is False)


if __name__ == "__main__":
    unittest.main()
