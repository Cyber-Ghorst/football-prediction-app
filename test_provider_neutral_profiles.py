from datetime import datetime, timedelta, timezone
import unittest

from provider_neutral_profiles import build_provider_neutral_team_profile


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
        self.assertEqual(
            profile["matches"][0]["statistics"], {"Ball Possession": 57}
        )


if __name__ == "__main__":
    unittest.main()
