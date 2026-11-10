import unittest
from unittest.mock import patch

from sportmonks_layer2 import collect_sportmonks_team_profile, standings_strength, find_exact_match_fixture, load_repository_season_snapshot


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
            {"participant_id": home_id, "type": {"id": 1527}, "data": {"value": 7}},
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

    def test_malformed_provider_ids_are_not_coerced_or_attributed(self):
        from sportmonks_layer2 import _fixture_statistics_index, _provider_id, _scores

        self.assertEqual(_provider_id(10), 10)
        self.assertEqual(_provider_id("10"), 10)
        for invalid in (True, False, 10.9, "10.9", 0, -1, None):
            with self.subTest(value=invalid):
                self.assertIsNone(_provider_id(invalid))

        row = fixture(1, 10, 20, 2, 1)
        row["scores"][0]["participant_id"] = 10.9
        for statistic in row["statistics"]:
            if statistic.get("participant_id") == 10:
                statistic["participant_id"] = 10.9
        row["statistics"][1]["participant_id"] = True
        self.assertEqual(_scores(row, 10, 20), (None, 1))
        indexed = _fixture_statistics_index(row)
        self.assertNotIn(10, indexed)
        self.assertNotIn(1, indexed)

    def test_fractional_participant_ids_do_not_enter_team_history(self):
        row = fixture(1, 10, 20, 2, 1)
        row["participants"][0]["id"] = 10.9
        row["scores"][0]["participant_id"] = 10.9
        profile = collect_sportmonks_team_profile(
            {"id": 10, "name": "Home FC"}, 2026, [row], []
        )
        self.assertEqual(profile["matches"], [])
        self.assertEqual(
            profile["history_collection_diagnostics"]["excluded_missing_participants"],
            1,
        )

    def test_malformed_fixture_season_ids_are_excluded(self):
        for season_id in (True, 2026.9, "2026.9", "not-a-season", 0, -1):
            with self.subTest(season_id=season_id):
                row = fixture(1, 10, 20, 2, 1)
                row["season_id"] = season_id
                profile = collect_sportmonks_team_profile(
                    {"id": 10, "name": "Home FC"}, 2026, [row], []
                )
                self.assertEqual(profile["matches"], [])
                self.assertEqual(
                    profile["history_collection_diagnostics"]["excluded_wrong_season"],
                    1,
                )

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
        self.assertEqual(profile["matches"][0]["statistics"]["Counter Attacks"], 7.0)
        self.assertNotIn("Shots Accuracy", profile["matches"][0]["statistics"])
        self.assertNotIn("Attacks", profile["matches"][0]["statistics"])
        self.assertNotIn("Passes", profile["matches"][0]["statistics"])
        self.assertNotIn("Attacks", profile["matches"][0]["statistics"])
        raw_rows = profile["matches"][0]["statistics_raw_diagnostics"]
        shots_accuracy = next(row for row in raw_rows if row["statistic_name_raw"] == "Shots Accuracy")
        self.assertEqual(shots_accuracy["mapping_status"], "unmapped")
        self.assertEqual(shots_accuracy["raw_value"], 0.5)
        counter_row = next(row for row in raw_rows if row["statistic_type_id"] == 1527)
        self.assertEqual(counter_row["canonical_name"], "Counter Attacks")
        self.assertEqual(counter_row["mapping_status"], "mapped")
        self.assertEqual(profile["matches"][0]["statistics_provenance"][0]["provider"], "sportmonks")
        self.assertEqual(profile["matches"][0]["statistics_provenance"][0]["fixture_id"], 6)
        self.assertIsNone(profile["player_availability"])

    def test_conflicting_duplicate_supported_statistics_are_excluded(self):
        row = fixture(1, 10, 20, 2, 1)
        row["statistics"].append({
            "participant_id": 10,
            "type": {"id": 3, "name": "Total Shots"},
            "data": {"value": 99},
        })
        profile = collect_sportmonks_team_profile(
            {"id": 10, "name": "Home FC"}, 2026, [row], []
        )
        match = profile["matches"][0]
        self.assertNotIn("Total Shots", match["statistics"])
        self.assertTrue(any(
            item["canonical_name"] == "Total Shots"
            and item["reason"] == "conflicting_duplicate_observations"
            for item in match["statistics_conflicts"]
        ))
        self.assertFalse(any(
            item["canonical_name"] == "Total Shots"
            for item in match["statistics_provenance"]
        ))

    def test_invalid_duplicate_supported_statistic_is_excluded_regardless_of_row_order(self):
        for reverse in (False, True):
            with self.subTest(invalid_first=reverse):
                row = fixture(1, 10, 20, 2, 1)
                valid = next(
                    item for item in row["statistics"]
                    if item["participant_id"] == 10
                    and item["type"].get("name") == "Total Shots"
                )
                invalid = {
                    "participant_id": 10,
                    "type": {"id": 3, "name": "Total Shots"},
                    "data": {"value": "not-a-number"},
                }
                row["statistics"].append(invalid)
                if reverse:
                    row["statistics"].remove(valid)
                    row["statistics"].append(valid)
                profile = collect_sportmonks_team_profile(
                    {"id": 10, "name": "Home FC"}, 2026, [row], []
                )
                match = profile["matches"][0]
                self.assertNotIn("Total Shots", match["statistics"])
                self.assertTrue(match["statistics_conflicts"])

    def test_repository_season_snapshot_loads_season_data_once_as_reusable_bundle(self):
        teams = [{"team_id": "sportmonks:10", "name": "Home FC"}]
        fixtures = [{"fixture_id": "sportmonks:1", "raw_payload": {"id": 1}}]
        statistics = [{"fixture_id": "sportmonks:1", "team_id": "sportmonks:10"}]
        with patch(
            "football_repository.get_repository_season_snapshot",
            return_value={"teams": teams, "fixtures": fixtures, "statistics": statistics},
        ) as get_snapshot:
            snapshot = load_repository_season_snapshot("postgresql://example", "sportmonks:2026")

        self.assertEqual(snapshot["season_id"], "sportmonks:2026")
        self.assertEqual(snapshot["teams"], teams)
        self.assertEqual(snapshot["fixtures"], fixtures)
        self.assertEqual(snapshot["statistics"], statistics)
        get_snapshot.assert_called_once_with(
            "postgresql://example", "sportmonks:2026", fixture_limit=2000
        )

    def test_shared_team_profiles_build_league_reference_only_once(self):
        from sportmonks_layer2 import collect_repository_team_profiles

        raw_fixture = fixture(1, 10, 20, 2, 1)
        snapshot = {
            "season_id": "2026",
            "teams": [
                {"team_id": "sportmonks:10", "name": "Home FC"},
                {"team_id": "sportmonks:20", "name": "Away FC"},
            ],
            "fixtures": [
                {
                    "fixture_id": "sportmonks:1",
                    "raw_payload": raw_fixture,
                    "collected_at": "2026-11-09T10:30:00+00:00",
                    "provider_updated_at": "2026-11-08T14:00:00+00:00",
                },
            ],
            "statistics": [],
        }
        with patch(
            "sportmonks_layer2.build_league_reference_statistics",
            wraps=__import__("sportmonks_layer2").build_league_reference_statistics,
        ) as build_reference, patch(
            "sportmonks_layer2._fixture_statistics_index",
            wraps=__import__("sportmonks_layer2")._fixture_statistics_index,
        ) as build_statistics_index:
            profiles = collect_repository_team_profiles(
                "postgresql://example",
                ["sportmonks:10", "sportmonks:20"],
                "2026",
                season_snapshot=snapshot,
            )

        self.assertEqual(set(profiles), {"sportmonks:10", "sportmonks:20"})
        self.assertEqual(build_reference.call_count, 1)
        # One parse per provider fixture, reused for both team profiles and
        # the league reference distribution.
        self.assertEqual(build_statistics_index.call_count, 1)
        self.assertEqual(
            profiles["sportmonks:10"]["matches"][0]["statistics"]["Ball Possession"],
            60.0,
        )
        self.assertEqual(
            profiles["sportmonks:20"]["matches"][0]["statistics"]["Ball Possession"],
            40.0,
        )
        for profile in profiles.values():
            diagnostics = profile["history_collection_diagnostics"]
            self.assertEqual(
                diagnostics["history_repository_collected_at"],
                "2026-11-09T10:30:00+00:00",
            )
            self.assertEqual(
                diagnostics["history_provider_updated_at"],
                "2026-11-08T14:00:00+00:00",
            )
            # Repository ingestion time is not mislabeled as a direct live-fetch timestamp.
            self.assertIsNone(diagnostics["history_collection_fetched_at"])

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

    def test_state_labels_require_exact_completed_values(self):
        from sportmonks_layer2 import _state

        for label, expected in (
            ("Finished", "finished"),
            ("FT", "finished"),
            ("Full Time", "finished"),
            ("AET", "finished"),
            ("after penalties", "finished"),
            ("Penalties", "live"),
            ("Penalty Shootout", "live"),
            ("Extra Time", "live"),
            ("1st Half", "live"),
            ("NS", "scheduled"),
            ("Not Started", "scheduled"),
            ("unfinished", "unknown"),
            ("not finished", "unknown"),
            ("pre-finished", "unknown"),
            ("not live", "unknown"),
        ):
            with self.subTest(label=label):
                self.assertEqual(
                    _state({"state_id": None, "state": {"name": label}}),
                    expected,
                )

    def test_malformed_state_ids_are_not_coerced_to_finished(self):
        from sportmonks_layer2 import _state

        for state_id in (True, 5.9, "5.9", "finished"):
            with self.subTest(state_id=state_id):
                self.assertEqual(
                    _state({"state_id": state_id, "state": {"name": "unknown"}}),
                    "unknown",
                )
        self.assertEqual(
            _state({"state_id": "5", "state": {"name": "unknown"}}),
            "finished",
        )

    def test_all_documented_in_play_state_ids_are_not_treated_as_completed(self):
        from sportmonks_layer2 import _state
        for state_id in (2, 3, 4, 6, 9, 21, 22, 25):
            with self.subTest(state_id=state_id):
                row = fixture(1, 10, 20, 1, 0, state="unknown")
                row["state_id"] = state_id
                row["state"] = {}
                self.assertEqual(_state(row), "live")

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

    def test_empty_sidelined_include_is_distinguished_from_missing_feed(self):
        from sportmonks_layer2 import extract_sportmonks_match_details

        row = fixture(20, 10, 20, 0, 0, state="NS")
        row["sidelined"] = []
        details = extract_sportmonks_match_details(row, 10, 20, 2026)
        self.assertTrue(details["availability"]["home"]["sidelined_feed_available"])
        self.assertEqual(details["availability"]["home"]["reported_unavailable_count"], 0)

    def test_sidelined_completed_and_team_identity_are_preserved(self):
        from sportmonks_layer2 import extract_sportmonks_match_details

        row = fixture(20, 10, 20, 0, 0, state="NS")
        row["sidelined"] = [{
            "participant_id": 10, "player_id": 102, "completed": False,
            "player": {"id": 102, "name": "Unavailable Player"},
            "sideline": {"category": "Hamstring", "start_date": "2026-11-01", "end_date": None},
        }]
        details = extract_sportmonks_match_details(row, 10, 20, 2026)
        sidelined = details["availability"]["home"]["reported_sidelined"][0]
        self.assertEqual(sidelined["team_id"], 10)
        self.assertFalse(sidelined["completed"])

    def test_extract_match_details_rejects_wrong_fixture_id(self):
        from sportmonks_layer2 import extract_sportmonks_match_details

        row = fixture(20, 10, 20, 0, 0, state="NS")
        with self.assertRaises(ValueError):
            extract_sportmonks_match_details(
                row, 10, 20, 2026, expected_fixture_id=21
            )

    def test_extract_match_details_rejects_wrong_match_identity(self):
        from sportmonks_layer2 import extract_sportmonks_match_details

        row = fixture(20, 10, 20, 0, 0, state="NS")
        with self.assertRaises(ValueError):
            extract_sportmonks_match_details(row, 20, 10, 2026)


    def test_history_is_sorted_by_parsed_utc_kickoff_not_iso_text(self):
        older = fixture(1, 10, 20, 1, 0)
        older["starting_at"] = "2026-10-01T20:00:00+03:00"
        newer = fixture(2, 10, 20, 2, 0)
        newer["starting_at"] = "2026-10-01T18:30:00Z"
        newest = fixture(3, 10, 20, 3, 0)
        newest["starting_at"] = "2026-10-02T10:00:00Z"
        for row in (older, newer, newest):
            row["collection_fetched_at"] = "2026-11-07T12:00:00+00:00"

        profile = collect_sportmonks_team_profile(
            {"id": 10, "name": "Home FC"}, 2026,
            [older, newest, newer], [],
        )
        self.assertEqual([m["fixture_id"] for m in profile["matches"]], [3, 2, 1])
        diagnostics = profile["history_collection_diagnostics"]
        self.assertEqual(diagnostics["history_order"], "newest_first_by_parsed_utc_kickoff")
        self.assertEqual(diagnostics["history_collection_fetched_at"], "2026-11-07T12:00:00+00:00")
        self.assertEqual(diagnostics["history_latest_match_at"], "2026-10-02T10:00:00+00:00")

    def test_invalid_score_and_kickoff_are_excluded_and_reported(self):
        invalid_score = fixture(1, 10, 20, 1, 0)
        invalid_score["scores"][0]["score"]["goals"] = 1.5
        invalid_date = fixture(2, 10, 20, 2, 0)
        invalid_date["starting_at"] = "not-a-real-date"
        profile = collect_sportmonks_team_profile(
            {"id": 10, "name": "Home FC"}, 2026,
            [invalid_score, invalid_date], [],
        )
        diagnostics = profile["history_collection_diagnostics"]
        self.assertEqual(profile["data_quality"]["matches_returned"], 0)
        self.assertEqual(diagnostics["excluded_invalid_scores"], 1)
        self.assertEqual(diagnostics["excluded_invalid_kickoff"], 1)
        self.assertEqual(diagnostics["team_fixture_accounting_status"], "balanced")
        self.assertEqual(diagnostics["history_integrity_status"], "issues_detected")

    def test_statistic_normalization_rejects_invalid_numeric_values(self):
        from sportmonks_layer2 import _normalize_stat_value

        self.assertEqual(_normalize_stat_value("Ball Possession", "0.60"), 60.0)
        self.assertEqual(_normalize_stat_value("Passes %", "1%"), 1.0)
        self.assertEqual(_normalize_stat_value("Total Shots", 12), 12.0)
        self.assertEqual(_normalize_stat_value("Passes %", 1.5), 1.5)
        for key, value in (
            ("Ball Possession", -1),
            ("Ball Possession", "101%"),
            ("Ball Possession", "nan"),
            ("Ball Possession", "inf"),
            ("Passes %", 101.5),
            ("Total Shots", -1),
            ("Total Shots", "nan"),
            ("Total Shots", "inf"),
        ):
            with self.subTest(key=key, value=value):
                self.assertIsNone(_normalize_stat_value(key, value))

    def test_statistics_coverage_is_reported_without_dropping_valid_matches(self):
        row = fixture(1, 10, 20, 1, 0)
        row["statistics"] = [
            item for item in row["statistics"]
            if isinstance(item.get("type"), dict)
            and item["type"].get("name") in {"Ball Possession", "Ball Possession %", "Total Shots"}
        ]
        profile = collect_sportmonks_team_profile(
            {"id": 10, "name": "Home FC"}, 2026, [row], [],
        )
        diagnostics = profile["history_collection_diagnostics"]
        self.assertEqual(profile["data_quality"]["matches_returned"], 1)
        self.assertEqual(diagnostics["matches_with_any_statistics"], 1)
        self.assertEqual(diagnostics["matches_with_complete_core_statistics"], 0)
        self.assertEqual(diagnostics["statistics_coverage_by_metric"]["Ball Possession"], 1)
        self.assertEqual(diagnostics["core_statistics_completeness_pct"], 25.0)

    def test_layer2_statistics_coverage_uses_shared_eight_metric_definitions(self):
        from statistics_coverage import CORE_STATISTICS

        row = fixture(1, 10, 20, 1, 0)
        row["statistics"].extend([
            {"participant_id": 10, "type": {"id": 5, "name": "Shots on Target"}, "data": {"value": 6}},
            {"participant_id": 10, "type": {"id": 6, "name": "Tackles"}, "data": {"value": 14}},
            {"participant_id": 10, "type": {"id": 7, "name": "Interceptions"}, "data": {"value": 9}},
            {"participant_id": 10, "type": {"id": 8, "name": "Corner Kicks"}, "data": {"value": 7}},
        ])
        profile = collect_sportmonks_team_profile(
            {"id": 10, "name": "Home FC"}, 2026, [row], [],
        )
        diagnostics = profile["history_collection_diagnostics"]
        expected_labels = [label for label, _group, _aliases in CORE_STATISTICS]

        self.assertEqual(diagnostics["statistics_core_metrics"], expected_labels)
        self.assertEqual(diagnostics["statistics_coverage_by_metric"], {
            label: 1 for label in expected_labels
        })
        self.assertEqual(diagnostics["matches_with_complete_core_statistics"], 1)
        self.assertEqual(diagnostics["core_statistics_completeness_pct"], 100.0)


    def test_duplicate_fixture_ids_are_reported_and_excluded_from_history(self):
        first = fixture(1, 10, 20, 1, 0)
        duplicate = fixture(1, 10, 20, 3, 0)
        profile = collect_sportmonks_team_profile(
            {"id": 10, "name": "Home FC"}, 2026, [first, duplicate], [],
        )
        diagnostics = profile["history_collection_diagnostics"]
        self.assertEqual(profile["data_quality"]["matches_returned"], 1)
        self.assertEqual(diagnostics["duplicate_fixture_id_count"], 1)
        self.assertEqual(diagnostics["excluded_duplicate_fixture_id"], 1)
        self.assertEqual(diagnostics["history_integrity_status"], "issues_detected")

    def test_upcoming_fixture_diagnostics_accept_iso_kickoff_and_report_counts(self):
        from datetime import datetime, timezone
        from sportmonks_layer2 import diagnose_upcoming_match_fixture

        row = fixture(30, 10, 20, 0, 0, state="unknown")
        row["state_id"] = 1
        row["state"] = {}
        row["starting_at"] = "2026-11-08T15:00:00Z"
        now = int(datetime(2026, 11, 7, 12, tzinfo=timezone.utc).timestamp())
        diagnostic = diagnose_upcoming_match_fixture(
            [row], 10, 20, 2026, now_timestamp=now
        )
        self.assertTrue(diagnostic["verified"])
        self.assertEqual(diagnostic["fixture"]["id"], 30)
        self.assertEqual(diagnostic["same_season"], 1)
        self.assertEqual(diagnostic["scheduled"], 1)
        self.assertEqual(diagnostic["exact_home_away"], 1)
        self.assertEqual(diagnostic["future_kickoff"], 1)

    def test_upcoming_fixture_diagnostics_report_unparseable_kickoff(self):
        from datetime import datetime, timezone
        from sportmonks_layer2 import diagnose_upcoming_match_fixture

        row = fixture(31, 10, 20, 0, 0, state="unknown")
        row["state"] = "NS"
        row["state_id"] = None
        row["starting_at"] = "not-a-date"
        now = int(datetime(2026, 11, 7, tzinfo=timezone.utc).timestamp())
        diagnostic = diagnose_upcoming_match_fixture(
            [row], 10, 20, 2026, now_timestamp=now
        )
        self.assertFalse(diagnostic["verified"])
        self.assertEqual(diagnostic["exact_home_away"], 1)
        self.assertEqual(diagnostic["missing_kickoff"], 1)
        self.assertIn("kickoff timestamp could not be parsed", diagnostic["reason"])


if __name__ == "__main__":
    unittest.main()
