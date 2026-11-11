import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from free_fixture_observation_pipeline import (
    collect_bzzoiro_observations,
    collect_highlightly_observations,
    collect_api_ninjas_observations,
    collect_livescore_observations,
    collect_openfootball_observations,
    collect_openligadb_observations,
    collect_openmatchday_observations,
)


class FreeFixtureObservationPipelineTests(unittest.TestCase):
    @patch("free_fixture_observation_pipeline.archive_future_fixture_observations")
    def test_openligadb_scope_is_normalized_and_archived(self, archive):
        archive.return_value = {"snapshot_id": "snapshot-1"}
        client = Mock()
        client.matches.return_value = [{
            "provider": "openligadb", "provider_fixture_id": "42",
            "eligible_for_review": True,
        }]
        result = collect_openligadb_observations(
            "provider-db", [{
                "league_shortcut": "bl1", "season": 2026,
                "country": "Germany", "competition_name": "Bundesliga",
                "provider_competition_id": 1,
            }],
            client=client,
        )
        client.matches.assert_called_once_with(
            "bl1", 2026,
            league_metadata={
                "league_shortcut": "bl1", "season": 2026,
                "country": "Germany", "competition_name": "Bundesliga",
                "provider_competition_id": 1,
            },
        )
        self.assertTrue(result["archived"])
        self.assertEqual(result["snapshot_id"], "snapshot-1")
        self.assertEqual(archive.call_args.kwargs["provider"], "openligadb")

    @patch("free_fixture_observation_pipeline.archive_future_fixture_observations")
    def test_openfootball_multiple_datasets_are_archived_together(self, archive):
        archive.return_value = {"snapshot_id": "snapshot-2"}
        client = Mock()
        client.season.side_effect = [
            [{"provider": "openfootball", "provider_fixture_id": "a", "eligible_for_review": False}],
            [{"provider": "openfootball", "provider_fixture_id": "b", "eligible_for_review": True}],
        ]
        result = collect_openfootball_observations(
            "provider-db",
            [
                {"season_file": "2026-27/en.1.json", "competition": "Premier League"},
                {"season_file": "2026-27/de.1.json", "competition": "Bundesliga"},
            ],
            client=client,
        )
        self.assertEqual(client.season.call_count, 2)
        self.assertEqual(result["observation_count"], 2)
        self.assertEqual(result["eligible_for_review_count"], 1)
        self.assertEqual(archive.call_args.kwargs["request_params"]["datasets"][0]["season_file"],
                         "2026-27/en.1.json")

    @patch("free_fixture_observation_pipeline.archive_future_fixture_observations")
    def test_openmatchday_csv_rows_are_archived_without_promoting_them(self, archive):
        archive.return_value = {"snapshot_id": "snapshot-3"}
        client = Mock()
        client.season_csv.return_value = [{
            "provider": "open_matchday", "provider_fixture_id": "dataset:key",
            "eligible_for_review": False,
            "exclusion_reason": "kickoff_missing_timezone_or_precision",
        }]
        result = collect_openmatchday_observations(
            "provider-db",
            [{"url": "https://raw.githubusercontent.com/oladeeayo/open-matchday/main/data/a.csv",
              "competition": "League", "season": "2627"}],
            client=client,
        )
        self.assertTrue(result["archived"])
        self.assertEqual(result["eligible_for_review_count"], 0)
        self.assertEqual(archive.call_args.kwargs["observations"][0]["eligible_for_review"], False)

    @patch("free_fixture_observation_pipeline.archive_future_fixture_observations")
    def test_livescore_normalizes_scheduled_events_before_archiving(self, archive):
        archive.return_value = {"snapshot_id": "snapshot-4"}
        client = Mock()
        client.base_url = "https://worldcup26.ir"
        client.leagues.return_value = [{
            "id": "league-1", "slug": "league-1", "name": "Premier League",
            "country": "England", "lastSyncedAt": "2026-11-11T01:30:00Z",
        }]
        client.fixtures.return_value = [{
            "id": "event-9",
            "date": "2026-11-20T19:00:00+00:00",
            "status": {"type": {"name": "STATUS_SCHEDULED"}},
            "season": {"id": "season-26"},
            "competitions": [{"id": "league-1", "competitors": [
                {"homeAway": "home", "team": {"id": "1", "displayName": "Home FC"}},
                {"homeAway": "away", "team": {"id": "2", "displayName": "Away FC"}},
            ]}],
        }]
        result = collect_livescore_observations(
            "provider-db", ["league-1"], date_from="2026-11-11", date_to="2026-11-18",
            client=client,
        )
        client.fixtures.assert_called_once_with(
            "league-1", status="scheduled", date_from="20261111", date_to="20261118"
        )
        self.assertEqual(archive.call_args.kwargs["request_params"]["date_from"], "2026-11-11")
        self.assertEqual(archive.call_args.kwargs["request_params"]["api_date_from"], "20261111")
        self.assertEqual(result["eligible_for_review_count"], 1)
        self.assertEqual(archive.call_args.kwargs["observations"][0]["provider_fixture_id"], "event-9")
        self.assertEqual(archive.call_args.kwargs["observations"][0]["source_sync_at"], "2026-11-11T01:30:00Z")
        self.assertEqual(archive.call_args.kwargs["observations"][0]["competition_name"], "Premier League")
        self.assertEqual(archive.call_args.kwargs["observations"][0]["raw_payload"]["country"], "England")
        client.leagues.assert_called_once_with(kind="all", available=True)

    def test_livescore_rejects_invalid_or_reversed_date_ranges(self):
        client = Mock()
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            collect_livescore_observations(
                "provider-db", ["eng.1"], date_from="20261111", date_to="2026-11-18",
                client=client,
            )
        with self.assertRaisesRegex(ValueError, "must not precede"):
            collect_livescore_observations(
                "provider-db", ["eng.1"], date_from="2026-11-18", date_to="2026-11-11",
                client=client,
            )
        client.fixtures.assert_not_called()

    @patch("free_fixture_observation_pipeline.archive_future_fixture_observations")
    def test_bzzoiro_requires_credentials_but_fails_closed_without_them(self, archive):
        result = collect_bzzoiro_observations("provider-db")
        self.assertFalse(result["archived"])
        self.assertEqual(result["observation_count"], 0)
        self.assertIn("BZZOIRO_API_TOKEN", result["errors"][0]["error"])
        archive.assert_not_called()

    @patch("free_fixture_observation_pipeline.archive_future_fixture_observations")
    def test_bzzoiro_forces_upcoming_status_and_archives(self, archive):
        archive.return_value = {"snapshot_id": "snapshot-bzz"}
        client = Mock()
        client.upcoming.return_value = [{
            "provider": "bzzoiro", "provider_fixture_id": "event-10",
            "eligible_for_review": True,
        }]
        result = collect_bzzoiro_observations(
            "provider-db", params={"league_id": 10, "status": "finished"},
            client=client,
        )
        self.assertEqual(client.upcoming.call_args.kwargs["params"]["status"], "upcoming")
        self.assertEqual(archive.call_args.kwargs["request_params"]["status"], "upcoming")
        self.assertEqual(result["eligible_for_review_count"], 1)

    @patch("free_fixture_observation_pipeline.archive_future_fixture_observations")
    def test_bzzoiro_report_counts_exclusion_reasons(self, archive):
        archive.return_value = {"snapshot_id": "snapshot-bzz-diagnostics"}
        client = Mock()
        client.upcoming.return_value = [
            {"provider": "bzzoiro", "provider_fixture_id": "1",
             "eligible_for_review": False,
             "exclusion_reason": "kickoff_missing_timezone_or_precision"},
            {"provider": "bzzoiro", "provider_fixture_id": "2",
             "eligible_for_review": False,
             "exclusion_reason": "not_scheduled"},
            {"provider": "bzzoiro", "provider_fixture_id": "3",
             "eligible_for_review": True},
        ]
        result = collect_bzzoiro_observations("provider-db", client=client)
        self.assertEqual(result["observation_count"], 3)
        self.assertEqual(result["eligible_for_review_count"], 1)
        self.assertEqual(result["exclusion_reason_counts"], {
            "kickoff_missing_timezone_or_precision": 1,
            "not_scheduled": 1,
        })

    @patch("free_fixture_observation_pipeline.archive_future_fixture_observations")
    def test_failed_provider_scope_does_not_archive_empty_success(self, archive):
        client = Mock()
        client.matches.side_effect = RuntimeError("upstream unavailable")
        result = collect_openligadb_observations(
            "provider-db", [{"league_shortcut": "bl1", "season": 2026}],
            client=client,
        )
        self.assertFalse(result["archived"])
        self.assertEqual(len(result["errors"]), 1)
        archive.assert_not_called()


    @patch("free_fixture_observation_pipeline.load_provider_observation_snapshots", return_value=[])
    @patch("free_fixture_observation_pipeline.archive_future_fixture_observations")
    def test_highlightly_collects_each_utc_day_and_archives_observations(
        self, archive, snapshots
    ):
        archive.return_value = {"snapshot_id": "highlightly-snapshot"}
        client = Mock()
        client.base_url = "https://soccer.highlightly.net"
        client.last_metadata = {}
        kickoff = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat().replace("+00:00", "Z")
        client.matches.return_value = [{
            "id": 1001, "date": kickoff,
            "country": {"code": "GB", "name": "England"},
            "homeTeam": {"id": 1, "name": "Home FC"},
            "awayTeam": {"id": 2, "name": "Away FC"},
            "league": {"id": 8, "season": 2026, "name": "Premier League"},
            "state": {"description": "Not started"},
        }]
        result = collect_highlightly_observations(
            "provider-db", date_from=datetime.now(timezone.utc).date().isoformat(),
            days=2, client=client,
        )
        self.assertEqual(client.matches.call_count, 2)
        self.assertEqual(result["provider"], "highlightly")
        self.assertEqual(result["observation_count"], 2)
        self.assertTrue(result["archived"])
        self.assertEqual(archive.call_args.kwargs["provider"], "highlightly")
        self.assertEqual(archive.call_args.kwargs["observations"][0]["provider_fixture_id"], "1001")

    @patch("free_fixture_observation_pipeline.load_provider_observation_snapshots")
    @patch("free_fixture_observation_pipeline.archive_future_fixture_observations")
    def test_highlightly_skips_api_calls_inside_quota_cooldown(self, archive, snapshots):
        snapshots.return_value = [{
            "retrieved_at": datetime(2026, 11, 11, 10, 0, tzinfo=timezone.utc),
        }]
        client = Mock()
        report = collect_highlightly_observations(
            "provider-db", date_from="2026-11-11", days=7, client=client,
            now=datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc),
            cooldown_hours=23,
        )
        self.assertEqual(report["skipped"], "refresh_cooldown")
        self.assertEqual(report["last_successful_snapshot_at"], "2026-11-11T10:00:00+00:00")
        client.matches.assert_not_called()
        archive.assert_not_called()

    @patch("free_fixture_observation_pipeline.load_provider_observation_snapshots")
    @patch("free_fixture_observation_pipeline.archive_future_fixture_observations")
    def test_highlightly_refreshes_after_quota_cooldown(self, archive, snapshots):
        snapshots.return_value = [{
            "retrieved_at": datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc),
        }]
        archive.return_value = {"snapshot_id": "highlightly-refresh"}
        client = Mock()
        client.base_url = "https://soccer.highlightly.net"
        client.last_metadata = {}
        client.matches.return_value = []
        report = collect_highlightly_observations(
            "provider-db", date_from="2026-11-11", days=1, client=client,
            now=datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc),
            cooldown_hours=23,
        )
        self.assertEqual(client.matches.call_count, 1)
        self.assertTrue(report["archived"])
        archive.assert_called_once()

    @patch("free_fixture_observation_pipeline.load_provider_observation_snapshots")
    def test_highlightly_fails_closed_if_cooldown_state_cannot_be_read(self, snapshots):
        snapshots.side_effect = RuntimeError("database unavailable")
        client = Mock()
        report = collect_highlightly_observations(
            "provider-db", date_from="2026-11-11", days=7, client=client,
            now=datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(report["skipped"], "cooldown_state_unavailable")
        self.assertEqual(report["observation_count"], 0)
        self.assertEqual(len(report["errors"]), 1)
        client.matches.assert_not_called()

    @patch("free_fixture_observation_pipeline.archive_future_fixture_observations")
    def test_api_ninjas_collects_only_documented_free_leagues(self, archive):
        archive.return_value = {"snapshot_id": "ninjas-snapshot"}
        client = Mock()
        kickoff = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace("+00:00", "Z")
        client.matches.side_effect = [[{
            "game_id": "epl-game-1", "league": "epl", "season": 2026,
            "start_time": kickoff, "status": "scheduled",
            "home_team": {"team_id": "home-1", "name": "Home FC"},
            "away_team": {"team_id": "away-1", "name": "Away FC"},
        }], []]
        result = collect_api_ninjas_observations(
            "provider-db", season=2026, leagues=["epl", "laliga"], client=client,
        )
        self.assertEqual(client.matches.call_count, 2)
        self.assertEqual(client.matches.call_args_list[0].kwargs["league"], "epl")
        self.assertEqual(client.matches.call_args_list[0].kwargs["status"], "scheduled")
        self.assertEqual(result["provider"], "api_ninjas")
        self.assertEqual(result["observation_count"], 1)
        self.assertTrue(result["archived"])
        self.assertEqual(archive.call_args.kwargs["provider"], "api_ninjas")

    def test_api_ninjas_collector_rejects_leagues_outside_free_tier(self):
        client = Mock()
        result = collect_api_ninjas_observations(
            "provider-db", season=2026, leagues=["championship"], client=client,
        )
        self.assertFalse(result["archived"])
        self.assertIn("outside the documented free-tier", result["errors"][0]["error"])
        client.matches.assert_not_called()

if __name__ == "__main__":
    unittest.main()
