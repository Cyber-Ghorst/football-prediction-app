import unittest

from provider_team_scope_corroboration_audit import build_corroboration_report


class ProviderTeamScopeCorroborationAuditTests(unittest.TestCase):
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
        candidate = competition["candidates"][0]
        self.assertEqual(candidate["country_name_from_iso_code"], "Germany")
        self.assertEqual(candidate["gender_scope_normalized_candidate"], "male")
        self.assertEqual(candidate["status"], "scope_corroboration_candidate")
        self.assertEqual(report["provider_links_created"], 0)
        self.assertEqual(report["provider_scope_fields_updated"], 0)

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
