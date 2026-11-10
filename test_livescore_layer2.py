import unittest
from datetime import datetime, timezone

from livescore_layer2 import (
    apply_livescore_verified_result_fallback_to_profiles,
    collect_livescore_verified_result_fallback,
)


class FakeLiveScoreClient:
    def __init__(self, events_by_date, *, global_sync="2026-11-10T11:30:00Z",
                 competition_sync="2026-11-10T11:30:00Z"):
        self.events_by_date = events_by_date
        self.global_sync = global_sync
        self.competition_sync = competition_sync
        self.meta_calls = 0
        self.league_calls = 0
        self.fixture_calls = []

    def meta(self):
        self.meta_calls += 1
        return {
            "lastSuccessfulSyncAt": self.global_sync,
            "service": {"dataSource": "MongoDB"},
        }

    def leagues(self, kind="club", available=True):
        self.league_calls += 1
        return [{
            "slug": "eng.1",
            "name": "Premier League",
            "country": "England",
            "active": True,
            "season": {"year": 2026},
            "coverage": {
                "hasData": True,
                "lastSyncedAt": self.competition_sync,
            },
        }]

    def fixtures(self, league, **kwargs):
        self.fixture_calls.append((league, kwargs))
        return self.events_by_date.get(kwargs.get("date_from"), [])


def sm_fixture(fid=500, *, home_id=10, away_id=20, home="Coventry",
               away="Fulham", kickoff="2026-11-09T14:00:00Z", scores=None):
    if scores is None:
        scores = [
            {"participant_id": home_id, "description": "1ST_HALF", "score": {"goals": 1}},
            {"participant_id": away_id, "description": "1ST_HALF", "score": {"goals": 0}},
        ]
    return {
        "id": fid,
        "season_id": 2026,
        "league_id": 8,
        "state_id": 5,
        "starting_at": kickoff,
        "participants": [
            {"id": home_id, "name": home, "meta": {"location": "home"}},
            {"id": away_id, "name": away, "meta": {"location": "away"}},
        ],
        "scores": scores,
    }


def livescore_event(event_id="ls-500", *, home="Coventry", away="Fulham",
                    kickoff="2026-11-09T14:00:00Z", home_score=2, away_score=1):
    return {
        "id": event_id,
        "updatedAt": "2026-11-10T11:45:00Z",
        "status": {"type": {"state": "post", "completed": True}},
        "competitions": [{
            "date": kickoff,
            "competitors": [
                {
                    "id": f"{event_id}-home",
                    "homeAway": "home",
                    "team": {"name": home},
                    "score": home_score,
                },
                {
                    "id": f"{event_id}-away",
                    "homeAway": "away",
                    "team": {"name": away},
                    "score": away_score,
                },
            ],
        }],
    }


