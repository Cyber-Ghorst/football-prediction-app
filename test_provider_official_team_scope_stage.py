import unittest

from provider_official_team_scope_stage import build_official_scope_stage_rows


class OfficialTeamScopeStageTests(unittest.TestCase):
    def test_complete_standings_candidate_is_staged_as_separate_evidence(self):
        audit = {
            "candidates": [{
                "provider": "highlightly",
                "provider_entity_id": "134391",
                "competition_provider_id": "67162",
                "competition_key": "bundesliga",
                "season_label": "2026/27",
                "official_team_name": "FC Bayern München",
                "official_reference_url": "https://www.bundesliga.com/en/bundesliga/clubs",
                "source_endpoint": "standings",
                "source_retrieved_at": "2026-11-16T13:00:00+00:00",
                "team_evidence_method": "league_season_standings",
                "provider_roster_observation_complete": True,
                "scope_candidate": {
                    "team_type": "club", "gender_scope": "male",
                    "age_group": "senior", "squad_scope": "first_team",
                },
                "status": "candidate_review_complete_standings",
                "promotion_allowed": False,
            }],
        }
        rows = build_official_scope_stage_rows(audit)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["provider"], "highlightly")
        self.assertEqual(row["season_label"], "2026/27")
        self.assertEqual(row["scope_candidate"]["age_group"], "senior")
        self.assertFalse(row["promotion_allowed"])
        self.assertEqual(row["evidence_status"], "candidate_review_complete_standings")
        self.assertEqual(row["source_endpoint"], "standings")

    def test_incomplete_participant_evidence_stays_incomplete(self):
        rows = build_official_scope_stage_rows({
            "candidates": [{
                "provider": "livescore_football",
                "provider_entity_id": "122",
                "competition_provider_id": "ger.1",
                "competition_key": "bundesliga",
                "season_label": "2026/27",
                "official_team_name": "1. FC Köln",
                "official_reference_url": "https://www.bundesliga.com/en/bundesliga/clubs",
                "source_endpoint": "fixtures",
                "source_retrieved_at": "2026-11-16T13:00:00+00:00",
                "team_evidence_method": "season_window_fixture_participants",
                "provider_roster_observation_complete": False,
                "scope_candidate": {
                    "team_type": "club", "gender_scope": "male",
                    "age_group": "senior", "squad_scope": "first_team",
                },
                "status": "candidate_review_incomplete_or_participant_evidence",
            }],
        })
        self.assertFalse(rows[0]["provider_roster_observation_complete"])
        self.assertFalse(rows[0]["promotion_allowed"])

    def test_api_football_nonmember_is_staged_as_held_without_scope_candidate(self):
        rows = build_official_scope_stage_rows({
            "candidates": [{
                "provider": "api_football",
                "provider_entity_id": "504",
                "competition_provider_id": "135",
                "competition_key": "serie_a",
                "season_label": "2024/25",
                "official_team_name": None,
                "official_reference_url": "https://en.legaseriea.it/serie-a/standings?app_v1=true",
                "team_evidence_method": "provider_league_season_team_catalogue",
                "provider_roster_observation_complete": False,
                "scope_candidate": None,
                "status": "held_not_in_official_2026_27_roster",
            }],
        })
        self.assertEqual(rows[0]["season_label"], "2024/25")
        self.assertIsNone(rows[0]["scope_candidate"])
        self.assertFalse(rows[0]["promotion_allowed"])

    def test_missing_required_identity_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            build_official_scope_stage_rows({
                "candidates": [{
                    "provider": "highlightly",
                    "provider_entity_id": "1",
                    "competition_provider_id": "67162",
                    "competition_key": "bundesliga",
                    "official_reference_url": "",
                    "status": "held",
                }],
            })


if __name__ == "__main__":
    unittest.main()
