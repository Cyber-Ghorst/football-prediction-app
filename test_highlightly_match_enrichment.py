import unittest
from datetime import datetime, timezone

from highlightly_match_enrichment import (
    _highlightly_rows,
    _highlightly_stat_value,
    _season_value,
    apply_highlightly_lineups_fallback,
    apply_highlightly_statistics_fallback,
    collect_highlightly_match_enrichment,
    normalize_highlightly_lineups,
)


def sm_fixture(fid=700, date="2026-11-07T15:00:00Z", state="FT", season=2026):
    return {
        "id": fid,
        "season_id": season,
        "starting_at": date,
        "state_id": 5 if state == "FT" else 1,
        "state": {"short_name": state, "name": "Finished" if state == "FT" else "Not Started"},
        "participants": [
            {"id": 1, "name": "Arsenal", "meta": {"location": "home"}},
            {"id": 2, "name": "Chelsea", "meta": {"location": "away"}},
        ],
        "scores": [
            {"participant_id": 1, "description": "CURRENT", "score": {"goals": 2}},
            {"participant_id": 2, "description": "CURRENT", "score": {"goals": 1}},
        ] if state == "FT" else [],
        "statistics": [
            {"participant_id": 1, "type": {"name": "Ball Possession"}, "data": {"value": "60%"}},
            {"participant_id": 1, "type": {"name": "Pass Accuracy"}, "data": {"value": 0.82}},
            {"participant_id": 1, "type": {"name": "Total Shots"}, "data": {"value": 12}},
            {"participant_id": 2, "type": {"name": "Ball Possession"}, "data": {"value": "40%"}},
            {"participant_id": 2, "type": {"name": "Pass Accuracy"}, "data": {"value": 0.70}},
            {"participant_id": 2, "type": {"name": "Total Shots"}, "data": {"value": 8}},
        ],
    }


def hl_match(mid=9001, date="2026-11-07T15:00:00Z", state="Finished", season=2026):
    return {
        "id": mid,
        "date": date,
        "homeTeam": {"id": 11, "name": "Arsenal"},
        "awayTeam": {"id": 12, "name": "Chelsea"},
        "league": {"id": 99, "name": "Premier League", "season": season,
                   "country": {"name": "England"}},
        "state": {"description": state, "score": {"current": "2 - 1"} if state == "Finished" else {}},
    }


class FakeHighlightly:
    def __init__(self, matches, stats=None, lineups=None):
        self.match_rows = matches
        self.stats = stats or {}
        self.lineup_payload = lineups
        self.stats_calls = []
        self.lineup_calls = []

    def matches(self, **params):
        return self.match_rows

    def statistics(self, match_id):
        self.stats_calls.append(str(match_id))
        return self.stats.get(str(match_id), [])

    def lineups(self, match_id):
        self.lineup_calls.append(str(match_id))
        return self.lineup_payload


