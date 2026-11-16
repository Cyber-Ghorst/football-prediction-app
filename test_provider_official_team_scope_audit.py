import unittest

from provider_official_team_scope_audit import (
    OFFICIAL_COMPETITIONS,
    build_official_team_scope_audit,
    filter_duplicate_livescore_participant_rows,
)


class OfficialTeamScopeAuditTests(unittest.TestCase):
    def test_official_lists_cover_five_2026_27_top_flights(self):
        self.assertEqual(
            {key: len(value["teams"]) for key, value in OFFICIAL_COMPETITIONS.items()},
            {
                "premier_league": 20,
                "laliga": 20,
                "serie_a": 20,
                "bundesliga": 18,
                "ligue1": 18,
            },
        )

    def test_highlightly_complete_standings_produce_senior_first_team_review_candidate(self):
        report = build_official_team_scope_audit([{
            "provider": "highlightly",
            "provider_entity_id": "134391",
            "name": "Bayern Munich",
            "raw_payload": {
                "season_label": "2026",
                "competition_provider_ids": ["67162"],
                "source_endpoint": "standings",
                "source_retrieved_at": "2026-11-16T13:00:00+00:00",
                "team_evidence_method": "league_season_standings",
                "roster_observation_complete": True,
            },
        }])
        candidate = report["candidates"][0]
        self.assertEqual(candidate["official_team_name"], "FC Bayern München")
        self.assertEqual(candidate["status"], "candidate_review_complete_standings")
        self.assertEqual(candidate["scope_candidate"], {
            "team_type": "club",
            "gender_scope": "male",
            "age_group": "senior",
            "squad_scope": "first_team",
        })
        self.assertFalse(candidate["promotion_allowed"])
        self.assertEqual(report["canonical_ids_assigned"], 0)
        self.assertEqual(report["provider_links_created"], 0)

    def test_complete_livescore_standings_admit_all_36_roster_candidates_without_promotion(self):
        rows = []
        for competition_key, competition_id in (("bundesliga", "ger.1"), ("ligue1", "fra.1")):
            for index, team_name in enumerate(OFFICIAL_COMPETITIONS[competition_key]["teams"]):
                rows.append({
                    "provider": "livescore_football",
                    "provider_entity_id": f"{competition_key}-{index}",
                    "name": team_name,
                    "raw_payload": {
                        "season_label": "2026/27",
                        "competition_provider_ids": [competition_id],
                        "source_endpoint": f"/get/soccer/{competition_id}/standings",
                        "source_retrieved_at": "2026-11-16T13:00:00+00:00",
                        "team_evidence_method": "season_standings",
                        "team_evidence_complete": True,
                    },
                })
        report = build_official_team_scope_audit(rows)
        self.assertEqual(len(report["candidates"]), 36)
        self.assertTrue(all(
            row["status"] == "candidate_review_complete_standings"
            and row["promotion_allowed"] is False
            and row["scope_candidate"] == {
                "team_type": "club", "gender_scope": "male",
                "age_group": "senior", "squad_scope": "first_team",
            }
            for row in report["candidates"]
        ))
        self.assertEqual(report["canonical_ids_assigned"], 0)
        self.assertEqual(report["provider_links_created"], 0)

    def test_livescore_reviewed_alias_remains_incomplete_participant_evidence(self):
        report = build_official_team_scope_audit([{
            "provider": "livescore_football",
            "provider_entity_id": "122",
            "name": "FC Cologne",
            "raw_payload": {
                "season_label": "2026",
                "competition_provider_ids": ["ger.1"],
                "source_endpoint": "fixtures",
                "source_retrieved_at": "2026-11-16T13:00:00+00:00",
                "team_evidence_method": "season_window_fixture_participants",
                "team_evidence_complete": False,
            },
        }])
        candidate = report["candidates"][0]
        self.assertEqual(candidate["official_team_name"], "1. FC Köln")
        self.assertEqual(candidate["name_match_method"], "reviewed_official_name_alias")
        self.assertEqual(
            candidate["status"],
            "candidate_review_incomplete_or_participant_evidence",
        )
        self.assertFalse(candidate["provider_roster_observation_complete"])


    def test_laliga_provider_name_variants_match_official_club_list(self):
        rows = [
            ("679031", "Elche", "Elche CF"),
            ("465430", "Getafe", "Getafe CF"),
            ("467132", "Villarreal", "Villarreal CF"),
        ]
        report = build_official_team_scope_audit([
            {
                "provider": "highlightly",
                "provider_entity_id": provider_id,
                "name": name,
                "raw_payload": {
                    "season_label": "2026",
                    "competition_provider_ids": ["119924"],
                    "team_evidence_method": "league_season_standings",
                    "roster_observation_complete": True,
                },
            }
            for provider_id, name, _ in rows
        ])
        self.assertEqual(
            {candidate["official_team_name"] for candidate in report["candidates"]},
            {official_name for _, _, official_name in rows},
        )
        self.assertTrue(all(candidate["status"] == "candidate_review_complete_standings"
                            for candidate in report["candidates"]))

    def test_missing_and_wrong_season_are_held(self):
        report = build_official_team_scope_audit([
            {
                "provider": "highlightly", "provider_entity_id": "1", "name": "Bayern Munich",
                "raw_payload": {"competition_provider_ids": ["67162"]},
            },
            {
                "provider": "highlightly", "provider_entity_id": "2", "name": "Bayern Munich",
                "raw_payload": {"season_label": "2024", "competition_provider_ids": ["67162"]},
            },
        ])
        self.assertEqual(
            [row["status"] for row in report["candidates"]],
            ["held_missing_explicit_2026_27_season", "held_wrong_season"],
        )
        self.assertTrue(all(row["scope_candidate"] is None for row in report["candidates"]))


    def test_api_football_stale_season_name_match_is_not_current_membership_approval(self):
        report = build_official_team_scope_audit([
            {
                "provider": "api_football", "provider_entity_id": "35", "name": "Bournemouth",
                "raw_payload": {
                    "season_label": "2024", "competition_provider_ids": ["39"],
                },
            },
            {
                "provider": "api_football", "provider_entity_id": "46", "name": "Leicester",
                "raw_payload": {
                    "season_label": "2024", "competition_provider_ids": ["39"],
                },
            },
        ])
        current_name_match, not_current_member = report["candidates"]
        self.assertEqual(
            current_name_match["status"],
            "candidate_name_matches_official_roster_but_provider_season_stale",
        )
        self.assertEqual(current_name_match["official_team_name"], "AFC Bournemouth")
        self.assertIsNone(current_name_match["scope_candidate"])
        self.assertEqual(not_current_member["status"], "held_not_in_official_2026_27_roster")
        self.assertIsNone(not_current_member["official_team_name"])
        self.assertIsNone(not_current_member["scope_candidate"])
        self.assertEqual(report["canonical_ids_assigned"], 0)
        self.assertEqual(report["provider_links_created"], 0)


    def test_api_football_existing_scope_filter_is_competition_scoped(self):
        report = build_official_team_scope_audit(
            [
                {
                    "provider": "api_football", "provider_entity_id": "39", "name": "Bournemouth",
                    "raw_payload": {
                        "season_label": "2024", "competition_provider_ids": ["39"],
                    },
                },
                {
                    "provider": "api_football", "provider_entity_id": "505", "name": "Inter",
                    "raw_payload": {
                        "season_label": "2024", "competition_provider_ids": ["135"],
                    },
                },
            ],
            existing_api_football_scope_pairs={("39", "39")},
        )
        self.assertEqual(len(report["candidates"]), 1)
        self.assertEqual(report["candidates"][0]["provider_entity_id"], "505")
        self.assertEqual(report["candidates"][0]["competition_key"], "serie_a")
        self.assertEqual(
            report["candidates"][0]["status"],
            "candidate_name_matches_official_roster_but_provider_season_stale",
        )

    def test_unmatched_official_name_is_held(self):
        report = build_official_team_scope_audit([{
            "provider": "highlightly", "provider_entity_id": "999", "name": "Unknown FC",
            "raw_payload": {
                "season_label": "2026", "competition_provider_ids": ["67162"],
                "team_evidence_method": "league_season_standings",
                "roster_observation_complete": True,
            },
        }])
        self.assertEqual(report["candidates"][0]["status"], "held_official_team_name_unmatched")
        self.assertIsNone(report["candidates"][0]["scope_candidate"])

    def test_filter_preserves_only_real_participant_rows_and_keeps_standings_candidates(self):
        participant = {
            "provider": "livescore_football",
            "provider_entity_id": "131",
            "name": "Bayer Leverkusen",
            "source_repository_row": True,
            "raw_payload": {
                "competition_provider_ids": ["ger.1"],
                "team_evidence_method": "season_window_fixture_participants",
                "source_endpoint": "fixtures",
            },
        }
        standings = {
            "provider": "livescore_football",
            "provider_entity_id": "131",
            "name": "Bayer Leverkusen",
            "source_repository_row": False,
            "raw_payload": {
                "competition_provider_ids": ["ger.1"],
                "season_label": "2026/27",
                "team_evidence_method": "season_standings",
                "source_endpoint": "/get/soccer/ger.1/standings",
            },
        }
        filtered, preserved = filter_duplicate_livescore_participant_rows(
            [participant, standings], {("131", "ger.1")}
        )
        self.assertEqual(filtered, [standings])
        self.assertEqual(len(preserved), 1)
        self.assertEqual(preserved[0]["evidence_method"], "season_window_fixture_participants")
        self.assertTrue(preserved[0]["retained_in_source_repository"])

    def test_non_overlapping_participant_rows_remain_available_as_fallback(self):
        participant = {
            "provider": "livescore_football",
            "provider_entity_id": "999",
            "name": "New Club",
            "source_repository_row": True,
            "raw_payload": {
                "competition_provider_ids": ["fra.1"],
                "team_evidence_method": "season_window_fixture_participants",
            },
        }
        filtered, preserved = filter_duplicate_livescore_participant_rows(
            [participant], {("131", "ger.1")}
        )
        self.assertEqual(filtered, [participant])
        self.assertEqual(preserved, [])



if __name__ == "__main__":
    unittest.main()
