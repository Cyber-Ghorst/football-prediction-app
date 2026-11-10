import unittest

from canonical_data import canonicalize_api_ninjas_match, match_identity
from sportmonks_canonical import canonicalize_sportmonks_fixture


class SportmonksCanonicalTests(unittest.TestCase):
    def fixture(self):
        return {
            "id": 12345, "season_id": 987, "starting_at": "2026-11-07T15:00:00Z",
            "state_id": 5, "participants": [
                {"id": 100, "name": "Arsenal", "meta": {"location": "home"}},
                {"id": 200, "name": "Chelsea", "meta": {"location": "away"}},
            ],
            "scores": [
                {"participant_id": 100, "description": "CURRENT", "score": {"goals": 2}},
                {"participant_id": 200, "description": "CURRENT", "score": {"goals": 1}},
            ],
        }

    def test_normalizes_participants_state_and_current_scores(self):
        result = canonicalize_sportmonks_fixture(
            self.fixture(), competition_key="eng-premier-league", season=2026
        )
        self.assertEqual(result["status"], "finished")
        self.assertEqual((result["home_score"], result["away_score"]), (2, 1))
        self.assertEqual(result["source_ids"]["sportmonks"], "12345")

    def test_period_scores_are_not_used_when_current_scores_are_missing(self):
        row = self.fixture()
        row["scores"] = [
            {"participant_id": 100, "description": "1ST_HALF", "score": {"goals": 1}},
            {"participant_id": 100, "description": "2ND_HALF", "score": {"goals": 2}},
            {"participant_id": 200, "description": "1ST_HALF", "score": {"goals": 0}},
            {"participant_id": 200, "description": "2ND_HALF", "score": {"goals": 1}},
        ]
        result = canonicalize_sportmonks_fixture(
            row, competition_key="eng-premier-league", season=2026
        )
        self.assertIsNone(result["home_score"])
        self.assertIsNone(result["away_score"])

    def test_current_scores_reject_boolean_fractional_and_negative_values(self):
        for invalid in (True, 1.5, -1, "1.5", "-1"):
            with self.subTest(invalid=invalid):
                row = self.fixture()
                row["scores"][0]["score"]["goals"] = invalid
                result = canonicalize_sportmonks_fixture(
                    row, competition_key="eng-premier-league", season=2026
                )
                self.assertIsNone(result["home_score"])
                self.assertEqual(result["away_score"], 1)

    def test_conflicting_duplicate_current_scores_are_unknown(self):
        row = self.fixture()
        row["scores"].append({
            "participant_id": 100, "description": "CURRENT",
            "score": {"goals": 3},
        })
        result = canonicalize_sportmonks_fixture(
            row, competition_key="eng-premier-league", season=2026
        )
        self.assertIsNone(result["home_score"])
        self.assertEqual(result["away_score"], 1)

    def test_identity_matches_other_provider_without_comparing_ids(self):
        sm = canonicalize_sportmonks_fixture(
            self.fixture(), competition_key="eng-premier-league", season=2026
        )
        ninjas = canonicalize_api_ninjas_match({
            "game_id": "ninjas-123", "season": 2026,
            "start_time": "2026-11-07T15:02:00Z", "status": "final",
            "home_team": {"team_id": "ars", "name": "Arsenal"},
            "away_team": {"team_id": "che", "name": "Chelsea"},
            "home_score": 2, "away_score": 1,
        }, competition_key="eng-premier-league")
        self.assertTrue(match_identity(sm, ninjas))
        self.assertNotEqual(sm["source_ids"]["sportmonks"], ninjas["source_ids"]["api_ninjas"])

    def test_state_ids_without_expanded_state_are_normalized(self):
        for state_id, expected in (
            (1, "scheduled"),
            (2, "live"), (3, "live"), (4, "live"), (6, "live"),
            (9, "live"), (21, "live"), (22, "live"), (25, "live"),
            (5, "finished"), (7, "finished"), (8, "finished"),
        ):
            with self.subTest(state_id=state_id):
                row = self.fixture()
                row["state_id"] = state_id
                row["state"] = {}
                result = canonicalize_sportmonks_fixture(
                    row, competition_key="eng-premier-league", season=2026
                )
                self.assertEqual(result["status"], expected)

    def test_status_labels_require_exact_finished_state(self):
        for label, expected in (
            ("Finished", "finished"),
            ("Full Time", "finished"),
            ("AET", "finished"),
            ("after penalties", "finished"),
            ("Penalties", "live"),
            ("Penalty Shootout", "live"),
            ("1st Half", "live"),
            ("not live", "unknown"),
            ("not in play", "unknown"),
            ("NS", "scheduled"),
            ("unfinished", "unknown"),
            ("not finished", "unknown"),
            ("pre-finished", "unknown"),
        ):
            with self.subTest(label=label):
                row = self.fixture()
                row["state_id"] = None
                row["state"] = {"name": label}
                result = canonicalize_sportmonks_fixture(
                    row, competition_key="eng-premier-league", season=2026
                )
                self.assertEqual(result["status"], expected)

    def test_missing_participant_or_kickoff_fails_closed(self):
        bad = self.fixture()
        bad["participants"] = bad["participants"][:1]
        with self.assertRaises(ValueError):
            canonicalize_sportmonks_fixture(bad, competition_key="eng-premier-league", season=2026)


if __name__ == "__main__":
    unittest.main()
