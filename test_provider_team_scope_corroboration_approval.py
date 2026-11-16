import unittest
from provider_team_scope_corroboration_approval import build_approved_records

class TeamScopeCorroborationApprovalTests(unittest.TestCase):
    def _candidate(self, target_season=None, api_season=None, verified=False):
        return {
            "target_provider":"livescore_football","target_provider_team_id":"ls-1",
            "target_provider_team_name":"Bayern Munich","api_ninjas_team_id":"soccer-bayern",
            "api_ninjas_team_name":"Bayern Munich","competition_scope":"ger.1",
            "api_ninjas_domestic_competition":"bundesliga",
            "country_code_iso3166_alpha2":"DE","country_name_from_iso_code":"Germany",
            "team_type_from_api_ninjas":"club","gender_from_api_ninjas":"men",
            "gender_scope_normalized_candidate":"male","status":"scope_corroboration_candidate",
            "target_season_label":target_season,"api_ninjas_season_label":api_season,
            "season_match_verified":verified,
        }

    def _report(self, candidate):
        return {"competitions":[{"target_provider":"livescore_football",
            "target_competition_provider_id":"ger.1","api_ninjas_competition_code":"bundesliga",
            "candidates":[candidate]}]}

    def test_missing_season_is_never_approved(self):
        self.assertEqual(build_approved_records(self._report(self._candidate())), [])

    def test_wrong_season_is_never_approved(self):
        self.assertEqual(build_approved_records(
            self._report(self._candidate("2026/27","2024",False))), [])

    def test_explicit_matching_2026_27_season_is_approved(self):
        rows = build_approved_records(
            self._report(self._candidate("2026/27","2026/27",True)))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["evidence_snapshot"]["target_season_label"], "2026/27")
        self.assertEqual(rows[0]["evidence_snapshot"]["api_ninjas_season_label"], "2026/27")

    def test_manual_alias_without_explicit_season_is_held(self):
        report = {"competitions":[{"target_provider":"highlightly",
            "target_competition_provider_id":"52695","api_ninjas_competition_code":"ligue1",
            "api_ninjas_team_catalogue":[{"provider_entity_id":"soccer-aj-auxerre",
                "name":"AJ Auxerre","country_code":"FR","team_type":"club","gender_scope":"men"}],
            "unmatched_target_teams":[{"provider_entity_id":"92692","name":"Auxerre",
                "near_name_candidates":[]}]}]}
        self.assertEqual(build_approved_records(report), [])

if __name__ == "__main__":
    unittest.main()
