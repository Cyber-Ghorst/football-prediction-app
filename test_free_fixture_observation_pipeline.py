import unittest
from unittest.mock import Mock, patch

from free_fixture_observation_pipeline import (
    collect_bzzoiro_observations,
    collect_openfootball_observations,
    collect_openligadb_observations,
    collect_openmatchday_observations,
    collect_thesportsdb_observations,
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
    @patch("free_fixture_observation_pipeline.archive_future_fixture_observations")
    def test_thesportsdb_requires_terms_acknowledgement_and_archives_next_events(self, archive):
        archive.return_value = {"snapshot_id": "snapshot-tsdb"}
        client = Mock()
        client.leagues_by_country.return_value = [{
            "idLeague": "4328", "strLeague": "Premier League", "strCountry": "England"
        }]
        client.events_next_league.return_value = [{
            "idEvent": "event-1", "strTimestamp": "2026-11-20T19:00:00Z",
            "strStatus": "Not Started", "strSeason": "2026-2027",
            "idHomeTeam": "1", "strHomeTeam": "Home FC",
            "idAwayTeam": "2", "strAwayTeam": "Away FC",
        }]
        with self.assertRaisesRegex(ValueError, "terms acknowledgement"):
            collect_thesportsdb_observations(
                "provider-db", country="England", client=client,
            )
        result = collect_thesportsdb_observations(
            "provider-db", country="England", client=client,
            terms_acknowledged=True, request_delay_seconds=0,
        )
        self.assertEqual(result["snapshot_id"], "snapshot-tsdb")
        client.leagues_by_country.assert_called_with("England", sport="Soccer")
        client.events_next_league.assert_called_with("4328")
        self.assertEqual(archive.call_args.args[1], "thesportsdb")
        self.assertEqual(archive.call_args.args[2]["country"], "England")

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
