import unittest
from provider_team_scope_corroboration_audit import build_corroboration_report

class ProviderTeamScopeCorroborationAuditTests(unittest.TestCase):
    def _rows(self, target_season=None, api_season=None):
        target_raw = {"competition_provider_ids": ["ger.1"]}
        api_raw = {"domestic_league_codes": ["bundesliga"]}
        if target_season is not None:
            target_raw["season_label"] = target_season
        if api_season is not None:
            api_raw["season_label"] = api_season
        return [
            {"provider":"api_ninjas","provider_entity_id":"soccer-bayern","name":"Bayern Munich",
             "country":"DE","team_type":"club","gender_scope":"men","raw_payload":api_raw},
            {"provider":"livescore_football","provider_entity_id":"ls-1","name":"Bayern Munich",
             "raw_payload":target_raw},
        ]

    def _competition(self, report):
        return next(row for row in report["competitions"]
                    if row["target_provider"] == "livescore_football"
                    and row["target_competition_provider_id"] == "ger.1")

    def test_exact_name_is_not_candidate_when_season_missing(self):
        report = build_corroboration_report(self._rows())
        candidate = self._competition(report)["candidates"][0]
        self.assertEqual(candidate["status"], "held_missing_explicit_season")
        self.assertFalse(candidate["season_match_verified"])
        self.assertEqual(report["approved_scope_corroborations"], 0)

    def test_wrong_season_is_held(self):
        report = build_corroboration_report(self._rows("2026/27", "2024"))
        candidate = self._competition(report)["candidates"][0]
        self.assertEqual(candidate["status"], "held_mismatched_season")
        self.assertFalse(candidate["season_match_verified"])

    def test_matching_explicit_2026_27_season_is_candidate(self):
        report = build_corroboration_report(self._rows("2026/27", "2026/27"))
        candidate = self._competition(report)["candidates"][0]
        self.assertEqual(candidate["status"], "scope_corroboration_candidate")
        self.assertTrue(candidate["season_match_verified"])
        self.assertEqual(candidate["target_season_label"], "2026/27")
        self.assertEqual(candidate["api_ninjas_season_label"], "2026/27")

    def test_existing_approvals_are_reported_as_legacy_provisional(self):
        approved = [{"provider":"highlightly","provider_entity_id":"1"}]
        report = build_corroboration_report([], approved)
        self.assertEqual(report["approved_scope_corroborations"], 0)
        self.assertEqual(report["legacy_provisional_scope_corroborations"], 1)

if __name__ == "__main__":
    unittest.main()
