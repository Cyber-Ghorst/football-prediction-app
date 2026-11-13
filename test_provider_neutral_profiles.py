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
        self.assertIsNone(profile["matches"][0]["opponent_strength"])
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


if __name__ == "__main__":
    unittest.main()
