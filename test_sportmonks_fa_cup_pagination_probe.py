import unittest
from unittest.mock import Mock

from sportmonks_fa_cup_pagination_probe import inspect_response, run_probe


class FakeClient:
    def __init__(self):
        self.responses = [
            {"data": [{"id": i} for i in range(25)], "pagination": {"per_page": 25, "current_page": 1, "has_more": True}},
            {"data": [{"id": i} for i in range(25, 40)], "pagination": {"per_page": 25, "current_page": 2, "has_more": False}},
            {"data": [{"id": i} for i in range(50)], "pagination": {"per_page": 50, "current_page": 1, "has_more": True}},
            {"data": [{"id": i} for i in range(50)], "pagination": {"per_page": 50, "current_page": 2, "has_more": True}},
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

    def test_probe_compares_both_page_sizes_without_database_access(self):
        report = run_probe(client_factory=FakeClient)
        self.assertTrue(report["success"])
        self.assertTrue(report["read_only"])
        self.assertFalse(report["database_accessed"])
        self.assertEqual(report["requests_made"], 4)
        by_size = {x["per_page"]: x for x in report["page_comparisons"]}
        self.assertFalse(by_size[50]["same_id_sequence"])
        self.assertEqual(by_size[50]["overlap_count"], 50)
        self.assertEqual(by_size[25]["page_2_count"], 15)


if __name__ == "__main__":
    unittest.main()
