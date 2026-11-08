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


if __name__ == "__main__":
    unittest.main()
