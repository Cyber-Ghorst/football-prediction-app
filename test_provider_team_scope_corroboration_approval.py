import unittest

from provider_team_scope_corroboration_approval import build_approved_records


class TeamScopeCorroborationApprovalTests(unittest.TestCase):
    def test_builds_only_complete_exact_scope_approval_records(self):
        report = {
            "competitions": [{
                "target_provider": "livescore_football",
                "target_competition_provider_id": "ger.1",
                "api_ninjas_competition_code": "bundesliga",
                "candidates": [{
                    "target_provider": "livescore_football",
                    "target_provider_team_id": "ls-1",
                    "target_provider_team_name": "Bayern Munich",
                    "api_ninjas_team_id": "soccer-bayern",
                    "api_ninjas_team_name": "Bayern Munich",
                    "competition_scope": "ger.1",
                    "api_ninjas_domestic_competition": "bundesliga",
                    "identity_basis": "unique_exact_normalized_team_name_within_same_current_domestic_competition",
                    "country_code_iso3166_alpha2": "DE",
                    "country_name_from_iso_code": "Germany",
                    "team_type_from_api_ninjas": "club",
                    "gender_from_api_ninjas": "men",
                    "gender_scope_normalized_candidate": "male",
                    "status": "scope_corroboration_candidate",
                }],
            }],
        }
        rows = build_approved_records(report)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["country_name"], "Germany")
        self.assertEqual(rows[0]["team_type"], "club")
        self.assertEqual(rows[0]["gender_scope"], "male")
        self.assertEqual(rows[0]["corroborating_provider"], "api_ninjas")

    def test_does_not_approve_ambiguous_or_incomplete_candidates(self):
        candidate = {
            "target_provider": "highlightly",
            "target_provider_team_id": "hl-1",
            "target_provider_team_name": "Team",
            "api_ninjas_team_id": "soccer-team",
            "api_ninjas_team_name": "Team",
            "competition_scope": "67162",
            "api_ninjas_domestic_competition": "bundesliga",
            "country_code_iso3166_alpha2": "DE",
            "country_name_from_iso_code": "Germany",
            "team_type_from_api_ninjas": "club",
            "gender_from_api_ninjas": None,
            "gender_scope_normalized_candidate": None,
            "status": "held_api_ninjas_scope_incomplete",
        }
        self.assertEqual(
            build_approved_records({"competitions": [{"candidates": [candidate]}]}),
            [],
        )


if __name__ == "__main__":
    unittest.main()
