import unittest
from datetime import datetime, timezone

from openscores_normalizer import normalize_openscores_fixtures


class OpenScoresNormalizerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = {
            "id": 501,
            "season_id": 2026,
            "scheduled_kickoff_at": "2026-11-12T18:30:00Z",
            "status": "scheduled",
            "home_team": {"id": 10, "name": "Home FC"},
            "away_team": {"id": 20, "name": "Away FC"},
            "score": {"home_ft_score": None, "away_ft_score": None},
            "source_ids": {"flashscore": "fs-501"},
        }

    def test_normalizes_observed_openscores_fixture_shape(self):
        result = normalize_openscores_fixtures(
            [self.fixture], league_id=7, season_id=2026,
            retrieved_at_utc="2026-11-10T17:00:00Z",
        )
        self.assertEqual(result["fixtures_normalized"], 1)
        row = result["fixtures"][0]
        self.assertEqual(row["provider_fixture_id"], "501")
        self.assertEqual(row["provider_league_id"], "7")
        self.assertEqual(row["provider_season_id"], "2026")
        self.assertEqual(row["provider_home_team_id"], "10")
        self.assertEqual(row["provider_away_team_id"], "20")
        self.assertEqual(row["kickoff_utc"], datetime(2026, 11, 12, 18, 30, tzinfo=timezone.utc))
        self.assertEqual(row["source_ids"], {"flashscore": "fs-501"})
        self.assertEqual(row["reconciliation_status"], "pending_entity_mapping")

    def test_normalizes_scores_without_inventing_missing_values(self):
        item = dict(self.fixture)
        item["score"] = {"home_ft_score": 2, "away_ft_score": 1}
        row = normalize_openscores_fixtures([item], league_id=7, season_id=2026)["fixtures"][0]
        self.assertEqual((row["home_goals"], row["away_goals"]), (2, 1))

    def test_preserves_explicit_zero_score_values(self):
        item = dict(self.fixture)
        item["score"] = {"home_ft_score": {"value": 0}, "away_ft_score": {"value": 2}}
        row = normalize_openscores_fixtures([item], league_id=7, season_id=2026)["fixtures"][0]
        self.assertEqual((row["home_goals"], row["away_goals"]), (0, 2))

    def test_rejects_mismatched_season_context(self):
        item = dict(self.fixture, season_id=2025)
        result = normalize_openscores_fixtures([item], league_id=7, season_id=2026)
        self.assertEqual(result["fixtures_normalized"], 0)
        self.assertEqual(result["rejected"]["missing_or_invalid_season"], 1)

    def test_rejects_invalid_kickoff_and_missing_team_ids(self):
        invalid_time = dict(self.fixture, scheduled_kickoff_at="not-a-time")
        missing_team = dict(self.fixture, home_team={"name": "Home FC"})
        result = normalize_openscores_fixtures(
            [invalid_time, missing_team], league_id=7, season_id=2026
        )
        self.assertEqual(result["rejected"]["missing_or_invalid_kickoff"], 1)
        self.assertEqual(result["rejected"]["missing_home_team_identity"], 1)

    def test_deduplicates_fixture_ids_and_rejects_same_team_on_both_sides(self):
        duplicate = dict(self.fixture)
        same_team = dict(self.fixture, away_team={"id": 10, "name": "Home FC"})
        result = normalize_openscores_fixtures(
            [self.fixture, duplicate, same_team], league_id=7, season_id=2026
        )
        self.assertEqual(result["fixtures_normalized"], 1)
        self.assertEqual(result["rejected"]["duplicate_fixture_id"], 1)
        self.assertEqual(result["rejected"]["same_home_and_away_team"], 1)

    def test_rejects_non_records_and_requires_competition_context(self):
        result = normalize_openscores_fixtures(
            [None, "bad"], league_id=7, season_id=2026
        )
        self.assertEqual(result["rejected"]["not_a_record"], 2)
        with self.assertRaises(ValueError):
            normalize_openscores_fixtures([], league_id=None, season_id=2026)


if __name__ == "__main__":
    unittest.main()
