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


if __name__ == "__main__":
    unittest.main()