class LiveScoreLayer2FallbackTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
        self.competition = {
            "id": 8,
            "name": "Premier League",
            "country": {"name": "England"},
        }

    def collect(self, client, fixtures=None, selected_team_ids=None):
        return collect_livescore_verified_result_fallback(
            client,
            source_competition=self.competition,
            sportmonks_fixtures=fixtures or [sm_fixture()],
            selected_team_ids=selected_team_ids or {10, 20},
            competition_key="premier-league",
            season=2026,
            season_id=2026,
            now=self.now,
        )

    def test_fresh_exact_crosswalk_and_fixture_identity_allow_missing_score_fallback(self):
        client = FakeLiveScoreClient({
            "2026-11-09": [livescore_event()]
        })

        report = self.collect(client)

        self.assertEqual(report["status"], "completed")
        self.assertTrue(report["fallback_eligible"])
        self.assertEqual(report["livescore_slug"], "eng.1")
        self.assertEqual(len(report["verified_matches"]), 1)
        verified = report["verified_matches"][0]
        self.assertEqual(verified["home_score"], 2)
        self.assertEqual(verified["away_score"], 1)
        self.assertTrue(verified["crosswalk_verified"])
        self.assertTrue(verified["match_identity_verified"])
        self.assertEqual(verified["score_source_provider"], "livescore_football")
        self.assertEqual(client.fixture_calls[0][1]["date_from"], "2026-11-09")

    def test_stale_global_metadata_blocks_all_live_score_fallback(self):
        client = FakeLiveScoreClient(
            {"2026-11-09": [livescore_event()]},
            global_sync="2026-11-07T10:00:00Z",
        )

        report = self.collect(client)

        self.assertEqual(report["status"], "skipped")
        self.assertFalse(report["fallback_eligible"])
        self.assertEqual(report["verified_matches"], [])
        self.assertEqual(client.fixture_calls, [])

    def test_stale_competition_sync_blocks_fallback(self):
        client = FakeLiveScoreClient(
            {"2026-11-09": [livescore_event()]},
            competition_sync="2026-11-07T10:00:00Z",
        )

        report = self.collect(client)

        self.assertEqual(report["status"], "skipped")
        self.assertEqual(report["verified_matches"], [])
        self.assertEqual(client.fixture_calls, [])

    def test_stale_or_missing_event_timestamp_blocks_exact_score_fallback(self):
        stale_event = livescore_event()
        stale_event["updatedAt"] = "2026-11-07T10:00:00Z"
        missing_timestamp_event = livescore_event(event_id="missing-timestamp")
        missing_timestamp_event.pop("updatedAt")
        client = FakeLiveScoreClient({
            "2026-11-09": [stale_event, missing_timestamp_event]
        })

        report = self.collect(client)

        self.assertEqual(report["verified_matches"], [])
        self.assertEqual(report["stale_or_unverifiable_event_matches"], 2)
        self.assertEqual(report["status"], "no_exact_fresh_livescore_matches")

    def test_valid_current_sportmonks_scores_are_never_overwritten(self):
        current_scores = [
            {"participant_id": 10, "description": "CURRENT", "score": {"goals": 2}},
            {"participant_id": 20, "description": "CURRENT", "score": {"goals": 1}},
        ]
        client = FakeLiveScoreClient({"2026-11-09": [livescore_event(home_score=3)]})

        report = self.collect(client, fixtures=[sm_fixture(scores=current_scores)])

        self.assertEqual(report["status"], "no_missing_completed_scores")
        self.assertEqual(report["verified_matches"], [])
        self.assertEqual(client.meta_calls, 0)
        self.assertEqual(client.fixture_calls, [])

    def test_wrong_team_or_kickoff_does_not_match(self):
        client = FakeLiveScoreClient({
            "2026-11-09": [
                livescore_event(home="Different Club"),
                livescore_event(event_id="late", kickoff="2026-11-09T14:20:00Z"),
            ]
        })

        report = self.collect(client)

        self.assertEqual(report["verified_matches"], [])
        self.assertEqual(report["status"], "no_exact_fresh_livescore_matches")

    def test_invalid_livescore_scores_are_rejected(self):
        client = FakeLiveScoreClient({
            "2026-11-09": [livescore_event(home_score=True, away_score=1.5)]
        })

        report = self.collect(client)

        self.assertEqual(report["verified_matches"], [])

    def test_multiple_exact_livescore_events_are_ambiguous(self):
        client = FakeLiveScoreClient({
            "2026-11-09": [
                livescore_event(event_id="one"),
                livescore_event(event_id="two"),
            ]
        })

        report = self.collect(client)

        self.assertEqual(report["verified_matches"], [])

    def test_one_date_request_is_reused_for_multiple_missing_score_fixtures(self):
        fixtures = [
            sm_fixture(fid=500, home_id=10, away_id=20, home="Coventry", away="Fulham"),
            sm_fixture(fid=501, home_id=10, away_id=30, home="Coventry", away="Chelsea"),
        ]
        events = [
            livescore_event(event_id="ls-500", home="Coventry", away="Fulham"),
            livescore_event(event_id="ls-501", home="Coventry", away="Chelsea"),
        ]
        client = FakeLiveScoreClient({"2026-11-09": events})

        report = self.collect(client, fixtures=fixtures, selected_team_ids={10})

        self.assertEqual(len(report["verified_matches"]), 2)
        self.assertEqual(report["date_requests"], 1)
        self.assertEqual(report["date_cache_hits"], 1)
        self.assertEqual(len(client.fixture_calls), 1)

    def test_verified_livescore_scores_are_added_without_changing_tvd_evidence(self):
        client = FakeLiveScoreClient({"2026-11-09": [livescore_event()]})
        report = self.collect(client)
        home = {
            "id": 10, "name": "Coventry", "matches": [],
            "tactical_evidence": {"source": "primary_only"},
        }
        away = {
            "id": 20, "name": "Fulham", "matches": [],
            "tactical_evidence": {"source": "primary_only"},
        }

        result = apply_livescore_verified_result_fallback_to_profiles(
            [home, away], report["verified_matches"]
        )

        self.assertEqual(result["matches_added"], 2)
        self.assertEqual(home["matches"][0]["goals_for"], 2)
        self.assertEqual(home["matches"][0]["goals_against"], 1)
        self.assertEqual(away["matches"][0]["goals_for"], 1)
        self.assertEqual(away["matches"][0]["goals_against"], 2)
        self.assertEqual(
            home["matches"][0]["result_verification"]["score_source_provider"],
            "livescore_football",
        )
        self.assertEqual(home["tactical_evidence"], {"source": "primary_only"})
        self.assertEqual(
            home["data_quality"]["history_source"],
            "cockroachdb_plus_verified_livescore_result_fallback",
        )

    def test_duplicate_livescore_result_is_not_appended_twice(self):
        client = FakeLiveScoreClient({"2026-11-09": [livescore_event()]})
        report = self.collect(client)
        profile = {
            "id": 10,
            "name": "Coventry",
            "matches": [{"fixture_id": 500, "date": "2026-11-09T14:00:00+00:00"}],
        }

        result = apply_livescore_verified_result_fallback_to_profiles(
            [profile], report["verified_matches"]
        )

        self.assertEqual(result["matches_added"], 0)
        self.assertEqual(result["duplicates_skipped"], 1)
        self.assertEqual(len(profile["matches"]), 1)


if __name__ == "__main__":
    unittest.main()
