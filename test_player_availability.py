import unittest

from player_availability import assess_player_availability


class PlayerAvailabilityTests(unittest.TestCase):
    def test_importance_weighted_score_uses_complete_evidence(self):
        result = assess_player_availability({
            "roster_complete": True,
            "source": "verified_test_feed",
            "fixture_id": 123,
            "squad_players": [
                {"player_id": 1, "status": "available", "importance": 80},
                {"player_id": 2, "status": "unavailable", "importance": 20},
            ],
        })
        self.assertEqual(result["score"], 80.0)
        self.assertEqual(result["status"], "scored")
        self.assertEqual(result["players_assessed"], 2)

    def test_partial_sidelined_list_stays_unknown(self):
        result = assess_player_availability({
            "roster_complete": False,
            "reported_sidelined": [{"player_id": 2}],
        })
        self.assertIsNone(result["score"])
        self.assertEqual(result["status"], "unknown")

    def test_unknown_player_status_stays_unknown(self):
        result = assess_player_availability({
            "roster_complete": True,
            "squad_players": [
                {"player_id": 1, "status": "available", "importance": 50},
                {"player_id": 2, "status": "unknown", "importance": 50},
            ],
        })
        self.assertIsNone(result["score"])

    def test_missing_importance_stays_unknown(self):
        result = assess_player_availability({
            "roster_complete": True,
            "squad_players": [{"player_id": 1, "status": "unavailable"}],
        })
        self.assertIsNone(result["score"])

    def test_duplicate_player_ids_stay_unknown(self):
        result = assess_player_availability({
            "roster_complete": True,
            "squad_players": [
                {"player_id": 1, "status": "available", "importance": 50},
                {"player_id": 1, "status": "unavailable", "importance": 50},
            ],
        })
        self.assertIsNone(result["score"])

    def test_zero_total_importance_stays_unknown(self):
        result = assess_player_availability({
            "roster_complete": True,
            "squad_players": [{"player_id": 1, "status": "available", "importance": 0}],
        })
        self.assertIsNone(result["score"])


    def test_sportmonks_current_squad_and_fixture_sidelined_build_verified_evidence(self):
        from player_availability import build_sportmonks_availability_evidence

        squad = [
            {"id": 1, "in_squad": True, "display_name": "Regular Player",
             "statistics": [{"player_id": 1, "team_id": 10, "season_id": 2026,
                 "has_values": True, "details": [{"type_id": 119, "value": {"total": 900}}]}]},
            {"id": 2, "in_squad": True, "display_name": "Unavailable Player",
             "statistics": [{"player_id": 2, "team_id": 10, "season_id": 2026,
                 "has_values": True, "details": [{"type_id": 119, "value": {"total": 450}}]}]},
            {"id": 3, "in_squad": False, "display_name": "Former Player", "statistics": []},
        ]
        evidence = build_sportmonks_availability_evidence(
            squad_rows=squad,
            sidelined_rows=[{
                "player_id": 2, "team_id": 10, "completed": False,
                "start_date": "2026-11-01", "end_date": None,
            }],
            sidelined_feed_available=True,
            team_id=10,
            season_id=2026,
            fixture_id=123,
            kickoff="2026-11-23T20:00:00Z",
        )
        result = assess_player_availability(evidence)
        self.assertTrue(evidence["roster_complete"])
        self.assertEqual(evidence["players_assessed"], 2)
        self.assertEqual(result["score"], 66.7)
        self.assertEqual(result["status"], "scored")

    def test_empty_confirmed_sidelined_feed_means_all_squad_players_available(self):
        from player_availability import build_sportmonks_availability_evidence

        squad = [{
            "id": 1, "in_squad": True,
            "statistics": [{"player_id": 1, "team_id": 10, "season_id": 2026,
                "has_values": True, "details": [{"type_id": 119, "value": {"total": 900}}]}],
        }]
        evidence = build_sportmonks_availability_evidence(
            squad_rows=squad, sidelined_rows=[], sidelined_feed_available=True,
            team_id=10, season_id=2026, fixture_id=123, kickoff="2026-11-23",
        )
        self.assertEqual(assess_player_availability(evidence)["score"], 100.0)

    def test_missing_sidelined_feed_keeps_availability_unknown(self):
        from player_availability import build_sportmonks_availability_evidence

        evidence = build_sportmonks_availability_evidence(
            squad_rows=[{"id": 1, "in_squad": True,
                         "statistics": [{"player_id": 1, "team_id": 10, "season_id": 2026,
                           "details": [{"type_id": 119, "value": {"total": 900}}]}]}],
            sidelined_rows=[], sidelined_feed_available=False,
            team_id=10, season_id=2026, fixture_id=123, kickoff="2026-11-23",
        )
        self.assertIsNone(assess_player_availability(evidence)["score"])

    def test_mismatched_squad_season_and_missing_minutes_are_rejected(self):
        from player_availability import build_sportmonks_availability_evidence

        bad_rows = [
            {"id": 1, "in_squad": True, "statistics": [
                {"player_id": 1, "team_id": 10, "season_id": 2025,
                 "details": [{"type_id": 119, "value": {"total": 900}}]}]},
            {"id": 1, "in_squad": True, "statistics": [
                {"player_id": 1, "team_id": 10, "season_id": 2026, "details": []}]},
        ]
        for rows in bad_rows:
            evidence = build_sportmonks_availability_evidence(
                squad_rows=[rows], sidelined_rows=[], sidelined_feed_available=True,
                team_id=10, season_id=2026, fixture_id=123, kickoff="2026-11-23",
            )
            self.assertIsNone(assess_player_availability(evidence)["score"])

    def test_unavailable_player_without_minutes_keeps_score_unknown(self):
        from player_availability import build_sportmonks_availability_evidence

        evidence = build_sportmonks_availability_evidence(
            squad_rows=[{
                "id": 1, "in_squad": True,
                "statistics": [{"player_id": 1, "team_id": 10, "season_id": 2026,
                    "details": [{"type_id": 119, "value": {"total": 0}}]}],
            }],
            sidelined_rows=[{
                "player_id": 1, "team_id": 10, "completed": False,
                "start_date": "2026-11-01", "end_date": None,
            }],
            sidelined_feed_available=True,
            team_id=10, season_id=2026, fixture_id=123, kickoff="2026-11-23",
        )
        self.assertIsNone(assess_player_availability(evidence)["score"])

    def test_missing_current_squad_flag_keeps_availability_unknown(self):
        from player_availability import build_sportmonks_availability_evidence

        evidence = build_sportmonks_availability_evidence(
            squad_rows=[{"id": 1, "statistics": []}],
            sidelined_rows=[], sidelined_feed_available=True,
            team_id=10, season_id=2026, fixture_id=123, kickoff="2026-11-23",
        )
        self.assertIsNone(assess_player_availability(evidence)["score"])

    def test_completed_absence_before_kickoff_is_available(self):
        from player_availability import build_sportmonks_availability_evidence

        squad = [{
            "id": 1, "in_squad": True,
            "statistics": [{"player_id": 1, "team_id": 10, "season_id": 2026,
                "details": [{"type_id": 119, "value": {"total": 900}}]}],
        }]
        evidence = build_sportmonks_availability_evidence(
            squad_rows=squad,
            sidelined_rows=[{
                "player_id": 1, "team_id": 10, "completed": True,
                "start_date": "2026-10-01", "end_date": "2026-10-15",
            }],
            sidelined_feed_available=True,
            team_id=10, season_id=2026, fixture_id=123, kickoff="2026-11-23",
        )
        self.assertEqual(assess_player_availability(evidence)["score"], 100.0)

    def test_pending_absence_with_return_before_kickoff_stays_unknown(self):
        from player_availability import build_sportmonks_availability_evidence

        squad = [{
            "id": 1, "in_squad": True,
            "statistics": [{"player_id": 1, "team_id": 10, "season_id": 2026,
                "details": [{"type_id": 119, "value": {"total": 900}}]}],
        }]
        evidence = build_sportmonks_availability_evidence(
            squad_rows=squad,
            sidelined_rows=[{
                "player_id": 1, "team_id": 10, "completed": False,
                "start_date": "2026-10-01", "end_date": "2026-11-15",
            }],
            sidelined_feed_available=True,
            team_id=10, season_id=2026, fixture_id=123, kickoff="2026-11-23",
        )
        self.assertIsNone(assess_player_availability(evidence)["score"])

    def test_sidelined_fixture_and_season_mismatch_keep_score_unknown(self):
        from player_availability import build_sportmonks_availability_evidence

        squad = [{
            "id": 1, "in_squad": True,
            "statistics": [{"player_id": 1, "team_id": 10, "season_id": 2026,
                "details": [{"type_id": 119, "value": {"total": 900}}]}],
        }]
        for mismatch in (
            {"fixture_id": 999, "season_id": 2026},
            {"fixture_id": 123, "season_id": 2025},
        ):
            sidelined = {
                "player_id": 1, "team_id": 10, "completed": False,
                "start_date": "2026-11-01", "end_date": None,
                **mismatch,
            }
            evidence = build_sportmonks_availability_evidence(
                squad_rows=squad, sidelined_rows=[sidelined],
                sidelined_feed_available=True, team_id=10, season_id=2026,
                fixture_id=123, kickoff="2026-11-23",
            )
            self.assertIsNone(assess_player_availability(evidence)["score"])


    def test_missing_minutes_reports_available_statistic_type_ids(self):
        from player_availability import build_sportmonks_availability_evidence

        evidence = build_sportmonks_availability_evidence(
            squad_rows=[{
                "id": 1, "in_squad": True,
                "statistics": [{
                    "player_id": 1, "team_id": 10, "season_id": 2026,
                    "details": [
                        {"type_id": 52, "value": {"total": 2}},
                        {"type_id": 79, "value": {"total": 1}},
                    ],
                }],
            }],
            sidelined_rows=[], sidelined_feed_available=True,
            team_id=10, season_id=2026, fixture_id=123, kickoff="2026-11-23",
        )
        self.assertIsNone(assess_player_availability(evidence)["score"])
        self.assertEqual(evidence["minutes_type_ids_seen"], [52, 79])
        self.assertEqual(evidence["players_missing_minutes_detail"][0]["detail_type_ids"], [52, 79])


    def test_missing_minutes_diagnostic_captures_appearance_and_bench_values(self):
        from player_availability import build_sportmonks_availability_evidence

        evidence = build_sportmonks_availability_evidence(
            squad_rows=[{
                "id": 1, "in_squad": True,
                "statistics": [{
                    "player_id": 1, "team_id": 10, "season_id": 2026,
                    "details": [
                        {"type_id": 323, "value": {"total": 4}},
                    ],
                }],
            }],
            sidelined_rows=[], sidelined_feed_available=True,
            team_id=10, season_id=2026, fixture_id=123, kickoff="2026-11-23",
        )
        self.assertIsNone(assess_player_availability(evidence)["score"])
        self.assertEqual(evidence["player_statistic_values"], [
            {"player_id": 1, "type_id": 323, "value": {"total": 4}}
        ])


    def test_squad_flag_distribution_reports_former_or_youth_players(self):
        from player_availability import build_sportmonks_availability_evidence

        evidence = build_sportmonks_availability_evidence(
            squad_rows=[
                {"id": 1, "in_squad": True, "statistics": []},
                {"id": 2, "in_squad": False, "name": "Former Player"},
            ],
            sidelined_rows=[], sidelined_feed_available=True,
            team_id=10, season_id=2026, fixture_id=123, kickoff="2026-11-23",
        )
        self.assertEqual(evidence["current_squad_rows_seen"], 1)
        self.assertEqual(evidence["not_current_squad_rows_seen"], 1)
        self.assertEqual(evidence["not_current_squad_players"][0]["player_name"], "Former Player")


    def test_season_statistics_coverage_is_counted_for_entire_current_squad(self):
        from player_availability import build_sportmonks_availability_evidence

        evidence = build_sportmonks_availability_evidence(
            squad_rows=[
                {"id": 1, "in_squad": True, "name": "Player With Stats",
                 "statistics": [{"player_id": 1, "team_id": 10, "season_id": 2026,
                    "details": [{"type_id": 119, "value": {"total": 900}}]}]},
                {"id": 2, "in_squad": True, "name": "Player Without Stats",
                 "statistics": []},
            ],
            sidelined_rows=[], sidelined_feed_available=True,
            team_id=10, season_id=2026, fixture_id=123, kickoff="2026-11-23",
        )
        self.assertEqual(evidence["current_squad_rows_seen"], 2)
        self.assertEqual(evidence["matching_team_season_statistics_rows"], 1)
        self.assertEqual(evidence["players_without_season_statistics"][0]["player_name"], "Player Without Stats")
        self.assertIsNone(assess_player_availability(evidence)["score"])


    def test_bench_only_player_without_playing_appearances_has_zero_minutes(self):
        from player_availability import build_sportmonks_availability_evidence

        evidence = build_sportmonks_availability_evidence(
            squad_rows=[
                {"id": 1, "in_squad": True, "statistics": [{
                    "player_id": 1, "team_id": 10, "season_id": 2026,
                    "details": [{"type_id": 119, "value": {"total": 900}}],
                }]},
                {"id": 2, "in_squad": True, "statistics": [{
                    "player_id": 2, "team_id": 10, "season_id": 2026,
                    "details": [{"type_id": 323, "value": {"total": 3}}],
                }]},
            ],
            sidelined_rows=[], sidelined_feed_available=True,
            team_id=10, season_id=2026, fixture_id=123, kickoff="2026-11-23",
        )
        self.assertTrue(evidence["roster_complete"])
        self.assertEqual(assess_player_availability(evidence)["score"], 100.0)
        zero_player = next(p for p in evidence["squad_players"] if p["player_id"] == 2)
        self.assertEqual(zero_player["minutes_played"], 0.0)
        self.assertEqual(zero_player["importance"], 0.0)
        self.assertEqual(zero_player["minutes_evidence_method"], "bench_appearances_without_playing_appearances")

    def test_unavailable_bench_only_player_has_zero_importance(self):
        from player_availability import build_sportmonks_availability_evidence

        evidence = build_sportmonks_availability_evidence(
            squad_rows=[
                {"id": 1, "in_squad": True, "statistics": [{
                    "player_id": 1, "team_id": 10, "season_id": 2026,
                    "details": [{"type_id": 119, "value": {"total": 900}}],
                }]},
                {"id": 2, "in_squad": True, "statistics": [{
                    "player_id": 2, "team_id": 10, "season_id": 2026,
                    "details": [{"type_id": 323, "value": {"total": 3}}],
                }]},
            ],
            sidelined_rows=[{
                "player_id": 2, "team_id": 10, "completed": False,
                "start_date": "2026-11-01", "end_date": None,
            }],
            sidelined_feed_available=True,
            team_id=10, season_id=2026, fixture_id=123, kickoff="2026-11-23",
        )
        self.assertEqual(assess_player_availability(evidence)["score"], 100.0)

    def test_missing_minutes_with_positive_appearances_stays_unknown(self):
        from player_availability import build_sportmonks_availability_evidence

        evidence = build_sportmonks_availability_evidence(
            squad_rows=[{
                "id": 1, "in_squad": True,
                "statistics": [{
                    "player_id": 1, "team_id": 10, "season_id": 2026,
                    "details": [{"type_id": 321, "value": {"total": 2}}],
                }],
            }],
            sidelined_rows=[], sidelined_feed_available=True,
            team_id=10, season_id=2026, fixture_id=123, kickoff="2026-11-23",
        )
        self.assertIsNone(assess_player_availability(evidence)["score"])


    def test_explicit_has_values_false_is_zero_minutes_evidence(self):
        from player_availability import build_sportmonks_availability_evidence

        evidence = build_sportmonks_availability_evidence(
            squad_rows=[
                {"id": 1, "in_squad": True, "statistics": [{
                    "player_id": 1, "team_id": 10, "season_id": 2026,
                    "details": [{"type_id": 119, "value": {"total": 900}}],
                }]},
                {"id": 2, "in_squad": True, "statistics": [{
                    "player_id": 2, "team_id": 10, "season_id": 2026,
                    "has_values": False,
                }]},
            ],
            sidelined_rows=[], sidelined_feed_available=True,
            team_id=10, season_id=2026, fixture_id=123, kickoff="2026-11-23",
        )
        self.assertTrue(evidence["roster_complete"])
        zero_player = next(p for p in evidence["squad_players"] if p["player_id"] == 2)
        self.assertEqual(zero_player["minutes_played"], 0.0)
        self.assertEqual(zero_player["importance"], 0.0)
        self.assertEqual(
            zero_player["minutes_evidence_method"],
            "sportmonks_has_values_false_no_season_statistics",
        )


    def test_squad_diagnostic_report_uses_final_evidence_and_assessment(self):
        from player_availability import build_squad_fetch_diagnostics

        result = build_squad_fetch_diagnostics(
            {"status": "retrieved", "rows_returned": 30, "roster_complete": False,
             "reason": "stale reason"},
            {"roster_complete": True, "current_squad_rows_seen": 29,
             "players_assessed": 29, "reason": "verified complete roster"},
            {"score": 100.0, "status": "scored"},
        )
        self.assertTrue(result["roster_complete"])
        self.assertEqual(result["current_squad_players"], 29)
        self.assertEqual(result["players_assessed"], 29)
        self.assertEqual(result["reason"], "verified complete roster")
        self.assertEqual(result["availability_score"], 100.0)
        self.assertEqual(result["availability_status"], "scored")
        self.assertEqual(result["rows_returned"], 30)



if __name__ == "__main__":
    unittest.main()
