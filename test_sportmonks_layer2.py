import unittest

from sportmonks_layer2 import collect_sportmonks_team_profile, standings_strength, find_exact_match_fixture


def fixture(fid, home_id, away_id, home_goals, away_goals, state="FT"):
    return {
        "id": fid,
        "season_id": 2026,
        "starting_at": f"2026-10-{fid:02d} 15:00:00",
        "updated_at": "2026-10-20T10:00:00Z",
        "state": {"short_name": state, "name": "Finished"},
        "participants": [
            {"id": home_id, "name": f"Team {home_id}", "meta": {"location": "home"}},
            {"id": away_id, "name": f"Team {away_id}", "meta": {"location": "away"}},
        ],
        "scores": [
            {"participant_id": home_id, "description": "CURRENT", "score": {"goals": home_goals}},
            {"participant_id": away_id, "description": "CURRENT", "score": {"goals": away_goals}},
        ],
        "statistics": [
            {"participant_id": home_id, "type": {"id": 1, "name": "Ball Possession %"}, "data": {"value": "60%"}},
            {"participant_id": away_id, "type": {"id": 1, "name": "Ball Possession"}, "data": {"value": "40%"}},
            {"participant_id": home_id, "type": {"id": 2, "name": "Pass Accuracy"}, "data": {"value": 0.82}},
            {"participant_id": away_id, "type": {"id": 2, "name": "Pass Accuracy"}, "data": {"value": 0.71}},
            {"participant_id": home_id, "type": {"id": 3, "name": "Total Shots"}, "data": {"value": 12}},
            {"participant_id": away_id, "type": {"id": 3, "name": "Total Shots"}, "data": {"value": 8}},
            {"participant_id": home_id, "type": {"id": 4, "name": "Shots Accuracy"}, "data": {"value": 0.5}},
            {"participant_id": home_id, "type": {"id": 42, "name": "Shots Total"}, "data": {"value": 14}},
            {"participant_id": home_id, "type": {"id": 58, "name": "Shots Blocked"}, "data": {"value": 3}},
            {"participant_id": home_id, "type": {"id": 99, "name": "Successful Passes Percentage"}, "data": {"value": 0.84}},
            {"participant_id": home_id, "type": {"id": 43, "name": "Attacks"}, "data": {"value": 85}},
            {"participant_id": home_id, "type": {"id": 100, "name": "Passes"}, "data": {"value": 300}},
            {"participant_id": home_id, "type": {"id": 101, "name": "Big Chances Created"}, "data": {"value": 4}},
        ],
    }


