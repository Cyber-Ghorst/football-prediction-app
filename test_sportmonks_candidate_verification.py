import unittest

from sportmonks_candidate_verification import (
    apply_verified_result_candidates_to_profiles,
    verify_highlightly_candidate,
)


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

    def test_fixtures_for_utc_date_uses_utc_calendar_day(self):
        from sportmonks_candidate_verification import fixtures_for_utc_date

        fixtures = [
            {"id": 1, "starting_at": "2026-09-19T16:30:00+00:00"},
            {"id": 2, "starting_at": "2026-09-20T00:30:00+08:00"},
            {"id": 3, "starting_at": "2026-09-20T01:00:00+00:00"},
        ]
        result = fixtures_for_utc_date(fixtures, "2026-09-19")
        self.assertEqual([row["id"] for row in result], [1, 2])

    def test_finished_state_labels_do_not_match_substrings(self):
        from sportmonks_candidate_verification import _finished

        for label, expected in (
            ("Finished", True),
            ("Full Time", True),
            ("AET", True),
            ("after penalties", True),
            ("Penalties", False),
            ("Penalty Shootout", False),
            ("unfinished", False),
            ("not finished", False),
            ("pre-finished", False),
        ):
            with self.subTest(label=label):
                self.assertEqual(_finished({"state_id": None, "state": {"name": label}}), expected)

    def test_exact_highlightly_corroborated_sportmonks_result_updates_recent_history(self):
        verified = verify_highlightly_candidate(self.candidate, [sm_fixture()], **self.identity)
        verified["verification_completed_at"] = "2026-10-24T14:05:00Z"
        verified["verification_source"] = "targeted_date_endpoint"
        home = {
            "id": 10, "name": "Coventry", "matches": [],
            "tactical_evidence": {"source": "existing_primary_only"},
        }
        away = {
            "id": 20, "name": "Fulham", "matches": [],
            "tactical_evidence": {"source": "existing_primary_only"},
        }

        result = apply_verified_result_candidates_to_profiles(
            [home, away], [verified], expected_season_id=2026
        )

        self.assertEqual(result["matches_added"], 2)
        self.assertEqual(home["matches"][0]["goals_for"], 0)
        self.assertEqual(home["matches"][0]["goals_against"], 1)
        self.assertEqual(home["matches"][0]["venue"], "home")
        self.assertEqual(away["matches"][0]["goals_for"], 1)
        self.assertEqual(away["matches"][0]["goals_against"], 0)
        self.assertEqual(away["matches"][0]["venue"], "away")
        self.assertEqual(home["matches"][0]["statistics"], {})
        self.assertEqual(
            home["matches"][0]["result_verification"]["corroborated_by"],
            "highlightly",
        )
        self.assertEqual(home["tactical_evidence"], {"source": "existing_primary_only"})
        self.assertEqual(
            home["data_quality"]["history_source"],
            "cockroachdb_central_repository_plus_verified_sportmonks_candidates",
        )
        self.assertEqual(
            home["history_collection_diagnostics"]["statistics_coverage_by_metric"]["Total Shots"],
            0,
        )
        self.assertFalse(home["verified_result_history_fallback"]["tactical_evidence_updated"])

    def test_api_ninjas_candidate_can_be_verified_and_used_as_corroboration(self):
        candidate = {
            "candidate_provider": "api_ninjas",
            "kickoff_utc": self.candidate["kickoff_utc"],
            "home": "Coventry",
            "away": "Fulham",
            "score": [0, 1],
            "api_ninjas_match_id": "ninja-555",
        }
        verified = verify_highlightly_candidate(candidate, [sm_fixture()], **self.identity)
        verified["verification_completed_at"] = "2026-10-24T14:05:00Z"
        profile = {"id": 10, "name": "Coventry", "matches": []}

        result = apply_verified_result_candidates_to_profiles(
            [profile], [verified], expected_season_id=2026
        )

        self.assertEqual(result["matches_added"], 1)
        self.assertEqual(
            profile["matches"][0]["result_verification"]["corroborated_by"],
            "api_ninjas",
        )
        self.assertEqual(
            profile["matches"][0]["result_verification"]["external_match_id"],
            "ninja-555",
        )
        self.assertEqual(profile["matches"][0]["result_verification"]["candidate_provider"], "api_ninjas")


    def test_verified_result_fallback_rejects_mismatch_and_invalid_timestamp(self):
        verified = verify_highlightly_candidate(
            self.candidate, [sm_fixture(home_goals=1, away_goals=1)], **self.identity
        )
        verified["verification_completed_at"] = "2026-10-24T14:05:00Z"
        profiles = [{"id": 10, "name": "Coventry", "matches": []}]
        result = apply_verified_result_candidates_to_profiles(
            profiles, [verified], expected_season_id=2026
        )
        self.assertEqual(result["matches_added"], 0)
        self.assertEqual(profiles[0]["matches"], [])

        verified = verify_highlightly_candidate(self.candidate, [sm_fixture()], **self.identity)
        verified["verification_completed_at"] = "invalid"
        result = apply_verified_result_candidates_to_profiles(
            profiles, [verified], expected_season_id=2026
        )
        self.assertEqual(result["matches_added"], 0)
        self.assertEqual(profiles[0]["matches"], [])

    def test_verified_result_fallback_skips_duplicate_and_limits_recent_history(self):
        verified = verify_highlightly_candidate(self.candidate, [sm_fixture()], **self.identity)
        verified["verification_completed_at"] = "2026-10-24T14:05:00Z"
        existing = [
            {"fixture_id": index + 100, "date": f"2026-10-{23-index:02d}T14:00:00+00:00",
             "venue": "home", "goals_for": 1, "goals_against": 0,
             "statistics": {}, "opponent_statistics": {}}
            for index in range(10)
        ]
        profile = {"id": 10, "name": "Coventry", "matches": existing}
        duplicate = dict(verified)
        duplicate["sportmonks_candidates"] = [
            dict(verified["sportmonks_candidates"][0], fixture_id=100)
        ]
        result = apply_verified_result_candidates_to_profiles(
            [profile], [duplicate], expected_season_id=2026
        )
        self.assertEqual(result["matches_added"], 0)
        self.assertEqual(result["duplicates_skipped"], 1)
        self.assertEqual(len(profile["matches"]), 10)

        verified = verify_highlightly_candidate(self.candidate, [sm_fixture()], **self.identity)
        verified["verification_completed_at"] = "2026-10-24T14:05:00Z"
        profile = {"id": 10, "name": "Coventry", "matches": existing}
        result = apply_verified_result_candidates_to_profiles(
            [profile], [verified], expected_season_id=2026
        )
        self.assertEqual(result["matches_added"], 1)
        self.assertEqual(len(profile["matches"]), 10)
        self.assertEqual(profile["matches"][0]["fixture_id"], 1)
        self.assertNotIn(109, [match["fixture_id"] for match in profile["matches"]])


    def test_multiple_exact_sportmonks_fixtures_are_not_imported(self):
        fixtures = [sm_fixture(fid=1), sm_fixture(fid=2)]
        verified = verify_highlightly_candidate(self.candidate, fixtures, **self.identity)
        verified["verification_completed_at"] = "2026-10-24T14:05:00Z"
        profile = {"id": 10, "name": "Coventry", "matches": []}
        result = apply_verified_result_candidates_to_profiles(
            [profile], [verified], expected_season_id=2026
        )
        self.assertEqual(result["matches_added"], 0)
        self.assertEqual(result["ambiguous_candidates_skipped"], 1)
        self.assertEqual(profile["matches"], [])


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

    def test_period_scores_are_not_used_when_current_score_is_missing(self):
        fixture = sm_fixture()
        fixture["scores"] = [
            {"participant_id": 10, "description": "1ST_HALF", "score": {"goals": 0}},
            {"participant_id": 10, "description": "2ND_HALF", "score": {"goals": 0}},
            {"participant_id": 20, "description": "1ST_HALF", "score": {"goals": 1}},
            {"participant_id": 20, "description": "2ND_HALF", "score": {"goals": 0}},
        ]
        result = verify_highlightly_candidate(self.candidate, [fixture], **self.identity)
        self.assertEqual(result["verification_status"], "exact_fixture_found_but_not_completed_with_valid_scores")
        self.assertEqual(result["exact_completed_score_valid_fixtures"], 0)
        self.assertIsNone(result["sportmonks_candidates"][0]["score"][0])

    def test_candidate_verification_rejects_boolean_fractional_and_negative_scores(self):
        for invalid in (True, 1.5, -1, "1.5", "-1"):
            with self.subTest(invalid=invalid):
                fixture = sm_fixture(home_goals=invalid)
                result = verify_highlightly_candidate(self.candidate, [fixture], **self.identity)
                self.assertEqual(result["verification_status"], "exact_fixture_found_but_not_completed_with_valid_scores")
                self.assertFalse(result["sportmonks_candidates"][0]["score_valid"])

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

    def test_candidate_team_id_resolves_brighton_alias_to_exact_provider_name(self):
        from sportmonks_candidate_verification import resolve_candidate_team_id

        fixtures = [{
            "participants": [
                {"id": 78, "name": "Brighton & Hove Albion"},
                {"id": 117, "name": "Coventry City"},
            ]
        }]
        result = resolve_candidate_team_id("Brighton", fixtures)
        self.assertEqual(result["team_id"], 78)
        self.assertEqual(result["status"], "explicit_alias_resolved_from_date_fixtures")
        self.assertEqual(result["matched_provider_names"], ["Brighton & Hove Albion"])

    def test_candidate_team_id_resolves_leeds_alias_to_exact_provider_name(self):
        from sportmonks_candidate_verification import resolve_candidate_team_id

        fixtures = [{
            "participants": [
                {"id": 71, "name": "Leeds United"},
                {"id": 78, "name": "Brighton & Hove Albion"},
            ]
        }]
        result = resolve_candidate_team_id("Leeds", fixtures)
        self.assertEqual(result["team_id"], 71)
        self.assertEqual(result["status"], "explicit_alias_resolved_from_date_fixtures")
        self.assertEqual(result["matched_provider_names"], ["Leeds United"])

    def test_candidate_team_id_resolves_bournemouth_alias_to_exact_provider_name(self):
        from sportmonks_candidate_verification import resolve_candidate_team_id

        fixtures = [{
            "participants": [
                {"id": 52, "name": "AFC Bournemouth"},
                {"id": 3, "name": "Sunderland"},
            ]
        }]
        result = resolve_candidate_team_id("Bournemouth", fixtures)
        self.assertEqual(result["team_id"], 52)
        self.assertEqual(result["status"], "explicit_alias_resolved_from_date_fixtures")
        self.assertEqual(result["matched_provider_names"], ["AFC Bournemouth"])

    def test_candidate_team_id_resolves_tottenham_alias_to_exact_provider_name(self):
        from sportmonks_candidate_verification import resolve_candidate_team_id

        fixtures = [{
            "participants": [
                {"id": 6, "name": "Tottenham Hotspur"},
                {"id": 20, "name": "Newcastle United"},
            ]
        }]
        result = resolve_candidate_team_id("Tottenham", fixtures)
        self.assertEqual(result["team_id"], 6)
        self.assertEqual(result["status"], "explicit_alias_resolved_from_date_fixtures")
        self.assertEqual(result["matched_provider_names"], ["Tottenham Hotspur"])

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
