import unittest
from sportmonks_catalogue_access_audit import build_catalogue_report


class FakeSportmonks:
    def __init__(self):
        self.closed = False
    def __enter__(self): return self
    def __exit__(self, *args):
        self.closed = True
    def available_leagues(self, **kwargs):
        return [
            {"id": 82, "name": "Bundesliga", "country": {"name": "Germany"}},
            {"id": 301, "name": "Ligue 1", "country": {"name": "France"}},
            {"id":  international_id(), "name": "World Cup", "country": {"name": "World"}},
        ]
    def _get(self, path, params=None):
        if path == "my/leagues":
            return {"data": self.available_leagues()}
        raise AssertionError("Unexpected endpoint: " + path)
    def _all_pages(self, path, **params):
        query = path.rsplit("/", 1)[-1].casefold()
        return [
            row for row in self.available_leagues()
            if query in str(row.get("name", "")).casefold()
        ]
    def available_seasons(self):
        return [
            {"id": 1001, "league_id": 82, "name": "2025/2026"},
            {"id": 1002, "league_id": 301, "name": "2025/2026"},
        ]


def international_id():
    return 900


class SportmonksCatalogueAuditTests(unittest.TestCase):
    def test_catalogue_audit_is_read_only_and_reports_exact_targets(self):
        report = build_catalogue_report(FakeSportmonks)
        self.assertTrue(report["read_only"])
        self.assertFalse(report["database_touched"])
        self.assertEqual(report["entity_links_written"], 0)
        self.assertEqual(report["league_catalogue_count"], 3)
        self.assertEqual(report["season_catalogue_count"], 2)
        self.assertEqual(
            [target["status"] for target in report["targets"]],
            ["unique_exact_catalogue_match"] * 3,
        )
        self.assertEqual(report["targets"][0]["candidates"][0]["season_count"], 1)

    def test_missing_competition_is_not_fabricated(self):
        class MissingWorldCup(FakeSportmonks):
            def available_leagues(self, **kwargs):
                return super().available_leagues(**kwargs)[:2]
        report = build_catalogue_report(MissingWorldCup)
        self.assertEqual(report["targets"][2]["status"], "not_visible_in_account_catalogue")
        self.assertEqual(report["targets"][2]["candidate_count"], 0)
        self.assertEqual(report["status"], "partial")


if __name__ == "__main__":
    unittest.main()
