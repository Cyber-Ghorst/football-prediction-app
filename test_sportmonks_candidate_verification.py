import unittest

from sportmonks_candidate_verification import verify_highlightly_candidate


def sm_fixture(fid=1, season_id=2026, league_id=8, home_id=10, away_id=20,
               kickoff="2026-10-24 14:00:00", state_id=5, home_goals=0, away_goals=1):
    return {
        "id": fid, "season_id": season_id, "league_id": league_id,
        "starting_at": kickoff, "state_id": state_id,
        "participants": [
            {"id": home_id, "name": "Coventry", "meta": {"location": "home"}},
            {"id": away_id, "name": "Fulham", "meta": {"location": "away"}},
        ],
        "scores": [
            {"participant_id": home_id, "description": "CURRENT", "score": {"goals": home_goals}},
            {"participant_id": away_id, "description": "CURRENT", "score": {"goals": away_goals}},
        ],
    }


class HighlightlyCandidateVerificationTests(unittest.TestCase):
    def setUp(self):
        self.candidate = {
            "kickoff_utc": "2026-10-24T14:00:00+00:00",
            "home": "Coventry", "away": "Fulham", "score": [0, 1],
            "highlightly_match_id": "1325382224",
        }
        self.identity = {
            "season_id": 2026, "league_id": 8,
            "home_team_id": 10, "away_team_id": 20,
        }

    def test_exact_completed_fixture_and_score_agree(self):
        result = verify_highlightly_candidate(self.candidate, [sm_fixture()], **self.identity)
        self.assertEqual(result["verification_status"], "exact_fixture_and_score_agree")
        self.assertEqual(result["exact_completed_score_valid_fixtures"], 1)
        self.assertTrue(result["candidate_score_agreement"])

    def test_score_conflict_is_reported_not_hidden(self):
        result = verify_highlightly_candidate(
            self.candidate, [sm_fixture(home_goals=1, away_goals=1)], **self.identity
        )
        self.assertEqual(result["verification_status"], "exact_fixture_found_score_disagrees")
        self.assertFalse(result["candidate_score_agreement"])

    def test_wrong_season_is_not_accepted(self):
        result = verify_highlightly_candidate(
            self.candidate, [sm_fixture(season_id=2025)], **self.identity
        )
        self.assertEqual(result["verification_status"], "no_same_season_competition_fixture_returned_for_date")
        self.assertEqual(result["same_season_and_competition_fixtures"], 0)

    def test_wrong_home_away_orientation_is_not_accepted(self):
        result = verify_highlightly_candidate(
            self.candidate, [sm_fixture(home_id=20, away_id=10)], **self.identity
        )
        self.assertEqual(result["verification_status"], "same_season_competition_found_but_exact_team_pair_not_found")
        self.assertEqual(result["exact_home_away_team_fixtures"], 0)

    def test_kickoff_mismatch_is_reported(self):
        result = verify_highlightly_candidate(
            self.candidate, [sm_fixture(kickoff="2026-10-24 15:00:00")], **self.identity
        )
        self.assertEqual(result["verification_status"], "same_teams_found_but_kickoff_differs")
        self.assertEqual(result["exact_kickoff_fixtures"], 0)

    def test_unresolved_team_mapping_stays_unverified(self):
        result = verify_highlightly_candidate(
            self.candidate, [sm_fixture()], season_id=2026, league_id=8,
            home_team_id=None, away_team_id=20,
        )
        self.assertEqual(result["verification_status"], "unresolved_exact_team_mapping")


if __name__ == "__main__":
    unittest.main()
