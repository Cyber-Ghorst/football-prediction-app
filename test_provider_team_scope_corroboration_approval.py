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

    def test_approves_allowlisted_alias_only_after_exact_scope_revalidation(self):
        report = {"competitions": [{
            "target_provider": "highlightly",
            "target_competition_provider_id": "52695",
            "unmatched_target_teams": [{
                "provider_entity_id": "92692", "name": "Auxerre",
                "near_name_candidates": [{
                    "api_ninjas_team_id": "soccer-aj-auxerre",
                    "api_ninjas_team_name": "AJ Auxerre",
                    "country_code_iso3166_alpha2": "FR",
                    "country_name_from_iso_code": "France",
                    "team_type_from_api_ninjas": "club",
                    "gender_from_api_ninjas": "men",
                    "api_ninjas_domestic_competition": "ligue1",
                }],
            }],
        }]}
        rows = build_approved_records(report)
        alias = next(row for row in rows
                     if row["match_method"] == "manual_official_competition_alias_review")
        self.assertEqual(alias["provider_entity_id"], "92692")
        self.assertEqual(alias["corroborating_entity_id"], "soccer-aj-auxerre")
        self.assertTrue(alias["evidence_snapshot"]["official_reference_urls"])

    def test_approves_catalogue_verified_alias_without_fuzzy_suggestion(self):
        report = {"competitions": [{
            "target_provider": "highlightly",
            "target_competition_provider_id": "52695",
            "api_ninjas_competition_code": "ligue1",
            "api_ninjas_team_catalogue": [{
                "provider_entity_id": "soccer-brest",
                "name": "Brest",
                "country_code": "FR",
                "team_type": "club",
                "gender_scope": "men",
            }],
            "unmatched_target_teams": [{
                "provider_entity_id": "90990",
                "name": "Stade Brestois 29",
                "near_name_candidates": [],
            }],
        }]}
        rows = build_approved_records(report)
        alias = next(row for row in rows
                     if row["match_method"] == "manual_official_competition_alias_review")
        self.assertEqual(alias["provider_entity_id"], "90990")
        self.assertEqual(alias["corroborating_entity_id"], "soccer-brest")
        self.assertEqual(alias["evidence_snapshot"]["country_name_from_iso_code"], "France")

    def test_api_football_manual_aliases_require_official_2026_27_competition_evidence(self):
        report = {"competitions": [
            {
                "target_provider": "api_football",
                "target_competition_provider_id": "39",
                "api_ninjas_competition_code": "epl",
                "api_ninjas_team_catalogue": [{
                    "provider_entity_id": "soccer-afc-bournemouth",
                    "name": "AFC Bournemouth", "country_code": "GB",
                    "team_type": "club", "gender_scope": "men",
                }],
                "unmatched_target_teams": [{
                    "provider_entity_id": "35", "name": "Bournemouth",
                    "near_name_candidates": [],
                }],
            },
            {
                "target_provider": "api_football",
                "target_competition_provider_id": "61",
                "api_ninjas_competition_code": "ligue1",
                "api_ninjas_team_catalogue": [{
                    "provider_entity_id": "soccer-aj-auxerre",
                    "name": "AJ Auxerre", "country_code": "FR",
                    "team_type": "club", "gender_scope": "men",
                }],
                "unmatched_target_teams": [{
                    "provider_entity_id": "108", "name": "Auxerre",
                    "near_name_candidates": [],
                }],
            },
        ]}
        rows = build_approved_records(report)
        aliases = [row for row in rows
                   if row["match_method"] == "manual_official_competition_alias_review"]
        self.assertEqual(len(aliases), 2)
        by_target = {row["provider_entity_id"]: row for row in aliases}
        self.assertEqual(by_target["35"]["corroborating_entity_id"],
                         "soccer-afc-bournemouth")
        self.assertEqual(by_target["108"]["corroborating_entity_id"],
                         "soccer-aj-auxerre")
        self.assertTrue(
            by_target["35"]["evidence_snapshot"]["official_reference_urls"][0]
            .startswith("https://www.premierleague.com/")
        )
        self.assertTrue(
            by_target["108"]["evidence_snapshot"]["official_reference_urls"][0]
            .startswith("https://ligue1.com/")
        )

    def test_wrong_api_id_does_not_pass_manual_alias_allowlist(self):
        report = {"competitions": [{
            "target_provider": "highlightly",
            "target_competition_provider_id": "52695",
            "unmatched_target_teams": [{
                "provider_entity_id": "92692", "name": "Auxerre",
                "near_name_candidates": [{
                    "api_ninjas_team_id": "wrong-id",
                    "api_ninjas_team_name": "AJ Auxerre",
                    "country_code_iso3166_alpha2": "FR",
                    "country_name_from_iso_code": "France",
                    "team_type_from_api_ninjas": "club",
                    "gender_from_api_ninjas": "men",
                    "api_ninjas_domestic_competition": "ligue1",
                }],
            }],
        }]}
        self.assertFalse(any(
            row["match_method"] == "manual_official_competition_alias_review"
            for row in build_approved_records(report)
        ))

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