class HighlightlyMatchEnrichmentTests(unittest.TestCase):
    def test_highlightly_lineup_fallback_fills_only_missing_exact_fixture_lineups(self):
        starters = [{"player_id": 101, "name": "Player One"}]
        home = {
            "name": "Arsenal",
            "lineups": {"lineups_available": False, "starting_players": []},
            "availability": {"injury_data_available": False, "player_availability": None},
        }
        away = {
            "name": "Chelsea",
            "lineups": {"lineups_available": True, "starting_players": [{"name": "Existing"}]},
            "availability": {"injury_data_available": False, "player_availability": None},
        }
        report = {
            "fetched_at": "2026-11-08T11:59:00Z",
            "collection_completed_at": "2026-11-08T12:00:00Z",
            "lineups": {
                "sportmonks_fixture_id": "700",
                "highlightly_match_id": "9001",
                "home": {
                    "team_name": "Arsenal",
                    "team_id": 11,
                    "formation": "4-3-3",
                    "starting_players": starters,
                    "substitutes": [],
                    "lineups_available": True,
                },
                "away": {
                    "team_name": "Chelsea",
                    "team_id": 12,
                    "formation": "4-4-2",
                    "starting_players": [{"name": "Other Player"}],
                    "substitutes": [],
                    "lineups_available": True,
                },
            },
        }

        result = apply_highlightly_lineups_fallback(
            [home, away], report, expected_fixture_id=700
        )

        self.assertEqual(result["lineups_added"], 1)
        self.assertEqual(home["lineups"]["source"], "highlightly")
        self.assertEqual(home["lineups"]["starting_players"], starters)
        self.assertTrue(away["lineups"]["lineups_available"])
        self.assertEqual(away["lineups"]["starting_players"], [{"name": "Existing"}])
        self.assertIsNone(home["availability"]["player_availability"])
        self.assertFalse(result["availability_changed"])

    def test_highlightly_lineup_fallback_rejects_wrong_fixture_and_invalid_timestamp(self):
        profile = {
            "name": "Arsenal",
            "lineups": {"lineups_available": False},
            "availability": {"player_availability": None},
        }
        report = {
            "collection_completed_at": "invalid",
            "lineups": {
                "sportmonks_fixture_id": "999",
                "home": {"team_name": "Arsenal", "lineups_available": True,
                         "starting_players": [{"name": "Player"}]},
                "away": {"team_name": "Chelsea", "lineups_available": True,
                         "starting_players": [{"name": "Player"}]},
            },
        }

        wrong_fixture = apply_highlightly_lineups_fallback(
            [profile], report, expected_fixture_id=700
        )
        self.assertEqual(wrong_fixture["reason"], "highlightly_lineup_fixture_id_mismatch")
        self.assertFalse(profile["lineups"].get("lineups_available"))

        report["lineups"]["sportmonks_fixture_id"] = "700"
        invalid_timestamp = apply_highlightly_lineups_fallback(
            [profile], report, expected_fixture_id=700
        )
        self.assertEqual(invalid_timestamp["reason"], "missing_or_invalid_highlightly_collection_timestamp")
        self.assertFalse(profile["lineups"].get("lineups_available"))


    def test_layer2_fallback_fills_only_missing_fields_after_exact_identity(self):
        home = {
            "name": "Arsenal",
            "matches": [{
                "fixture_id": 700,
                "venue": "home",
                "opponent_name": "Chelsea",
                "statistics": {"Total Shots": 12.0},
                "opponent_statistics": {},
                "statistics_provenance": [],
                "statistics_raw_diagnostics": [],
            }],
        }
        away = {
            "name": "Chelsea",
            "matches": [{
                "fixture_id": 700,
                "venue": "away",
                "opponent_name": "Arsenal",
                "statistics": {},
                "opponent_statistics": {},
                "statistics_provenance": [],
                "statistics_raw_diagnostics": [],
            }],
        }
        report = {
            "fetched_at": "2026-11-08T11:59:00Z",
            "collection_completed_at": "2026-11-08T12:00:00Z",
            "statistics": [{
                "sportmonks_fixture_id": "700",
                "highlightly_match_id": "9001",
                "teams": {
                    "home": {
                        "team_name": "Arsenal",
                        "highlightly_observations": [
                            {"canonical_name": "Total Shots", "raw_value": 14, "normalized_value": 14.0},
                            {"canonical_name": "Ball Possession", "raw_value": 0.6, "normalized_value": 60.0},
                        ],
                    },
                    "away": {
                        "team_name": "Chelsea",
                        "highlightly_observations": [
                            {"canonical_name": "Total Shots", "raw_value": 8, "normalized_value": 8.0},
                            {"canonical_name": "Ball Possession", "raw_value": 0.4, "normalized_value": 40.0},
                        ],
                    },
                },
            }],
        }

        result = apply_highlightly_statistics_fallback([home, away], report)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["fields_added"], 7)
        self.assertEqual(result["primary_values_preserved"], 1)
        self.assertEqual(home["matches"][0]["statistics"]["Total Shots"], 12.0)
        self.assertEqual(home["matches"][0]["statistics"]["Ball Possession"], 60.0)
        self.assertEqual(home["matches"][0]["opponent_statistics"]["Total Shots"], 8.0)
        self.assertEqual(away["matches"][0]["statistics"]["Total Shots"], 8.0)
        self.assertEqual(away["matches"][0]["opponent_statistics"]["Ball Possession"], 60.0)
        self.assertEqual(home["matches"][0]["statistics_provenance"][-1]["provider"], "highlightly")
        self.assertEqual(
            home["tactical_summary"]["available_metrics"]["average_possession"], 60.0
        )
        self.assertFalse(home["highlightly_statistics_fallback"]["tactical_evidence_updated"])

    def test_layer2_fallback_rejects_wrong_team_and_invalid_timestamp(self):
        profile = {
            "name": "Arsenal",
            "matches": [{
                "fixture_id": 700,
                "venue": "home",
                "opponent_name": "Chelsea",
                "statistics": {},
                "opponent_statistics": {},
            }],
        }
        report = {
            "fetched_at": "2026-11-08T11:59:00Z",
            "collection_completed_at": "invalid",
            "statistics": [{
                "sportmonks_fixture_id": "700",
                "teams": {
                    "home": {"team_name": "Different Club", "highlightly_observations": [
                        {"canonical_name": "Total Shots", "normalized_value": 14.0}
                    ]},
                    "away": {"team_name": "Chelsea", "highlightly_observations": []},
                },
            }],
        }

        result = apply_highlightly_statistics_fallback([profile], report)

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(profile["matches"][0]["statistics"], {})

    def test_layer2_fallback_skips_conflicting_duplicate_metric_rows(self):
        profile = {
            "name": "Arsenal",
            "matches": [{
                "fixture_id": 700,
                "venue": "home",
                "opponent_name": "Chelsea",
                "statistics": {},
                "opponent_statistics": {},
            }],
        }
        report = {
            "fetched_at": "2026-11-08T11:59:00Z",
            "collection_completed_at": "2026-11-08T12:00:00Z",
            "statistics": [{
                "sportmonks_fixture_id": "700",
                "highlightly_match_id": "9001",
                "teams": {
                    "home": {"team_name": "Arsenal", "highlightly_observations": [
                        {"canonical_name": "Total Shots", "normalized_value": 14.0},
                        {"canonical_name": "Total Shots", "normalized_value": 15.0},
                    ]},
                    "away": {"team_name": "Chelsea", "highlightly_observations": []},
                },
            }],
        }

        result = apply_highlightly_statistics_fallback([profile], report)

        self.assertEqual(result["fields_added"], 0)
        self.assertEqual(result["ambiguous_metrics_skipped"], 1)
        self.assertEqual(profile["matches"][0]["statistics"], {})


    def test_highlightly_statistics_reject_nonfinite_negative_and_out_of_range_values(self):
        self.assertEqual(_highlightly_stat_value("Ball Possession", 0.6), 60.0)
        self.assertEqual(_highlightly_stat_value("Ball Possession", "60%"), 60.0)
        self.assertEqual(_highlightly_stat_value("Ball Possession", "1%"), 1.0)
        self.assertEqual(_highlightly_stat_value("Total Shots", 12), 12.0)
        for name, value in (
            ("Ball Possession", -1),
            ("Ball Possession", 101),
            ("Ball Possession", "101%"),
            ("Ball Possession", "nan"),
            ("Ball Possession", "inf"),
            ("Total Shots", -1),
            ("Total Shots", "nan"),
            ("Total Shots", "inf"),
        ):
            with self.subTest(name=name, value=value):
                self.assertIsNone(_highlightly_stat_value(name, value))


    def test_season_parser_rejects_boolean_fractional_and_malformed_values(self):
        self.assertEqual(_season_value(2026), 2026)
        self.assertEqual(_season_value("2026"), 2026)
        self.assertEqual(_season_value({"year": 2026}), 2026)
        self.assertEqual(_season_value({"year": None, "start": "2026"}), 2026)
        for invalid in (True, False, 2026.9, "2026.0", "2026/27", "", 0, -1):
            with self.subTest(value=invalid):
                self.assertIsNone(_season_value(invalid))

    def test_missing_or_malformed_provider_season_is_not_assumed(self):
        rows = []
        missing = hl_match(mid=9101)
        missing["league"].pop("season")
        malformed = hl_match(mid=9102)
        malformed["league"]["season"] = 2026.9
        boolean = hl_match(mid=9103)
        boolean["league"]["season"] = True
        wrong = hl_match(mid=9104, season=2025)
        valid = hl_match(mid=9105, season="2026")
        rows.extend((missing, malformed, boolean, wrong, valid))
        client = FakeHighlightly(rows)

        accepted = _highlightly_rows(
            client, "Premier League", "England", 2026
        )

        self.assertEqual([item["raw"]["id"] for item in accepted], [9105])


    def test_statistics_normalize_units_and_expose_conflicts_without_averaging(self):
        sm = sm_fixture()
        hl_stats = [
            {"team": {"id": 11, "name": "Arsenal"}, "statistics": [
                {"displayName": "Ball possession", "value": 0.60},
                {"displayName": "Pass accuracy", "value": 0.82},
                {"displayName": "Total shots", "value": 14},
                {"displayName": "Shots accuracy", "value": 0.5},
            ]},
            {"team": {"id": 12, "name": "Chelsea"}, "statistics": [
                {"displayName": "Ball possession", "value": 0.40},
                {"displayName": "Pass accuracy", "value": 0.70},
                {"displayName": "Total shots", "value": 8},
            ]},
        ]
        client = FakeHighlightly([hl_match()], {"9001": hl_stats})
        report = collect_highlightly_match_enrichment(
            client=client, sportmonks_fixtures=[sm],
            competition="Premier League", country="England", season=2026,
            home_team_name="Arsenal", away_team_name="Chelsea",
            now=datetime(2026, 11, 8, tzinfo=timezone.utc),
        )
        self.assertEqual(report["statistics_matches_compared"], 1)
        self.assertEqual(report["statistics_metric_agreements"], 5)
        self.assertEqual(report["statistics_metric_conflicts"], 1)
        home = report["statistics"][0]["teams"]["home"]
        self.assertEqual(home["comparisons"]["Ball Possession"]["status"], "agreement")
        self.assertEqual(home["comparisons"]["Total Shots"]["status"], "conflict")
        self.assertEqual(home["comparisons"]["Total Shots"]["sportmonks"], 12.0)
        self.assertEqual(home["comparisons"]["Total Shots"]["highlightly"], 14.0)
        self.assertEqual(client.stats_calls, ["9001"])

    def test_statistics_payload_team_ids_must_match_exact_highlightly_fixture(self):
        stats = [
            {"team": {"id": 999, "name": "Arsenal"}, "statistics": [
                {"displayName": "Total shots", "value": 14},
            ]},
            {"team": {"id": 12, "name": "Chelsea"}, "statistics": [
                {"displayName": "Total shots", "value": 8},
            ]},
        ]
        client = FakeHighlightly([hl_match()], {"9001": stats})
        report = collect_highlightly_match_enrichment(
            client=client, sportmonks_fixtures=[sm_fixture()],
            competition="Premier League", country="England", season=2026,
            home_team_name="Arsenal", away_team_name="Chelsea",
            now=datetime(2026, 11, 8, tzinfo=timezone.utc),
        )
        self.assertEqual(report["statistics_matches_compared"], 0)
        self.assertTrue(any("team ID does not match" in value for value in report["errors"].values()))

    def test_wrong_competition_country_season_or_team_is_not_joined(self):
        bad = hl_match()
        bad["league"]["country"]["name"] = "Spain"
        client = FakeHighlightly([bad])
        report = collect_highlightly_match_enrichment(
            client=client, sportmonks_fixtures=[sm_fixture()],
            competition="Premier League", country="England", season=2026,
            home_team_name="Arsenal", away_team_name="Chelsea",
        )
        self.assertEqual(report["statistics_matches_compared"], 0)
        self.assertEqual(client.stats_calls, [])

    def test_upcoming_lineups_are_loaded_only_for_exact_fixture(self):
        sm = sm_fixture(fid=701, date="2026-11-09T18:00:00Z", state="NS")
        hl = hl_match(mid=9002, date="2026-11-09T18:02:00Z", state="Not Started")
        lineups = {
            "homeTeam": {
                "id": 11, "name": "Arsenal", "formation": "4-3-3",
                "initialLineup": [[{"id": 1, "name": "Keeper", "number": 1, "position": "Goalkeeper"}],
                                  [{"id": 2, "name": "Defender", "number": 2, "position": "Defender"}]],
                "substitutes": [{"id": 3, "name": "Sub", "number": 12, "position": "Midfielder"}],
            },
            "awayTeam": {
                "id": 12, "name": "Chelsea", "formation": "4-2-3-1",
                "initialLineup": [[{"id": 4, "name": "Keeper 2", "number": 1, "position": "Goalkeeper"}]],
                "substitutes": [],
            },
        }
        client = FakeHighlightly([hl], lineups=lineups)
        report = collect_highlightly_match_enrichment(
            client=client, sportmonks_fixtures=[sm],
            competition="Premier League", country="England", season=2026,
            home_team_name="Arsenal", away_team_name="Chelsea",
            selected_upcoming_fixture=sm,
            now=datetime(2026, 11, 9, 17, 30, tzinfo=timezone.utc),
        )
        self.assertTrue(report["upcoming_lineup_match_found"])
        self.assertEqual(report["lineups"]["home"]["formation"], "4-3-3")
        self.assertEqual(report["lineups"]["home"]["confirmation_status"], "provider_reported")
        self.assertEqual(len(report["lineups"]["home"]["starting_players"]), 2)
        self.assertEqual(len(report["lineups"]["home"]["substitutes"]), 1)
        self.assertEqual(client.lineup_calls, ["9002"])

    def test_lineup_payload_team_ids_must_match_exact_highlightly_fixture(self):
        sm = sm_fixture(fid=701, date="2026-11-09T18:00:00Z", state="NS")
        hl = hl_match(mid=9002, date="2026-11-09T18:02:00Z", state="Not Started")
        lineups = {
            "homeTeam": {"id": 999, "name": "Arsenal", "initialLineup": [{"id": 1, "name": "Keeper"}]},
            "awayTeam": {"id": 12, "name": "Chelsea", "initialLineup": [{"id": 2, "name": "Keeper 2"}]},
        }
        client = FakeHighlightly([hl], lineups=lineups)
        report = collect_highlightly_match_enrichment(
            client=client, sportmonks_fixtures=[sm],
            competition="Premier League", country="England", season=2026,
            home_team_name="Arsenal", away_team_name="Chelsea",
            selected_upcoming_fixture=sm,
            now=datetime(2026, 11, 9, 17, 30, tzinfo=timezone.utc),
        )
        self.assertIsNone(report["lineups"])
        self.assertTrue(any("team ID does not match" in value for value in report["errors"].values()))

    def test_lineup_request_is_skipped_outside_documented_availability_window(self):
        sm = sm_fixture(fid=702, date="2026-11-09T18:00:00Z", state="NS")
        hl = hl_match(mid=9003, date="2026-11-09T18:00:00Z", state="Not Started")
        client = FakeHighlightly([hl], lineups={})
        report = collect_highlightly_match_enrichment(
            client=client, sportmonks_fixtures=[sm],
            competition="Premier League", country="England", season=2026,
            home_team_name="Arsenal", away_team_name="Chelsea",
            selected_upcoming_fixture=sm,
            now=datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(report["lineup_requests"], 0)
        self.assertEqual(client.lineup_calls, [])
        self.assertIn("40 minutes before kickoff", report["lineup_not_requested_reason"])

    def test_lineup_wrong_team_identity_is_rejected(self):
        payload = {
            "homeTeam": {"name": "Different Club"},
            "awayTeam": {"name": "Chelsea"},
        }
        with self.assertRaises(ValueError):
            normalize_highlightly_lineups(
                payload, expected_home="Arsenal", expected_away="Chelsea", match_id=9
            )


if __name__ == "__main__":
    unittest.main()
