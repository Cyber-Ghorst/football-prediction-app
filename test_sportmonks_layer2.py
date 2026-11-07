import unittest

from sportmonks_layer2 import collect_sportmonks_team_profile, standings_strength


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
            {"participant_id": home_id, "type": {"id": 1, "name": "Ball Possession"}, "data": {"value": "60%"}},
            {"participant_id": away_id, "type": {"id": 1, "name": "Ball Possession"}, "data": {"value": "40%"}},
            {"participant_id": home_id, "type": {"id": 2, "name": "Pass Accuracy"}, "data": {"value": 0.82}},
            {"participant_id": away_id, "type": {"id": 2, "name": "Pass Accuracy"}, "data": {"value": 0.71}},
            {"participant_id": home_id, "type": {"id": 3, "name": "Total Shots"}, "data": {"value": 12}},
            {"participant_id": away_id, "type": {"id": 3, "name": "Total Shots"}, "data": {"value": 8}},
            {"participant_id": home_id, "type": {"id": 4, "name": "Shots Accuracy"}, "data": {"value": 0.5}},
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
        self.assertEqual(profile["matches"][0]["statistics"]["Passes %"], 82.0)
        self.assertEqual(profile["matches"][0]["statistics"]["Total Shots"], 12.0)
        self.assertNotIn("Shots Accuracy", profile["matches"][0]["statistics"])
        self.assertEqual(profile["matches"][0]["statistics_provenance"][0]["provider"], "sportmonks")
        self.assertEqual(profile["matches"][0]["statistics_provenance"][0]["fixture_id"], 6)
        self.assertIsNone(profile["player_availability"])

    def test_statistics_are_team_specific(self):
        row = fixture(1, 10, 20, 1, 0)
        profile = collect_sportmonks_team_profile({"id": 10, "name": "Home FC"}, 2026, [row], [])
        stats = profile["matches"][0]["statistics"]
        self.assertEqual(stats["Ball Possession"], 60.0)
        self.assertNotEqual(stats["Ball Possession"], 40.0)

    def test_profile_exposes_history_filter_diagnostics(self):
        valid = fixture(1, 10, 20, 1, 0)
        wrong_season = fixture(2, 10, 20, 1, 0)
        wrong_season["season_id"] = 2025
        missing_score = fixture(3, 10, 20, 1, 0)
        missing_score["scores"] = []
        not_finished = fixture(4, 10, 20, 1, 0, state="NS")
        other_team = fixture(5, 30, 40, 1, 0)
        missing_participants = fixture(6, 10, 20, 1, 0)
        missing_participants["participants"] = []

        profile = collect_sportmonks_team_profile(
            {"id": 10, "name": "Home FC"}, 2026,
            [valid, wrong_season, missing_score, not_finished, other_team, missing_participants], [],
        )
        quality = profile["data_quality"]
        self.assertEqual(quality["fixtures_scanned"], 6)
        self.assertEqual(quality["same_season_fixtures"], 5)
        self.assertEqual(quality["team_fixtures"], 3)
        self.assertEqual(quality["completed_fixtures"], 2)
        self.assertEqual(quality["fixtures_with_valid_scores"], 1)
        self.assertEqual(quality["matches_returned"], 1)
        self.assertEqual(quality["excluded_wrong_season"], 1)
        self.assertEqual(quality["excluded_missing_participants"], 1)
        self.assertEqual(quality["excluded_other_team"], 1)
        self.assertEqual(quality["excluded_not_completed"], 1)
        self.assertEqual(quality["excluded_missing_scores"], 1)
        self.assertEqual(quality["history_shortfall"], 9)

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


    def test_upcoming_fixture_accepts_state_id_and_iso_kickoff_without_epoch(self):
        from datetime import datetime, timezone
        from sportmonks_layer2 import diagnose_upcoming_match_fixture

        row = fixture(30, 10, 20, 0, 0, state="unknown")
        row["state_id"] = 1
        row["state"] = {}
        row.pop("starting_at_timestamp", None)
        row["starting_at"] = "2026-11-08T15:00:00Z"

        now = int(datetime(2026, 11, 7, 12, tzinfo=timezone.utc).timestamp())
        diagnostic = diagnose_upcoming_match_fixture([row], 10, 20, 2026, now_timestamp=now)

        self.assertTrue(diagnostic["verified"])
        self.assertEqual(diagnostic["fixture"]["id"], 30)
        self.assertEqual(diagnostic["same_season"], 1)
        self.assertEqual(diagnostic["scheduled"], 1)
        self.assertEqual(diagnostic["exact_home_away"], 1)
        self.assertEqual(diagnostic["future_kickoff"], 1)

    def test_upcoming_fixture_accepts_string_state_and_reports_missing_kickoff(self):
        from datetime import datetime, timezone
        from sportmonks_layer2 import diagnose_upcoming_match_fixture

        row = fixture(31, 10, 20, 0, 0, state="unknown")
        row["state"] = "NS"
        row["state_id"] = None
        row.pop("starting_at_timestamp", None)
        row["starting_at"] = "not-a-date"

        now = int(datetime(2026, 11, 7, tzinfo=timezone.utc).timestamp())
        diagnostic = diagnose_upcoming_match_fixture([row], 10, 20, 2026, now_timestamp=now)

        self.assertFalse(diagnostic["verified"])
        self.assertEqual(diagnostic["exact_home_away"], 1)
        self.assertEqual(diagnostic["missing_kickoff"], 1)
        self.assertIn("kickoff timestamp could not be parsed", diagnostic["reason"])


if __name__ == "__main__":
    unittest.main()
