import unittest
from unittest.mock import Mock, patch

from free_fixture_observation_pipeline import (
    collect_bzzoiro_observations,
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
            "provider-db", [{"league_shortcut": "bl1", "season": 2026}],
            client=client,
        )
        client.matches.assert_called_once_with("bl1", 2026)
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


if __name__ == "__main__":
    unittest.main()
