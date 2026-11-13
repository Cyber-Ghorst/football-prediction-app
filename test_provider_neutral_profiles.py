from datetime import datetime, timedelta, timezone
import unittest

from provider_neutral_profiles import (
    build_provider_neutral_team_profile,
    build_repository_team_profiles,
)


def _fixture(fixture_id, team_id="canonical:home", opponent_id="canonical:away",
             season_id="canonical:season", status="finished", days_ago=1,
             home_goals=2, away_goals=1):
    return {
        "fixture_id": fixture_id, "season_id": season_id, "status": status,
        "home_team_id": team_id, "away_team_id": opponent_id,
        "home_team": "Home FC", "away_team": "Away FC",
        "starting_at": (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(),
        "home_goals": home_goals, "away_goals": away_goals,
        "source_provider": "openligadb",
    }


class ProviderNeutralProfileTests(unittest.TestCase):
    def test_builds_profile_from_canonical_ids_and_keeps_unknown_inputs_missing(self):
        profile = build_provider_neutral_team_profile(
            {"team_id": "canonical:home", "name": "Home FC"},
            [_fixture("fixture:1")],
            season_id="canonical:season",
        )
        self.assertEqual(profile["id"], "canonical:home")
        self.assertEqual(profile["matches"][0]["goals_for"], 2)
        self.assertEqual(profile["matches"][0]["goals_against"], 1)
        self.assertEqual(profile["matches"][0]["opponent_strength"], 50.0)
        self.assertEqual(profile["data_quality"]["opponent_strength_source"],
                         "derived_from_completed_canonical_season_fixtures")
        self.assertIsNone(profile["player_availability"])
        self.assertFalse(profile["lineups"]["lineups_available"])
        self.assertEqual(profile["data_quality"]["provider"], "canonical_repository")

    def test_ignores_wrong_season_live_and_invalid_score_rows(self):
        rows = [
            _fixture("wrong-season", season_id="other-season"),
            _fixture("live", status="live"),
            _fixture("bad-score", home_goals=None),
        ]
        profile = build_provider_neutral_team_profile(
            {"team_id": "canonical:home", "name": "Home FC"},
            rows,
            season_id="canonical:season",
        )
        self.assertEqual(profile["matches"], [])
        self.assertEqual(profile["data_quality"]["excluded"]["wrong_season"], 1)
        self.assertEqual(profile["data_quality"]["excluded"]["not_completed"], 1)
        self.assertEqual(profile["data_quality"]["excluded"]["invalid_score"], 1)

    def test_uses_only_statistics_for_the_requested_canonical_team(self):
        profile = build_provider_neutral_team_profile(
            {"team_id": "canonical:home", "name": "Home FC"},
            [_fixture("fixture:1")],
            season_id="canonical:season",
            statistics=[
                {"fixture_id": "fixture:1", "team_id": "canonical:home",
                 "statistic_type": "Ball Possession", "statistic_value": 57,
                 "provider": "highlightly"},
                {"fixture_id": "fixture:1", "team_id": "canonical:away",
                 "statistic_type": "Ball Possession", "statistic_value": 43,
                 "provider": "highlightly"},
            ],
        )
        self.assertEqual(profile["matches"][0]["statistics"], {"Ball Possession": 57})

    def test_rejects_invalid_and_unmapped_statistics_without_imputation(self):
        profile = build_provider_neutral_team_profile(
            {"team_id": "canonical:home", "name": "Home FC"},
            [_fixture("fixture:1")],
            season_id="canonical:season",
            statistics=[
                {"fixture_id": "fixture:1", "team_id": "canonical:home",
                 "statistic_type": "Ball Possession", "statistic_value": 130,
                 "provider": "highlightly"},
                {"fixture_id": "fixture:1", "team_id": "canonical:home",
                 "statistic_type": "Pass Accuracy", "statistic_value": -4,
                 "provider": "highlightly"},
                {"fixture_id": "fixture:1", "team_id": "canonical:home",
                 "statistic_type": "Unknown Metric", "statistic_value": 12,
                 "provider": "highlightly"},
                {"fixture_id": "fixture:1", "team_id": "canonical:home",
                 "statistic_type": "Total Shots", "statistic_value": "not numeric",
                 "provider": "highlightly"},
            ],
        )
        match = profile["matches"][0]
        self.assertEqual(match["statistics"], {})
        self.assertEqual(len(match["statistics_invalid_rows"]), 3)
        self.assertEqual(len(match["statistics_unmapped_rows"]), 1)
        self.assertEqual(profile["data_quality"]["statistics_invalid_value_count"], 3)
        self.assertEqual(profile["data_quality"]["statistics_unmapped_observation_count"], 1)

    def test_normalizes_percentage_and_fractional_statistics(self):
        profile = build_provider_neutral_team_profile(
            {"team_id": "canonical:home", "name": "Home FC"},
            [_fixture("fixture:1")],
            season_id="canonical:season",
            statistics=[
                {"fixture_id": "fixture:1", "team_id": "canonical:home",
                 "statistic_type": "Ball Possession", "statistic_value": "0.57",
                 "provider": "highlightly"},
                {"fixture_id": "fixture:1", "team_id": "canonical:home",
                 "statistic_type": "Total Shots", "statistic_value": "14",
                 "provider": "highlightly"},
            ],
        )
        self.assertEqual(profile["matches"][0]["statistics"]["Ball Possession"], 57.0)
        self.assertEqual(profile["matches"][0]["statistics"]["Total Shots"], 14.0)

    def test_conflicting_provider_statistics_are_not_silently_overwritten(self):
        profile = build_provider_neutral_team_profile(
            {"team_id": "canonical:home", "name": "Home FC"},
            [_fixture("fixture:1")],
            season_id="canonical:season",
            statistics=[
                {"fixture_id": "fixture:1", "team_id": "canonical:home",
                 "statistic_type": "Ball Possession", "statistic_value": 57,
                 "source_provider": "highlightly"},
                {"fixture_id": "fixture:1", "team_id": "canonical:home",
                 "statistic_type": "Ball Possession", "statistic_value": 59,
                 "source_provider": "livescore_football"},
            ],
        )
        self.assertNotIn("Ball Possession", profile["matches"][0]["statistics"])
        self.assertEqual(profile["matches"][0]["statistics_conflicts"], ["Ball Possession"])
        self.assertEqual(profile["data_quality"]["statistics_conflict_count"], 1)

    def test_builds_multiple_profiles_from_one_canonical_snapshot(self):
        snapshot = {
            "season_id": "canonical:season",
            "teams": [
                {"team_id": "canonical:home", "name": "Home FC"},
                {"team_id": "canonical:away", "name": "Away FC"},
            ],
            "fixtures": [_fixture("fixture:1")],
            "statistics": [],
        }
        profiles = build_repository_team_profiles(
            snapshot, ["canonical:home", "canonical:away"], "canonical:season"
        )
        self.assertEqual(set(profiles), {"canonical:home", "canonical:away"})
        self.assertEqual(profiles["canonical:away"]["matches"][0]["goals_for"], 1)
        self.assertEqual(profiles["canonical:away"]["matches"][0]["venue"], "away")

    def test_rejects_snapshot_from_a_different_canonical_season(self):
        with self.assertRaisesRegex(ValueError, "season"):
            build_repository_team_profiles(
                {"season_id": "season:wrong", "teams": [], "fixtures": [], "statistics": []},
                ["canonical:home"], "canonical:season",
            )


    def test_includes_tvd_evidence_and_opponent_statistics_without_imputation(self):
        profile = build_provider_neutral_team_profile(
            {"team_id": "canonical:home", "name": "Home FC"},
            [_fixture("fixture:1")],
            season_id="canonical:season",
            statistics=[
                {"fixture_id": "fixture:1", "team_id": "canonical:home",
                 "statistic_type": "Ball Possession", "statistic_value": 57,
                 "provider": "highlightly"},
                {"fixture_id": "fixture:1", "team_id": "canonical:away",
                 "statistic_type": "Ball Possession", "statistic_value": 43,
                 "provider": "highlightly"},
            ],
        )
        self.assertEqual(profile["matches"][0]["opponent_statistics"]["Ball Possession"], 43)
        self.assertIsInstance(profile["tactical_evidence"], dict)
        self.assertIn("weapons", profile["tactical_evidence"])
        self.assertIn("vulnerabilities", profile["tactical_evidence"])
        self.assertEqual(
            profile["tactical_evidence"]["evidence_metadata"]["latest_five_weight"], 0.60
        )
        self.assertEqual(
            profile["tactical_evidence"]["evidence_metadata"]["previous_five_weight"], 0.40
        )
        self.assertIsNone(profile["player_availability"])
        self.assertFalse(profile["lineups"]["lineups_available"])

    def test_checks_duplicate_ids_and_duplicate_fixture_fingerprints(self):
        first = _fixture("fixture:1", days_ago=2)
        duplicate_id = dict(first)
        duplicate_fingerprint = dict(first, fixture_id="fixture:2")
        profile = build_provider_neutral_team_profile(
            {"team_id": "canonical:home", "name": "Home FC"},
            [first, duplicate_id, duplicate_fingerprint],
            season_id="canonical:season",
        )
        diagnostics = profile["history_collection_diagnostics"]
        self.assertEqual(len(profile["matches"]), 1)
        self.assertEqual(diagnostics["duplicate_fixture_id_count"], 1)
        self.assertEqual(diagnostics["duplicate_fixture_fingerprint_count"], 1)
        self.assertTrue(diagnostics["duplicate_fixture_ids_checked"])
        self.assertEqual(diagnostics["history_integrity_status"], "issues_detected")
        self.assertEqual(diagnostics["team_fixture_accounting_status"], "balanced")



    def test_provider_neutral_coverage_reports_eight_core_metrics_and_tactical_outputs(self):
        from statistics_coverage import build_provider_neutral_statistics_coverage
        match = {
            "fixture_id": "fixture:1",
            "statistics": {
                "Ball Possession": 57, "Passes %": 82, "Total Shots": 12,
                "Shots on Target": 4, "Tackles": 9, "Interceptions": 6,
                "Blocked Shots": 2, "Corner Kicks": 5, "Counter Attacks": 3,
            },
            "opponent_statistics": {"Counter Attacks": 2},
            "statistics_provenance": [{"provider": "highlightly"}],
            "statistics_invalid_rows": [], "statistics_unmapped_rows": [],
            "statistics_conflicts": [], "opponent_statistics_conflicts": [],
        }
        report = build_provider_neutral_statistics_coverage([match])
        self.assertEqual(report["core_metrics_total"], 8)
        self.assertEqual(report["core_metrics_complete"], 8)
        self.assertEqual(report["fixtures_checked"], 1)
        counter = next(row for row in report["tactical_evidence_metrics"] if row["statistic"] == "Counter Attacks")
        self.assertEqual(counter["team_output_fixtures"], 1)
        self.assertEqual(counter["opponent_output_fixtures"], 1)
        self.assertTrue(report["no_imputation"])

    def test_provider_neutral_coverage_separates_invalid_conflicting_and_missing(self):
        from statistics_coverage import build_provider_neutral_statistics_coverage
        report = build_provider_neutral_statistics_coverage([{
            "fixture_id": "fixture:1", "statistics": {}, "opponent_statistics": {},
            "statistics_invalid_rows": [{"statistic_type": "Ball Possession"}],
            "statistics_unmapped_rows": [{"raw_type": "Unknown Metric"}],
            "statistics_conflicts": ["Passes %"],
            "opponent_statistics_conflicts": [],
        }])
        by_name = {row["statistic"]: row for row in report["metrics"]}
        self.assertEqual(by_name["Ball Possession"]["status"], "invalid")
        self.assertEqual(by_name["Passes %"]["status"], "conflicted")
        self.assertEqual(by_name["Total Shots"]["status"], "missing")
        self.assertEqual(report["invalid_observations"], 1)
        self.assertEqual(report["unmapped_observations"], 1)
        self.assertEqual(report["conflict_count"], 1)


    def test_profile_exposes_layer2_freshness_and_statistics_accounting_contract(self):
        fixture = _fixture("fixture:1")
        fixture.update({
            "collection_fetched_at": "2026-11-12T10:00:00Z",
            "repository_collected_at": "2026-11-12T10:01:00Z",
            "provider_updated_at": "2026-11-12T09:59:00Z",
        })
        statistics = [
            {"fixture_id": "fixture:1", "team_id": "canonical:home",
             "statistic_type": "Ball Possession", "statistic_value": 57,
             "provider": "highlightly"},
            {"fixture_id": "fixture:1", "team_id": "canonical:home",
             "statistic_type": "Unknown Metric", "statistic_value": 3,
             "provider": "highlightly"},
        ]
        profile = build_provider_neutral_team_profile(
            {"team_id": "canonical:home", "name": "Home FC"},
            [fixture], season_id="canonical:season", statistics=statistics,
        )
        quality = profile["data_quality"]
        history = profile["history_collection_diagnostics"]
        self.assertEqual(quality["fixtures_scanned"], 1)
        self.assertEqual(quality["matches_returned"], 1)
        self.assertEqual(quality["statistics_observations"], 1)
        self.assertIsNone(quality["statistics_raw_observations"])
        self.assertFalse(quality["statistics_raw_observations_available"])
        self.assertEqual(quality["statistics_unmapped_observations"], 1)
        self.assertIn("core_statistics_completeness_pct", quality)
        self.assertIn("statistics_coverage_by_metric", quality)
        self.assertEqual(history["history_collection_fetched_at"], "2026-11-12T10:00:00+00:00")
        self.assertEqual(history["history_repository_collected_at"], "2026-11-12T10:01:00+00:00")
        self.assertEqual(history["history_provider_updated_at"], "2026-11-12T09:59:00+00:00")
        self.assertEqual(history["matches_with_any_statistics"], 1)
        self.assertEqual(history["matches_with_complete_core_statistics"], 0)


    def test_accepts_layer2_statistic_aliases_across_providers(self):
        aliases = [
            ("Accurate Passes Percentage", 81, "Passes %"),
            ("Pass Success Percentage", 81, "Passes %"),
            ("Successful Passes Percentage", 81, "Passes %"),
            ("Goal Attempts", 13, "Total Shots"),
            ("Shots Off Target", 5, "Shots off Target"),
            ("Shots Blocked", 2, "Blocked Shots"),
        ]
        rows = [
            {"fixture_id": "fixture:1", "team_id": "canonical:home",
             "statistic_type": raw_type, "statistic_value": value,
             "provider": "independent_provider"}
            for raw_type, value, _canonical in aliases
        ]
        profile = build_provider_neutral_team_profile(
            {"team_id": "canonical:home", "name": "Home FC"},
            [_fixture("fixture:1")],
            season_id="canonical:season",
            statistics=rows,
        )
        observed = profile["matches"][0]["statistics"]
        for _raw_type, value, canonical in aliases:
            self.assertEqual(observed[canonical], float(value))
        self.assertEqual(profile["matches"][0]["statistics_unmapped_rows"], [])


    def test_derives_opponent_strength_from_canonical_completed_season_results(self):
        fixtures = [
            _fixture("home-beats-a", team_id="canonical:home", opponent_id="canonical:a",
                     days_ago=3, home_goals=2, away_goals=0),
            _fixture("b-beats-a", team_id="canonical:b", opponent_id="canonical:a",
                     days_ago=2, home_goals=3, away_goals=0),
            _fixture("home-beats-b", team_id="canonical:home", opponent_id="canonical:b",
                     days_ago=1, home_goals=1, away_goals=0),
        ]
        profile = build_provider_neutral_team_profile(
            {"team_id": "canonical:home", "name": "Home FC"},
            fixtures, season_id="canonical:season",
        )
        strengths = {m["opponent_id"]: m["opponent_strength"] for m in profile["matches"]}
        self.assertGreater(strengths["canonical:b"], strengths["canonical:a"])
        self.assertAlmostEqual(strengths["canonical:b"], 66.667, places=2)
        self.assertAlmostEqual(strengths["canonical:a"], 33.333, places=2)
        self.assertEqual(profile["data_quality"]["opponent_strength_teams_in_standings"], 3)

    def test_explicit_canonical_opponent_strength_map_takes_precedence(self):
        profile = build_provider_neutral_team_profile(
            {"team_id": "canonical:home", "name": "Home FC"},
            [_fixture("fixture:1")], season_id="canonical:season",
            opponent_strength={"canonical:away": 88.0},
        )
        self.assertEqual(profile["matches"][0]["opponent_strength"], 88.0)
        self.assertEqual(profile["data_quality"]["opponent_strength_source"],
                         "supplied_canonical_strength_map")


if __name__ == "__main__":
    unittest.main()
