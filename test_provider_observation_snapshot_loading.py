import unittest
from unittest.mock import patch

from provider_data_storage import load_provider_observation_snapshots


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.sql = None
        self.params = None

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class ProviderObservationSnapshotLoadingTests(unittest.TestCase):
    def test_loads_recent_fixture_observation_batches(self):
        row = (
            "snapshot-1", "openligadb", "future_fixture_observations",
            {"scopes": [{"league_shortcut": "bl1"}]}, ["fixture-1"],
            {"observations": []}, "2026-11-11T00:00:00Z", None, "sha256",
        )
        cursor = FakeCursor([row])
        with patch("provider_data_storage.ensure_provider_storage") as ensure, \
             patch("provider_data_storage._connect", return_value=FakeConnection(cursor)):
            result = load_provider_observation_snapshots(
                "provider-db", provider="OpenLigaDB", limit=25,
            )
        ensure.assert_called_once_with("provider-db")
        self.assertEqual(result[0]["snapshot_id"], "snapshot-1")
        self.assertEqual(result[0]["provider"], "openligadb")
        self.assertEqual(cursor.params, ("future_fixture_observations", "openligadb", "openligadb", 25))
        self.assertIn("ORDER BY retrieved_at DESC", cursor.sql)

    def test_rejects_invalid_provider_and_limit(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            load_provider_observation_snapshots("provider-db", provider="openscores")
        with self.assertRaisesRegex(ValueError, "limit"):
            load_provider_observation_snapshots("provider-db", limit=0)
        with self.assertRaisesRegex(ValueError, "PROVIDER_DATABASE_URL"):
            load_provider_observation_snapshots("")


if __name__ == "__main__":
    unittest.main()
