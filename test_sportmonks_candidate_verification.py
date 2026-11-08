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


    def test_candidate_team_id_resolves_from_date_fixture_participants(self):
        from sportmonks_candidate_verification import resolve_candidate_team_id

        fixtures = [sm_fixture(home_id=101, away_id=202)]
        result = resolve_candidate_team_id("Coventry", fixtures)
        self.assertEqual(result["team_id"], 101)
        self.assertEqual(result["status"], "exact_name_resolved_from_date_fixtures")
        self.assertEqual(result["matched_provider_names"], ["Coventry"])

    def test_candidate_team_id_does_not_use_fuzzy_names(self):
        from sportmonks_candidate_verification import resolve_candidate_team_id

        fixtures = [sm_fixture(home_id=101, away_id=202)]
        result = resolve_candidate_team_id("Coventry City", fixtures)
        self.assertIsNone(result["team_id"])
        self.assertEqual(result["status"], "team_name_not_found_in_date_fixtures")


    def test_candidate_team_id_resolves_coventry_alias_to_exact_provider_name(self):
        from sportmonks_candidate_verification import resolve_candidate_team_id

        fixtures = [{
            "participants": [
                {"id": 117, "name": "Coventry City"},
                {"id": 11, "name": "Fulham"},
            ]
        }]
        result = resolve_candidate_team_id("Coventry", fixtures)
        self.assertEqual(result["team_id"], 117)
        self.assertEqual(result["status"], "explicit_alias_resolved_from_date_fixtures")
        self.assertEqual(result["matched_provider_names"], ["Coventry City"])

    def test_candidate_team_id_resolves_ipswich_alias_to_exact_provider_name(self):
        from sportmonks_candidate_verification import resolve_candidate_team_id

        fixtures = [{
            "participants": [
                {"id": 116, "name": "Ipswich Town"},
                {"id": 11, "name": "Fulham"},
            ]
        }]
        result = resolve_candidate_team_id("Ipswich", fixtures)
        self.assertEqual(result["team_id"], 116)
        self.assertEqual(result["status"], "explicit_alias_resolved_from_date_fixtures")
        self.assertEqual(result["matched_provider_names"], ["Ipswich Town"])

    def test_alias_resolution_does_not_accept_unlisted_fuzzy_names(self):
        from sportmonks_candidate_verification import resolve_candidate_team_id

        fixtures = [{"participants": [{"id": 117, "name": "Coventry City FC"}]}]
        result = resolve_candidate_team_id("Coventry", fixtures)
        self.assertIsNone(result["team_id"])
        self.assertEqual(result["status"], "team_name_not_found_in_date_fixtures")

    def test_candidate_team_id_ambiguous_exact_name_stays_unresolved(self):
        from sportmonks_candidate_verification import resolve_candidate_team_id

        fixtures = [
            sm_fixture(fid=1, home_id=101, away_id=202),
            sm_fixture(fid=2, home_id=303, away_id=404),
        ]
        result = resolve_candidate_team_id("Coventry", fixtures)
        self.assertIsNone(result["team_id"])
        self.assertEqual(result["status"], "ambiguous_exact_team_name")

    def test_date_participant_catalog_exposes_exact_names_and_ids_for_review(self):
        result = verify_highlightly_candidate(
            self.candidate, [sm_fixture(home_id=101, away_id=202)], season_id=2026,
            league_id=8, home_team_id=None, away_team_id=202,
        )
        catalog = result["date_fixture_participant_catalog"]
        self.assertEqual(catalog[0]["team_id"], 101)
        self.assertEqual(catalog[0]["provider_names"], ["Coventry"])
        self.assertEqual(catalog[0]["fixture_ids"], [1])

    def test_unresolved_team_mapping_stays_unverified(self):
        result = verify_highlightly_candidate(
            self.candidate, [sm_fixture()], season_id=2026, league_id=8,
            home_team_id=None, away_team_id=20,
        )
        self.assertEqual(result["verification_status"], "unresolved_exact_team_mapping")


if __name__ == "__main__":
    unittest.main()
