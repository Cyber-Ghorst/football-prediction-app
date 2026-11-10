import unittest
from unittest.mock import patch

from openscores_fixture_observation_sync import run_sync


class FakeClient:
    def __init__(self):
        self.calls = []
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def list_leagues(self):
        return {"data": [{"id": 1, "name": "Test League"}]}
    @staticmethod
    def _league_collection(data):
        return data, "$"
    def list_seasons(self, league_id):
        self.calls.append(("seasons", league_id))
        return {"data": {"seasons": [{"id": 2026}]}}
    def list_fixtures(self, **filters):
        self.calls.append(("fixtures", filters))
        return {
            "retrieved_at_utc": "2026-11-10T17:00:00Z",
            "data": {"items": [{
                "id": 77, "season_id": 2026,
                "scheduled_kickoff_at": "2026-11-12T19:00:00Z",
                "home_team": {"id": 10, "name": "Home"},
                "away_team": {"id": 20, "name": "Away"},
                "status": "scheduled",
            }]},
        }


class OpenScoresObservationSyncTests(unittest.TestCase):
    def test_live_flow_normalizes_stages_and_reconciles_observations_only(self):
        client = FakeClient()
        with patch(
            "openscores_fixture_observation_sync.upsert_openscores_observations",
            return_value={"observations_upserted": 1, "canonical_fixtures_written": 0},
        ) as save, patch(
            "openscores_fixture_observation_sync.reconcile_openscores_observations",
            return_value={"observations_checked": 1, "matched": 0,
                          "pending_entity_mapping": 1},
        ) as reconcile:
            report = run_sync(client_factory=lambda: client, database_url="postgresql://db")
        self.assertEqual(report["fixtures_normalized"], 1)
        self.assertEqual(report["observations_upserted"], 1)
        self.assertEqual(report["canonical_fixtures_written"], 0)
        self.assertTrue(report["read_only_for_canonical_fixtures"])
        self.assertFalse(report["prediction_ledger_touched"])
        save.assert_called_once()
        reconcile.assert_called_once_with("postgresql://db")

    def test_requires_database_before_provider_calls(self):
        client = FakeClient()
        with self.assertRaises(ValueError):
            run_sync(client_factory=lambda: client, database_url="")
        self.assertEqual(client.calls, [])


if __name__ == "__main__":
    unittest.main()
