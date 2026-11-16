import unittest

from provider_team_scope_corroboration_audit import build_corroboration_report


class ProviderTeamScopeCorroborationAuditTests(unittest.TestCase):
    def test_highlightly_five_domestic_competition_ids_are_mapped(self):
        rows = []
        report = build_corroboration_report(rows)
        highlightly = {
            row["target_competition_provider_id"]: row["api_ninjas_competition_code"]
            for row in report["competitions"]
            if row["target_provider"] == "highlightly"
        }
        self.assertEqual(
            highlightly,
            {
                "33973": "epl",
                "119924": "laliga",
                "115669": "seriea",
                "67162": "bundesliga",
                "52695": "ligue1",
            },
        )

    def test_highlightly_scope_audit_covers_all_five_domestic_competitions(self):
        rows = [
            {"provider": "api_ninjas", "provider_entity_id": "soccer-arsenal",
             "name": "Arsenal", "country": "GB", "team_type": "club",
             "gender_scope": "men",
             "raw_payload": {"domestic_league_codes": ["epl"]}},
            {"provider": "api_ninjas", "provider_entity_id": "soccer-real-madrid",
             "name": "Real Madrid", "country": "ES", "team_type": "club",
             "gender_scope": "men",
             "raw_payload": {"domestic_league_codes": ["laliga"]}},
            {"provider": "api_ninjas", "provider_entity_id": "soccer-ac-milan",
             "name": "AC Milan", "country": "IT", "team_type": "club",
             "gender_scope": "men",
             "raw_payload": {"domestic_league_codes": ["seriea"]}},
            {"provider": "highlightly", "provider_entity_id": "33973-1",
             "name": "Arsenal",
             "raw_payload": {"competition_provider_ids": ["33973"]}},
            {"provider": "highlightly", "provider_entity_id": "119924-1",
             "name": "Real Madrid",
             "raw_payload": {"competition_provider_ids": ["119924"]}},
            {"provider": "highlightly", "provider_entity_id": "115669-1",
             "name": "AC Milan",
             "raw_payload": {"competition_provider_ids": ["115669"]}},
        ]
        report = build_corroboration_report(rows)
        expected = {
            "33973": ("epl", "Arsenal"),
            "119924": ("laliga", "Real Madrid"),
            "115669": ("seriea", "AC Milan"),
        }
        for competition_id, (api_code, team_name) in expected.items():
            competition = next(
                row for row in report["competitions"]
                if row["target_provider"] == "highlightly"
                and row["target_competition_provider_id"] == competition_id
            )
            self.assertEqual(competition["api_ninjas_competition_code"], api_code)
            self.assertEqual(competition["target_team_rows"], 1)
            self.assertEqual(competition["unique_exact_name_candidates"], 1)
            self.assertEqual(competition["candidates"][0]["target_provider_team_name"], team_name)
        self.assertEqual(report["unique_exact_name_candidates"], 3)
        self.assertEqual(report["scope_complete_candidates"], 3)
        self.assertEqual(report["provider_links_created"], 0)

    def test_exact_unique_name_in_same_competition_is_candidate_only(self):
        rows = [
            {"provider": "api_ninjas", "provider_entity_id": "soccer-bayern",
             "name": "Bayern Munich", "country": "DE", "team_type": "club",
             "gender_scope": "men",
             "raw_payload": {"domestic_league_codes": ["bundesliga"]}},
            {"provider": "livescore_football", "provider_entity_id": "ger-1",
             "name": "Bayern Munich", "country": None, "team_type": None,
             "gender_scope": None,
             "raw_payload": {"competition_provider_ids": ["ger.1"]}},
        ]
        report = build_corroboration_report(rows)
        competition = next(row for row in report["competitions"]
                           if row["target_provider"] == "livescore_football"
                           and row["target_competition_provider_id"] == "ger.1")
        self.assertEqual(competition["scope_complete_candidates"], 1)
        self.assertEqual(
            competition["api_ninjas_team_catalogue"][0]["provider_entity_id"],
            "soccer-bayern",
        )
        candidate = competition["candidates"][0]
        self.assertEqual(candidate["country_name_from_iso_code"], "Germany")
        self.assertEqual(candidate["gender_scope_normalized_candidate"], "male")
        self.assertEqual(candidate["status"], "scope_corroboration_candidate")
        self.assertEqual(report["provider_links_created"], 0)
        self.assertEqual(report["provider_scope_fields_updated"], 0)

    def test_api_football_exact_match_is_scoped_to_the_same_domestic_competition(self):
        rows = [
            {"provider": "api_ninjas", "provider_entity_id": "soccer-arsenal",
             "name": "Arsenal", "country": "GB", "team_type": "club",
             "gender_scope": "men",
             "raw_payload": {"domestic_league_codes": ["epl"]}},
            {"provider": "api_football", "provider_entity_id": "42",
             "name": "Arsenal", "country": "England", "team_type": "club",
             "raw_payload": {"competition_provider_ids": ["39"]}},
            {"provider": "api_football", "provider_entity_id": "999",
             "name": "Arsenal", "country": "Spain", "team_type": "club",
             "raw_payload": {"competition_provider_ids": ["140"]}},
        ]
        report = build_corroboration_report(rows)
        premier = next(row for row in report["competitions"]
                       if row["target_provider"] == "api_football"
                       and row["target_competition_provider_id"] == "39")
        la_liga = next(row for row in report["competitions"]
                       if row["target_provider"] == "api_football"
                       and row["target_competition_provider_id"] == "140")
        self.assertEqual(premier["unique_exact_name_candidates"], 1)
        self.assertEqual(
            premier["candidates"][0]["gender_scope_normalized_candidate"], "male"
        )
        self.assertEqual(la_liga["unique_exact_name_candidates"], 0)
        self.assertEqual(la_liga["unmatched_target_teams"][0]["provider_entity_id"], "999")

    def test_reports_unmatched_target_team_ids_without_guessing_aliases(self):
        rows = [
            {"provider": "api_ninjas", "provider_entity_id": "soccer-bayern",
             "name": "Bayern Munich", "country": "DE", "team_type": "club",
             "gender_scope": "men",
             "raw_payload": {"domestic_league_codes": ["bundesliga"]}},
            {"provider": "livescore_football", "provider_entity_id": "ger-1",
             "name": "Bayern Munich",
             "raw_payload": {"competition_provider_ids": ["ger.1"]}},
            {"provider": "livescore_football", "provider_entity_id": "ger-2",
             "name": "Unmatched FC",
             "raw_payload": {"competition_provider_ids": ["ger.1"]}},
        ]
        report = build_corroboration_report(rows)
        competition = next(row for row in report["competitions"]
                           if row["target_provider"] == "livescore_football"
                           and row["target_competition_provider_id"] == "ger.1")
        self.assertEqual(competition["unmatched_target_team_rows"], 1)
        self.assertEqual(
            competition["unmatched_target_teams"][0]["provider_entity_id"],
            "ger-2",
        )
        self.assertEqual(
            competition["unmatched_target_teams"][0]["reason"],
            "no_unique_exact_normalized_name_match_in_api_ninjas_competition",
        )

    def test_near_name_candidates_are_review_only_and_never_exact_matches(self):
        rows = [
            {"provider": "api_ninjas", "provider_entity_id": "soccer-union",
             "name": "1. FC Union Berlin", "country": "DE", "team_type": "club",
             "gender_scope": "men",
             "raw_payload": {"domestic_league_codes": ["bundesliga"]}},
            {"provider": "livescore_football", "provider_entity_id": "ger-1",
             "name": "Union Berlin",
             "raw_payload": {"competition_provider_ids": ["ger.1"]}},
        ]
        report = build_corroboration_report(rows)
        competition = next(row for row in report["competitions"]
                           if row["target_provider"] == "livescore_football"
                           and row["target_competition_provider_id"] == "ger.1")
        self.assertEqual(competition["unique_exact_name_candidates"], 0)
        unmatched = competition["unmatched_target_teams"][0]
        self.assertTrue(unmatched["near_name_candidates"])
        self.assertEqual(
            unmatched["near_name_candidates"][0]["review_status"],
            "manual_review_only_not_an_identity_match",
        )
        self.assertEqual(competition["scope_complete_candidates"], 0)

    def test_reports_persisted_manual_alias_approvals_separately_from_unmatched(self):
        rows = [
            {"provider": "api_ninjas", "provider_entity_id": "soccer-aj-auxerre",
             "name": "AJ Auxerre", "country": "FR", "team_type": "club",
             "gender_scope": "men",
             "raw_payload": {"domestic_league_codes": ["ligue1"]}},
            {"provider": "highlightly", "provider_entity_id": "92692",
             "name": "Auxerre",
             "raw_payload": {"competition_provider_ids": ["52695"]}},
        ]
        approved = [{
            "provider": "highlightly", "provider_entity_id": "92692",
            "corroborating_entity_id": "soccer-aj-auxerre",
            "competition_provider_id": "52695",
            "match_method": "manual_official_competition_alias_review",
            "country_name": "France", "team_type": "club", "gender_scope": "male",
        }]
        report = build_corroboration_report(rows, approved)
        competition = next(row for row in report["competitions"]
                           if row["target_provider"] == "highlightly"
                           and row["target_competition_provider_id"] == "52695")
        self.assertEqual(competition["approved_manual_alias_corroborations"], 1)
        self.assertEqual(competition["unmatched_target_team_rows"], 0)
        self.assertEqual(report["approved_scope_corroborations"], 1)
        self.assertEqual(
            report["approved_by_match_method"]["manual_official_competition_alias_review"],
            1,
        )

    def test_does_not_match_across_competitions_or_ambiguous_names(self):
        rows = [
            {"provider": "api_ninjas", "provider_entity_id": "a1",
             "name": "Same FC", "country": "DE", "team_type": "club",
             "gender_scope": "men",
             "raw_payload": {"domestic_league_codes": ["bundesliga"]}},
            {"provider": "api_ninjas", "provider_entity_id": "a2",
             "name": "Same FC", "country": "DE", "team_type": "club",
             "gender_scope": "men",
             "raw_payload": {"domestic_league_codes": ["bundesliga"]}},
            {"provider": "livescore_football", "provider_entity_id": "x",
             "name": "Same FC", "raw_payload": {"competition_provider_ids": ["ger.1"]}},
        ]
        report = build_corroboration_report(rows)
        competition = next(row for row in report["competitions"]
                           if row["target_provider"] == "livescore_football"
                           and row["target_competition_provider_id"] == "ger.1")
        self.assertEqual(competition["unique_exact_name_candidates"], 0)
        self.assertEqual(len(competition["ambiguous_name_groups"]), 1)


if __name__ == "__main__":
    unittest.main()
