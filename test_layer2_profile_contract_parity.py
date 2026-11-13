"""Controlled Layer 2 parity tests using identical synthetic match evidence.

This compares shared profile outputs only. Provider-specific raw diagnostics are
intentionally not required to match.
"""
from datetime import datetime, timezone
import unittest

from provider_neutral_profiles import build_provider_neutral_team_profile
from sportmonks_layer2 import collect_sportmonks_team_profile


SEASON = "canonical:season"
TEAM = "canonical:home"
OPPONENT = "canonical:away"


def _paired_evidence():
    canonical_fixtures = []
    canonical_statistics = []
    sportmonks_fixtures = []

    for day in range(1, 16):
        kickoff = datetime(2026, 10, day, 15, 0, tzinfo=timezone.utc)
        team_is_home = day % 2 == 0
        home_id, away_id = (10, 20) if team_is_home else (20, 10)
        team_goals_for = (day % 4) + 1
        team_goals_against = day % 3
        home_goals, away_goals = (
            (team_goals_for, team_goals_against)
            if team_is_home else (team_goals_against, team_goals_for)
        )
        fixture_id = f"fixture:{day}"

        canonical_fixtures.append({
            "fixture_id": fixture_id,
            "season_id": SEASON,
            "status": "finished",
            "home_team_id": TEAM if team_is_home else OPPONENT,
            "away_team_id": OPPONENT if team_is_home else TEAM,
            "home_team": "Home FC" if team_is_home else "Away FC",
            "away_team": "Away FC" if team_is_home else "Home FC",
            "starting_at": kickoff.isoformat(),
            "home_goals": home_goals,
            "away_goals": away_goals,
            "source_provider": "independent_test_feed",
        })

        team_counterattacks = float(day + 1)
        opponent_counterattacks = float(day * 2)
        canonical_statistics.extend([
            {"fixture_id": fixture_id, "team_id": TEAM,
             "statistic_type": "Counter Attacks",
             "statistic_value": team_counterattacks, "provider": "independent_test_feed"},
            {"fixture_id": fixture_id, "team_id": OPPONENT,
             "statistic_type": "Counter Attacks",
             "statistic_value": opponent_counterattacks, "provider": "independent_test_feed"},
        ])

        sportmonks_fixtures.append({
            "id": day,
            "season_id": 2026,
            "starting_at": kickoff.isoformat(),
            "starting_at_timestamp": int(kickoff.timestamp()),
            "state": {"short_name": "FT", "name": "Finished"},
            "participants": [
                {"id": home_id, "name": "Home FC" if team_is_home else "Away FC",
                 "meta": {"location": "home"}},
                {"id": away_id, "name": "Away FC" if team_is_home else "Home FC",
                 "meta": {"location": "away"}},
            ],
            "scores": [
                {"participant_id": home_id, "description": "CURRENT",
                 "score": {"goals": home_goals}},
                {"participant_id": away_id, "description": "CURRENT",
                 "score": {"goals": away_goals}},
            ],
            "statistics": [
                {"participant_id": 10, "type": {"id": 1527, "name": "Counter Attacks"},
                 "data": {"value": team_counterattacks}},
                {"participant_id": 20, "type": {"id": 1527, "name": "Counter Attacks"},
                 "data": {"value": opponent_counterattacks}},
            ],
        })

    return canonical_fixtures, canonical_statistics, sportmonks_fixtures


class Layer2ProfileContractParityTests(unittest.TestCase):
    def test_shared_layer2_outputs_match_for_identical_evidence(self):
        canonical_fixtures, canonical_statistics, sportmonks_fixtures = _paired_evidence()

        canonical = build_provider_neutral_team_profile(
            {"team_id": TEAM, "name": "Home FC"},
            canonical_fixtures,
            season_id=SEASON,
            statistics=canonical_statistics,
            opponent_strength={OPPONENT: 100.0},
        )
        sportmonks = collect_sportmonks_team_profile(
            {"id": 10, "name": "Home FC"},
            2026,
            sportmonks_fixtures,
            [{"participant_id": 10, "position": 2},
             {"participant_id": 20, "position": 1}],
        )

        self.assertEqual(len(canonical["matches"]), 10)
        self.assertEqual(len(sportmonks["matches"]), 10)
        self.assertEqual(
            [row["date"] for row in canonical["matches"]],
            [row["date"] for row in sportmonks["matches"]],
        )
        self.assertEqual(
            [(row["venue"], row["goals_for"], row["goals_against"])
             for row in canonical["matches"]],
            [(row["venue"], row["goals_for"], row["goals_against"])
             for row in sportmonks["matches"]],
        )
        self.assertEqual(
            [row["opponent_strength"] for row in canonical["matches"]],
            [row["opponent_strength"] for row in sportmonks["matches"]],
        )

        self.assertEqual(canonical["form_summary"], sportmonks["form_summary"])
        self.assertEqual(canonical["home_rating"], sportmonks["home_rating"])
        self.assertEqual(canonical["away_rating"], sportmonks["away_rating"])

        for left, right in zip(canonical["matches"], sportmonks["matches"]):
            self.assertEqual(left["statistics"], right["statistics"])
            self.assertEqual(left["opponent_statistics"], right["opponent_statistics"])

        self.assertEqual(
            canonical["tactical_evidence"]["weapons"]["counterattack_threat"],
            sportmonks["tactical_evidence"]["weapons"]["counterattack_threat"],
        )
        self.assertEqual(
            canonical["tactical_evidence"]["vulnerabilities"]["transition_recovery"],
            sportmonks["tactical_evidence"]["vulnerabilities"]["transition_recovery"],
        )
        for profile in (canonical, sportmonks):
            self.assertEqual(
                profile["tactical_evidence"]["evidence_metadata"]["latest_five_weight"],
                0.60,
            )
            self.assertEqual(
                profile["tactical_evidence"]["evidence_metadata"]["previous_five_weight"],
                0.40,
            )
            self.assertIsNone(profile["player_availability"])
            self.assertFalse(profile["lineups"]["lineups_available"])

    def test_contract_comparison_does_not_require_provider_specific_diagnostics_to_match(self):
        canonical_fixtures, canonical_statistics, sportmonks_fixtures = _paired_evidence()
        canonical = build_provider_neutral_team_profile(
            {"team_id": TEAM, "name": "Home FC"}, canonical_fixtures,
            season_id=SEASON, statistics=canonical_statistics,
            opponent_strength={OPPONENT: 100.0},
        )
        sportmonks = collect_sportmonks_team_profile(
            {"id": 10, "name": "Home FC"}, 2026, sportmonks_fixtures,
            [{"participant_id": 10, "position": 2},
             {"participant_id": 20, "position": 1}],
        )

        self.assertEqual(canonical["data_quality"]["matches_returned"], 10)
        self.assertEqual(sportmonks["data_quality"]["matches_returned"], 10)
        self.assertEqual(canonical["history_collection_diagnostics"]["history_order"],
                         "newest_first_by_parsed_utc_kickoff")
        self.assertEqual(sportmonks["history_collection_diagnostics"]["history_order"],
                         "newest_first_by_parsed_utc_kickoff")
        self.assertEqual(canonical["data_quality"]["provider"], "canonical_repository")
        self.assertEqual(sportmonks["data_quality"]["provider"], "sportmonks")


if __name__ == "__main__":
    unittest.main()
