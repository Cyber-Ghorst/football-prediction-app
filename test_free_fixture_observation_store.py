import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from free_fixture_observation_store import archive_future_fixture_observations


class FreeFixtureObservationStoreTests(unittest.TestCase):
    def observation(self, provider="openligadb", fixture_id="openligadb:1", eligible=True):
        return {
            "provider": provider,
            "provider_fixture_id": fixture_id,
            "kickoff_utc": "2026-11-20T19:00:00Z",
            "eligible_for_review": eligible,
            "raw_payload": {"id": 1},
        }

    @patch("free_fixture_observation_store.save_provider_snapshot_and_record_run")
    def test_archives_immutable_observations_without_canonical_or_ledger_writes(self, save):
        save.return_value = {"snapshot_id": "snapshot-1", "run_id": "run-1"}
        result = archive_future_fixture_observations(
            "postgresql://provider-db",
            provider="openligadb",
            request_params={"league_shortcut": "bl1", "season": 2026},
            observations=[
                self.observation(),
                self.observation(fixture_id="openligadb:2", eligible=False),
            ],
            retrieved_at=datetime(2026, 11, 11, tzinfo=timezone.utc),
        )
        self.assertEqual(result["snapshot_id"], "snapshot-1")
        self.assertEqual(result["observation_count"], 2)
        self.assertEqual(result["eligible_for_review_count"], 1)
        self.assertEqual(result["canonical_fixture_writes"], 0)
        self.assertEqual(result["prediction_ledger_writes"], 0)
        kwargs = save.call_args.kwargs
        self.assertEqual(kwargs["resource_type"], "future_fixture_observations")
        self.assertEqual(kwargs["ttl_seconds"], 0)
        self.assertEqual(kwargs["source_ids"], ["openligadb:1", "openligadb:2"])
        self.assertEqual(kwargs["payload"]["canonical_fixture_writes"], 0)

    @patch("free_fixture_observation_store.save_provider_snapshot_and_record_run")
    def test_thesportsdb_is_an_approved_observation_provider(self, save):
        save.return_value = {"snapshot_id": "snapshot-tsdb", "run_id": "run-tsdb"}
        row = self.observation(
            provider="thesportsdb", fixture_id="thesportsdb:event-1",
        )
        result = archive_future_fixture_observations(
            "postgresql://provider-db", provider="thesportsdb",
            request_params={"country": "England"}, observations=[row],
        )
        self.assertEqual(result["snapshot_id"], "snapshot-tsdb")
        self.assertEqual(result["provider"], "thesportsdb")

    def test_rejects_provider_mismatch_and_missing_source_id(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            archive_future_fixture_observations(
                "postgresql://db", provider="openligadb",
                request_params={}, observations=[self.observation("bzzoiro")],
            )
        row = self.observation()
        row["provider_fixture_id"] = ""
        with self.assertRaisesRegex(ValueError, "provider-scoped fixture ID"):
            archive_future_fixture_observations(
                "postgresql://db", provider="openligadb",
                request_params={}, observations=[row],
            )

    def test_rejects_credentials_in_request_metadata(self):
        with self.assertRaisesRegex(ValueError, "Credentials"):
            archive_future_fixture_observations(
                "postgresql://db", provider="bzzoiro",
                request_params={"status": "upcoming", "api_key": "secret"},
                observations=[],
            )

    def test_rejects_unselected_provider_and_missing_database(self):
        with self.assertRaisesRegex(ValueError, "not an approved"):
            archive_future_fixture_observations(
                "postgresql://db", provider="openscores",
                request_params={}, observations=[],
            )
        with self.assertRaisesRegex(ValueError, "PROVIDER_DATABASE_URL"):
            archive_future_fixture_observations(
                "", provider="openfootball", request_params={}, observations=[],
            )


if __name__ == "__main__":
    unittest.main()
