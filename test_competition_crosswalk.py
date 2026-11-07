import unittest

from competition_crosswalk import build_competition_crosswalk, verified_livescore_slug


class CompetitionCrosswalkTests(unittest.TestCase):
    def setUp(self):
        self.api = [{"league": {"id": 39, "name": "Premier League"},
                     "country": {"name": "England"}}]
        self.live = [{"slug": "eng.1", "name": "Premier League",
                      "country": "England", "active": True,
                      "season": {"year": 2026},
                      "coverage": {"hasData": True, "matches": 120}}]

    def test_exact_name_country_active_data_and_season_required(self):
        rows = build_competition_crosswalk(self.api, self.live, requested_season=2026)
        self.assertTrue(rows[0]["verified"])
        self.assertEqual(verified_livescore_slug(rows, 39), "eng.1")

    def test_name_only_or_country_mismatch_does_not_map(self):
        live = [dict(self.live[0], country="Scotland")]
        rows = build_competition_crosswalk(self.api, live, requested_season=2026)
        self.assertFalse(rows[0]["verified"])
        self.assertIsNone(verified_livescore_slug(rows, 39))

    def test_inactive_or_empty_competition_does_not_map(self):
        for change in ({"active": False}, {"coverage": {"hasData": False}}):
            live = [dict(self.live[0], **change)]
            rows = build_competition_crosswalk(self.api, live, requested_season=2026)
            self.assertFalse(rows[0]["verified"])

    def test_missing_or_mismatched_season_does_not_map(self):
        for season in (None, {"year": 2025}):
            live = [dict(self.live[0], season=season)]
            rows = build_competition_crosswalk(self.api, live, requested_season=2026)
            self.assertFalse(rows[0]["verified"])

    def test_duplicate_exact_candidates_are_ambiguous(self):
        rows = build_competition_crosswalk(self.api, self.live * 2, requested_season=2026)
        self.assertFalse(rows[0]["verified"])

    def test_unknown_competition_is_not_fuzzy_matched(self):
        api = [{"league": {"id": 2, "name": "Premier League Cup"},
                "country": {"name": "England"}}]
        rows = build_competition_crosswalk(api, self.live, requested_season=2026)
        self.assertFalse(rows[0]["verified"])


if __name__ == "__main__":
    unittest.main()
