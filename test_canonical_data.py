import unittest
from datetime import datetime, timezone

from canonical_data import (
    MatchNormalizationError, canonicalize_api_football_fixture,
    canonicalize_api_ninjas_match, canonicalize_highlightly_match,
    canonicalize_livescore_event, match_identity, merge_source_ids,
)


class CanonicalMatchTests(unittest.TestCase):
    def livescore(self):
        return {
            "id": "ls-900",
            "status": {"type": {"state": "post", "completed": True}},
            "competitions": [{
                "date": "2026-11-07T15:00:00Z",
                "competitors": [
                    {"id": "ls-team-1", "homeAway": "home", "score": "2",
                     "team": {"id": "ls-team-1", "name": "Arsenal FC"}},
                    {"id": "ls-team-2", "homeAway": "away", "score": "1",
                     "team": {"id": "ls-team-2", "name": "Chelsea"}},
                ],
            }],
        }

    def api_fixture(self):
        return {
            "fixture": {"id": 771, "date": "2026-11-07T15:02:00+00:00",
                        "status": {"short": "FT"}},
            "teams": {"home": {"id": 42, "name": "Arsenal"},
                      "away": {"id": 49, "name": "Chelsea FC"}},
            "goals": {"home": 2, "away": 1},
        }

    def test_live_score_normalizes_nested_competitors_and_score(self):
        result = canonicalize_livescore_event(
            self.livescore(), competition_key="eng-premier-league", season=2026
        )
        self.assertEqual(result["status"], "finished")
        self.assertEqual(result["home_score"], 2)
        self.assertEqual(result["home"]["source_ids"]["livescore_football"], "ls-team-1")

    def test_livescore_string_false_completion_flag_is_not_truthy_finished(self):
        event = self.livescore()
        event["status"]["type"] = {"state": "unknown", "completed": "false"}
        result = canonicalize_livescore_event(
            event, competition_key="eng-premier-league", season=2026
        )
        self.assertEqual(result["status"], "unknown")

    def test_livescore_true_boolean_completion_flag_marks_finished(self):
        event = self.livescore()
        event["status"]["type"] = {"state": "unknown", "completed": True}
        result = canonicalize_livescore_event(
            event, competition_key="eng-premier-league", season=2026
        )
        self.assertEqual(result["status"], "finished")

    def test_api_football_normalizes_fixture_shape(self):
        result = canonicalize_api_football_fixture(
            self.api_fixture(), competition_key="eng-premier-league", season=2026
        )
        self.assertEqual(result["source_ids"]["api_football"], "771")
        self.assertEqual(result["away_score"], 1)

    def test_match_identity_uses_competition_season_teams_and_kickoff_not_ids(self):
        left = canonicalize_livescore_event(
            self.livescore(), competition_key="eng-premier-league", season=2026
        )
        right = canonicalize_api_football_fixture(
            self.api_fixture(), competition_key="eng-premier-league", season=2026
        )
        self.assertTrue(match_identity(left, right, team_aliases={
            "Arsenal FC": "Arsenal", "Chelsea FC": "Chelsea"
        }))
        self.assertNotEqual(
            left["source_ids"]["livescore_football"],
            right["source_ids"]["api_football"],
        )

    def test_invalid_scores_remain_unknown_in_canonical_records(self):
        base = {
            "game_id": "epl-invalid-score",
            "season": 2026,
            "start_time": "2026-11-07T15:00:00Z",
            "status": "final",
            "home_team": {"team_id": "home-1", "name": "Arsenal"},
            "away_team": {"team_id": "away-1", "name": "Chelsea"},
            "home_score": 2,
            "away_score": 1,
        }
        for invalid in (-1, 1.5, True, "-1", "1.5", "not-a-score"):
            with self.subTest(invalid=invalid):
                row = {**base, "home_score": invalid}
                result = canonicalize_api_ninjas_match(
                    row, competition_key="eng-premier-league"
                )
                self.assertIsNone(result["home_score"])
                self.assertEqual(result["away_score"], 1)

    def test_whole_number_score_strings_remain_supported(self):
        row = {
            "game_id": "epl-string-score",
            "season": 2026,
            "start_time": "2026-11-07T15:00:00Z",
            "status": "final",
            "home_team": {"team_id": "home-1", "name": "Arsenal"},
            "away_team": {"team_id": "away-1", "name": "Chelsea"},
            "home_score": "2",
            "away_score": "1",
        }
        result = canonicalize_api_ninjas_match(
            row, competition_key="eng-premier-league"
        )
        self.assertEqual((result["home_score"], result["away_score"]), (2, 1))

    def test_api_ninjas_normalizes_documented_match_shape(self):
        row = {
            "game_id": "epl-20261107-ars-che",
            "season": 2026,
            "start_time": "2026-11-07T15:00:00Z",
            "status": "final",
            "home_team": {"team_id": "soccer-arsenal", "name": "Arsenal"},
            "away_team": {"team_id": "soccer-chelsea", "name": "Chelsea"},
            "home_score": 2,
            "away_score": 1,
            "updated_at": "2026-11-07T17:10:00Z",
        }
        result = canonicalize_api_ninjas_match(row, competition_key="eng-premier-league")
        self.assertEqual(result["status"], "finished")
        self.assertEqual(result["home_score"], 2)
        self.assertEqual(result["source_ids"]["api_ninjas"], row["game_id"])
        self.assertEqual(result["raw_source_updated_at"], row["updated_at"])

    def test_highlightly_normalizes_nested_match_shape_and_score(self):
        row = {
            "id": 9001,
            "date": "2026-11-07T15:00:00.000Z",
            "homeTeam": {"id": 11, "name": "Arsenal"},
            "awayTeam": {"id": 12, "name": "Chelsea"},
            "league": {"id": 99, "season": 2026, "name": "Premier League"},
            "state": {"description": "Finished", "score": {"current": "2 - 1"}},
            "updated_at": "2026-11-07T17:10:00Z",
        }
        result = canonicalize_highlightly_match(row, competition_key="eng-premier-league")
        self.assertEqual(result["status"], "finished")
        self.assertEqual((result["home_score"], result["away_score"]), (2, 1))
        self.assertEqual(result["source_ids"]["highlightly"], "9001")

    def test_highlightly_unparseable_score_remains_unknown(self):
        row = {
            "id": 9002, "date": "2026-11-07T15:00:00Z",
            "homeTeam": {"id": 11, "name": "Arsenal"},
            "awayTeam": {"id": 12, "name": "Chelsea"},
            "league": {"season": 2026},
            "state": {"description": "Not started", "score": {"current": None}},
        }
        result = canonicalize_highlightly_match(row, competition_key="eng-premier-league")
        self.assertIsNone(result["home_score"])
        self.assertIsNone(result["away_score"])
        self.assertEqual(result["status"], "scheduled")

    def test_api_ninjas_and_highlightly_records_match_by_identity_not_ids(self):
        ninjas = canonicalize_api_ninjas_match({
            "game_id": "epl-game-1", "season": 2026,
            "start_time": "2026-11-07T15:00:00Z", "status": "final",
            "home_team": {"team_id": "soccer-arsenal", "name": "Arsenal"},
            "away_team": {"team_id": "soccer-chelsea", "name": "Chelsea"},
            "home_score": 2, "away_score": 1,
        }, competition_key="eng-premier-league")
        highlightly = canonicalize_highlightly_match({
            "id": 9001, "date": "2026-11-07T15:03:00Z",
            "homeTeam": {"id": 11, "name": "Arsenal"},
            "awayTeam": {"id": 12, "name": "Chelsea"},
            "league": {"season": 2026},
            "state": {"description": "Finished", "score": {"current": "2 - 1"}},
        }, competition_key="eng-premier-league")
        self.assertTrue(match_identity(ninjas, highlightly))
        self.assertNotEqual(ninjas["source_ids"]["api_ninjas"], highlightly["source_ids"]["highlightly"])

    def test_competition_or_season_mismatch_prevents_join(self):
        left = canonicalize_livescore_event(
            self.livescore(), competition_key="eng-premier-league", season=2026
        )
        right = canonicalize_api_football_fixture(
            self.api_fixture(), competition_key="esp-la-liga", season=2026
        )
        self.assertFalse(match_identity(left, right))
        right["competition_key"] = "eng-premier-league"
        right["season"] = 2025
        self.assertFalse(match_identity(left, right))

    def test_home_away_swap_prevents_join(self):
        left = canonicalize_livescore_event(
            self.livescore(), competition_key="eng-premier-league", season=2026
        )
        right = canonicalize_api_football_fixture(
            self.api_fixture(), competition_key="eng-premier-league", season=2026
        )
        right["home"], right["away"] = right["away"], right["home"]
        self.assertFalse(match_identity(left, right))

    def test_missing_kickoff_fails_closed(self):
        with self.assertRaises(MatchNormalizationError):
            canonicalize_api_football_fixture(
                {"fixture": {}, "teams": {}, "goals": {}},
                competition_key="eng-premier-league", season=2026
            )

    def test_source_ids_are_namespaced(self):
        left = canonicalize_livescore_event(
            self.livescore(), competition_key="eng-premier-league", season=2026
        )
        right = canonicalize_api_football_fixture(
            self.api_fixture(), competition_key="eng-premier-league", season=2026
        )
        ids = merge_source_ids(left, right)
        self.assertEqual(ids["livescore_football"], "ls-900")
        self.assertEqual(ids["api_football"], "771")
        self.assertEqual(ids["home.livescore_football"], "ls-team-1")
        self.assertEqual(ids["home.api_football"], "42")

    def test_reconcile_selects_priority_and_records_conflicting_scores(self):
        from canonical_data import reconcile_match_pair
        left = canonicalize_livescore_event(
            self.livescore(), competition_key="eng-premier-league", season=2026
        )
        right = canonicalize_api_football_fixture(
            self.api_fixture(), competition_key="eng-premier-league", season=2026
        )
        right["home_score"] = 3
        collected_at = datetime(2026, 11, 7, 18, 0, tzinfo=timezone.utc)
        result = reconcile_match_pair(
            left, right, team_aliases={"Arsenal FC": "Arsenal", "Chelsea FC": "Chelsea"},
            fetched_at={"livescore_football": collected_at, "api_football": collected_at},
            now=datetime(2026, 11, 7, 18, 1, tzinfo=timezone.utc),
            livescore_verified=True,
        )
        self.assertEqual(result["home_score"], 2)
        self.assertEqual(result["reconciliation"]["home_score"]["provider"], "livescore_football")
        self.assertEqual(result["reconciliation"]["home_score"]["status"], "conflict")
        self.assertEqual(result["source_ids"]["api_football"], "771")

    def test_reconcile_excludes_records_without_collection_timestamps(self):
        from canonical_data import reconcile_match_pair
        left = canonicalize_livescore_event(
            self.livescore(), competition_key="eng-premier-league", season=2026
        )
        right = canonicalize_api_football_fixture(
            self.api_fixture(), competition_key="eng-premier-league", season=2026
        )
        result = reconcile_match_pair(
            left, right,
            team_aliases={"Arsenal FC": "Arsenal", "Chelsea FC": "Chelsea"},
            now=datetime(2026, 11, 7, 18, 0, tzinfo=timezone.utc),
            livescore_verified=True,
        )
        self.assertIsNone(result["home_score"])
        self.assertIsNone(result["away_score"])
        self.assertEqual(result["reconciliation"]["home_score"]["status"], "unknown")
        self.assertIsNone(result["reconciliation"]["home_score"]["provider"])

    def test_reconcile_excludes_stale_observations(self):
        from canonical_data import reconcile_match_pair
        left = canonicalize_livescore_event(
            self.livescore(), competition_key="eng-premier-league", season=2026
        )
        right = canonicalize_api_football_fixture(
            self.api_fixture(), competition_key="eng-premier-league", season=2026
        )
        result = reconcile_match_pair(
            left, right,
            team_aliases={"Arsenal FC": "Arsenal", "Chelsea FC": "Chelsea"},
            fetched_at={
                "livescore_football": datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc),
                "api_football": datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc),
            },
            now=datetime(2026, 11, 7, 18, 0, tzinfo=timezone.utc),
            max_age_seconds=86400,
            livescore_verified=True,
        )
        self.assertIsNone(result["home_score"])
        self.assertEqual(result["reconciliation"]["home_score"]["status"], "unknown")

    def test_reconcile_refuses_ambiguous_or_unmatched_records(self):
        from canonical_data import reconcile_match_pair
        left = canonicalize_livescore_event(
            self.livescore(), competition_key="eng-premier-league", season=2026
        )
        right = canonicalize_api_football_fixture(
            self.api_fixture(), competition_key="esp-la-liga", season=2026
        )
        self.assertIsNone(reconcile_match_pair(left, right))


if __name__ == "__main__":
    unittest.main()
