import unittest
from datetime import datetime, timezone, timedelta

from canonical_data import canonicalize_api_ninjas_match, canonicalize_highlightly_match, canonicalize_api_football_fixture
from multi_source_reconciliation import reconcile_match_records

NOW = datetime(2026, 11, 7, 18, 0, tzinfo=timezone.utc)


class MultiSourceReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.ninjas = canonicalize_api_ninjas_match({
            "game_id": "ninjas-1", "season": 2026,
            "start_time": "2026-11-07T15:00:00Z", "status": "final",
            "home_team": {"team_id": "ars-n", "name": "Arsenal"},
            "away_team": {"team_id": "che-n", "name": "Chelsea"},
            "home_score": 2, "away_score": 1,
        }, competition_key="eng-premier-league")
        self.highlightly = canonicalize_highlightly_match({
            "id": 22, "date": "2026-11-07T15:02:00Z",
            "homeTeam": {"id": 10, "name": "Arsenal"},
            "awayTeam": {"id": 11, "name": "Chelsea"},
            "league": {"season": 2026},
            "state": {"description": "Finished", "score": {"current": "2 - 1"}},
        }, competition_key="eng-premier-league")
        self.api_football = canonicalize_api_football_fixture({
            "fixture": {"id": 33, "date": "2026-11-07T15:01:00Z", "status": {"short": "FT"}},
            "teams": {"home": {"id": 1, "name": "Arsenal"}, "away": {"id": 2, "name": "Chelsea"}},
            "goals": {"home": 3, "away": 1},
        }, competition_key="eng-premier-league", season=2026)
        self.fetched = {name: NOW - timedelta(minutes=2) for name in
                        ("api_ninjas", "highlightly", "api_football")}

    def test_three_sources_select_priority_and_report_all_agreement_and_conflict(self):
        result = reconcile_match_records(
            [self.ninjas, self.highlightly, self.api_football],
            fetched_at=self.fetched, now=NOW,
        )
        self.assertEqual(result["home_score"], 2)
        self.assertEqual(result["reconciliation"]["home_score"]["provider"], "highlightly")
        self.assertEqual(result["reconciliation"]["home_score"]["status"], "conflict")
        self.assertEqual(result["reconciliation"]["home_score"]["corroborating_providers"], ["api_ninjas"])
        self.assertEqual(result["reconciliation"]["home_score"]["conflicting_providers"], ["api_football"])
        observed = {row["provider"]: row["value"] for row in result["reconciliation"]["home_score"]["observations"]}
        self.assertEqual(observed, {"api_ninjas": 2, "highlightly": 2, "api_football": 3})
        self.assertTrue(all(row.get("source_id") for row in result["reconciliation"]["home_score"]["observations"]))
        self.assertEqual(set(result["source_ids"]), {"api_ninjas", "highlightly", "api_football"})

    def test_missing_fetched_timestamp_is_not_treated_as_fresh(self):
        result = reconcile_match_records(
            [self.ninjas, self.highlightly], now=NOW,
        )
        self.assertIsNone(result["home_score"])
        self.assertEqual(result["reconciliation"]["home_score"]["status"], "unknown")

    def test_stale_provider_is_excluded(self):
        fetched = dict(self.fetched)
        fetched["api_football"] = NOW - timedelta(days=3)
        result = reconcile_match_records(
            [self.ninjas, self.highlightly, self.api_football],
            fetched_at=fetched, now=NOW, max_age_seconds=3600,
        )
        self.assertEqual(result["reconciliation"]["home_score"]["conflicting_providers"], [])

    def test_duplicate_provider_cannot_vote_twice(self):
        self.assertIsNone(reconcile_match_records(
            [self.ninjas, dict(self.ninjas)], fetched_at=self.fetched, now=NOW,
        ))

    def test_any_identity_mismatch_rejects_the_whole_group(self):
        wrong = dict(self.api_football)
        wrong["competition_key"] = "esp-la-liga"
        self.assertIsNone(reconcile_match_records(
            [self.ninjas, self.highlightly, wrong],
            fetched_at=self.fetched, now=NOW,
        ))

    def test_livescore_is_not_promoted_without_explicit_verification(self):
        from canonical_data import canonicalize_livescore_event
        live = canonicalize_livescore_event({
            "id": "ls-1", "status": {"type": {"state": "post", "completed": True}},
            "competitions": [{"date": "2026-11-07T15:00:00Z", "competitors": [
                {"id": "h", "homeAway": "home", "score": "1", "team": {"name": "Arsenal"}},
                {"id": "a", "homeAway": "away", "score": "1", "team": {"name": "Chelsea"}},
            ]}],
        }, competition_key="eng-premier-league", season=2026)
        fetched = dict(self.fetched, livescore_football=NOW - timedelta(minutes=1))
        result = reconcile_match_records(
            [live, self.ninjas, self.highlightly], fetched_at=fetched, now=NOW,
        )
        self.assertEqual(result["reconciliation"]["home_score"]["provider"], "highlightly")
        result_verified = reconcile_match_records(
            [live, self.ninjas, self.highlightly], fetched_at=fetched, now=NOW,
            livescore_verified=True,
        )
        self.assertEqual(result_verified["reconciliation"]["home_score"]["provider"], "livescore_football")


if __name__ == "__main__":
    unittest.main()