class SportmonksLayer2Tests(unittest.TestCase):
    def test_standings_strength_uses_only_known_positions(self):
        result = standings_strength([
            {"participant_id": 10, "position": 1},
            {"participant_id": 20, "position": 4},
            {"participant_id": 30, "position": None},
        ])
        self.assertEqual(result, {10: 100.0, 20: 25.0})

    def test_profile_uses_completed_fixtures_and_team_identity(self):
        fixtures = [fixture(i, 10, 20, 2, 1) for i in range(1, 7)]
        fixtures.append(fixture(7, 10, 20, 1, 0, state="NS"))
        profile = collect_sportmonks_team_profile(
            {"id": 10, "name": "Home FC"},
            2026,
            fixtures,
            [{"participant_id": 10, "position": 1}, {"participant_id": 20, "position": 2}],
        )
        self.assertEqual(profile["data_quality"]["matches_returned"], 6)
        self.assertEqual(profile["matches"][0]["goals_for"], 2)
        self.assertEqual(profile["matches"][0]["opponent_strength"], 50.0)
        self.assertEqual(profile["matches"][0]["statistics"]["Ball Possession"], 60.0)
        self.assertEqual(profile["matches"][0]["statistics"]["Total Shots"], 14.0)
        self.assertEqual(profile["matches"][0]["statistics"]["Blocked Shots"], 3.0)
        self.assertEqual(profile["matches"][0]["statistics"]["Passes %"], 84.0)
        self.assertEqual(profile["matches"][0]["statistics"]["Big Chances Created"], 4.0)
        self.assertNotIn("Shots Accuracy", profile["matches"][0]["statistics"])
        self.assertNotIn("Attacks", profile["matches"][0]["statistics"])
        self.assertNotIn("Passes", profile["matches"][0]["statistics"])
        self.assertNotIn("Attacks", profile["matches"][0]["statistics"])
        raw_rows = profile["matches"][0]["statistics_raw_diagnostics"]
        shots_accuracy = next(row for row in raw_rows if row["statistic_name_raw"] == "Shots Accuracy")
        self.assertEqual(shots_accuracy["mapping_status"], "unmapped")
        self.assertEqual(shots_accuracy["raw_value"], 0.5)
        self.assertEqual(profile["matches"][0]["statistics_provenance"][0]["provider"], "sportmonks")
        self.assertEqual(profile["matches"][0]["statistics_provenance"][0]["fixture_id"], 6)
        self.assertIsNone(profile["player_availability"])

    def test_history_collection_diagnostics_explain_fixture_exclusions(self):
        valid = fixture(1, 10, 20, 2, 1)
        wrong_season = fixture(2, 10, 20, 1, 0)
        wrong_season["season_id"] = 2025
        missing_participants = {"id": 3, "season_id": 2026, "participants": []}
        other_team = fixture(4, 30, 40, 1, 0)
        not_completed = fixture(5, 10, 20, 0, 0, state="NS")
        missing_scores = fixture(6, 10, 20, 1, 0)
        missing_scores["scores"] = []
        missing_season_id = fixture(7, 10, 20, 3, 2)
        missing_season_id.pop("season_id")

        profile = collect_sportmonks_team_profile(
            {"id": 10, "name": "Home FC"},
            2026,
            [valid, wrong_season, missing_participants, other_team,
             not_completed, missing_scores, missing_season_id],
            [],
        )
        report = profile["history_collection_diagnostics"]
        self.assertEqual(report["fixtures_scanned"], 7)
        self.assertEqual(report["same_season_fixtures"], 5)
        self.assertEqual(report["season_eligible_fixtures"], 6)
        self.assertEqual(report["fixtures_missing_season_id"], 1)
        self.assertEqual(report["team_fixtures"], 4)
        self.assertEqual(report["completed_fixtures"], 3)
        self.assertEqual(report["fixtures_with_valid_scores"], 2)
        self.assertEqual(report["excluded_wrong_season"], 1)
        self.assertEqual(report["excluded_missing_participants"], 1)
        self.assertEqual(report["excluded_other_team"], 1)
        self.assertEqual(report["excluded_not_completed"], 1)
        self.assertEqual(report["excluded_missing_scores"], 1)

    def test_statistics_are_team_specific(self):
        row = fixture(1, 10, 20, 1, 0)
        profile = collect_sportmonks_team_profile({"id": 10, "name": "Home FC"}, 2026, [row], [])
        stats = profile["matches"][0]["statistics"]
        self.assertEqual(stats["Ball Possession"], 60.0)
        self.assertNotEqual(stats["Ball Possession"], 40.0)

    def test_wrong_season_fixture_is_excluded(self):
        row = fixture(1, 10, 20, 1, 0)
        row["season_id"] = 999
        profile = collect_sportmonks_team_profile({"id": 10, "name": "Home FC"}, 2026, [row], [])
        self.assertEqual(profile["matches"], [])

    def test_documented_finished_state_id_is_accepted(self):
        row = fixture(1, 10, 20, 1, 0, state="unknown")
        row["state_id"] = 5
        row["state"] = {}
        profile = collect_sportmonks_team_profile({"id": 10, "name": "Home FC"}, 2026, [row], [])
        self.assertEqual(profile["data_quality"]["matches_returned"], 1)

    def test_missing_score_or_participant_is_not_fabricated(self):
        row = fixture(1, 10, 20, 1, 0)
        row["scores"] = []
        profile = collect_sportmonks_team_profile({"id": 10, "name": "Home FC"}, 2026, [row], [])
        self.assertEqual(profile["matches"], [])
        self.assertIsNone(profile["home_rating"])

    def test_find_upcoming_fixture_requires_exact_home_away_and_season(self):
        from datetime import datetime, timezone
        from sportmonks_layer2 import find_upcoming_match_fixture

        row = fixture(20, 10, 20, 0, 0, state="NS")
        row["starting_at_timestamp"] = int(datetime(2026, 11, 8, tzinfo=timezone.utc).timestamp())
        wrong_orientation = fixture(21, 20, 10, 0, 0, state="NS")
        wrong_orientation["starting_at_timestamp"] = row["starting_at_timestamp"] + 60
        wrong_season = fixture(22, 10, 20, 0, 0, state="NS")
        wrong_season["season_id"] = 2025
        wrong_season["starting_at_timestamp"] = row["starting_at_timestamp"] + 120

        found = find_upcoming_match_fixture(
            [wrong_orientation, wrong_season, row], 10, 20, 2026,
            now_timestamp=int(datetime(2026, 11, 7, tzinfo=timezone.utc).timestamp()),
        )
        self.assertEqual(found["id"], 20)

    def test_find_exact_fixture_accepts_live_or_past_pair_but_requires_exact_orientation_and_season(self):
        from datetime import datetime, timezone
        now = int(datetime(2026, 11, 8, 16, tzinfo=timezone.utc).timestamp())
        live = fixture(20, 10, 20, 0, 0, state="LIVE")
        live["starting_at_timestamp"] = now - 1800
        wrong_orientation = fixture(21, 20, 10, 0, 0, state="LIVE")
        wrong_orientation["starting_at_timestamp"] = now - 900
        wrong_season = fixture(22, 10, 20, 0, 0, state="LIVE")
        wrong_season["season_id"] = 2025
        wrong_season["starting_at_timestamp"] = now - 600
        found = find_exact_match_fixture(
            [wrong_orientation, wrong_season, live], 10, 20, 2026,
            now_timestamp=now,
        )
        self.assertEqual(found["id"], 20)

    def test_exact_fixture_lookup_prefers_upcoming_pair_over_previous_meeting(self):
        from datetime import datetime, timezone
        now = int(datetime(2026, 11, 8, 16, tzinfo=timezone.utc).timestamp())
        previous = fixture(30, 10, 20, 1, 0, state="FT")
        previous["starting_at_timestamp"] = now - 86400
        upcoming = fixture(31, 10, 20, 0, 0, state="NS")
        upcoming["starting_at_timestamp"] = now + 86400
        found = find_exact_match_fixture(
            [previous, upcoming], 10, 20, 2026, now_timestamp=now
        )
        self.assertEqual(found["id"], 31)

    def test_extract_match_details_keeps_sidelined_and_lineup_status_unknown(self):
        from sportmonks_layer2 import extract_sportmonks_match_details

        row = fixture(20, 10, 20, 0, 0, state="NS")
        row["lineups"] = [
            {"team_id": 10, "player_id": 101, "player_name": "Home Player",
             "jersey_number": 9, "type": {"name": "Starting XI"}},
            {"team_id": 20, "player_id": 201, "player_name": "Away Player",
             "jersey_number": 1, "type": {"name": "Starting XI"}},
        ]
        row["formations"] = [
            {"participant_id": 10, "formation": "4-3-3"},
            {"participant_id": 20, "formation": "4-4-2"},
        ]
        row["sidelined"] = [
            {"participant_id": 10, "player_id": 102,
             "player": {"id": 102, "name": "Unavailable Player"},
             "type": {"name": "Injury"},
             "sideline": {"category": "Hamstring", "start_date": "2026-11-01", "end_date": None}},
        ]

        details = extract_sportmonks_match_details(row, 10, 20, 2026)
        self.assertEqual(details["teams"]["home"]["formation"], "4-3-3")
        self.assertTrue(details["teams"]["home"]["lineups_available"])
        self.assertEqual(details["teams"]["home"]["confirmation_status"], "unknown")
        self.assertEqual(details["availability"]["home"]["reported_unavailable_count"], 1)
        self.assertEqual(details["availability"]["home"]["reported_sidelined"][0]["player_name"], "Unavailable Player")
        self.assertIsNone(details["availability"]["home"]["player_availability"])

    def test_extract_match_details_rejects_wrong_match_identity(self):
        from sportmonks_layer2 import extract_sportmonks_match_details

        row = fixture(20, 10, 20, 0, 0, state="NS")
        with self.assertRaises(ValueError):
            extract_sportmonks_match_details(row, 20, 10, 2026)


if __name__ == "__main__":
    unittest.main()
