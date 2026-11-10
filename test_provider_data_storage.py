"""Tests for CockroachDB provider snapshot persistence."""
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import provider_data_storage as storage


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.result = None

    def execute(self, query, params=None):
        normalized = " ".join(query.split())
        if normalized == "SELECT 1":
            self.result = (1,)
        elif normalized.startswith("INSERT INTO provider_api_snapshots"):
            self.connection.snapshots.append(params)
        elif normalized.startswith("INSERT INTO provider_collection_runs"):
            if self.connection.fail_run_insert:
                raise RuntimeError("audit insert failed")
            self.connection.runs.append(params)
        elif normalized.startswith("SELECT snapshot_id"):
            self.result = self.connection.fresh if "expires_at > NOW()" in normalized else self.connection.latest
        else:
            self.result = None

    def fetchone(self):
        return self.result

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeConnection:
    def __init__(self):
        self.snapshots = []
        self.runs = []
        self.fresh = None
        self.latest = None
        self.fail_run_insert = False
        self.commit_calls = 0
        self.rollback_calls = 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commit_calls += 1

    def rollback(self):
        self.rollback_calls += 1

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ProviderStorageTests(unittest.TestCase):
    def setUp(self):
        self.connection = FakeConnection()
        self.connect_calls = 0
        storage._INITIALIZED_DATABASES.clear()
        fake_psycopg = types.ModuleType("psycopg")
        def fake_connect(*args, **kwargs):
            self.connect_calls += 1
            return self.connection
        fake_psycopg.connect = fake_connect
        fake_json = types.ModuleType("psycopg.types.json")

        class FakeJsonb:
            def __init__(self, obj):
                self.obj = obj

        fake_json.Jsonb = FakeJsonb
        fake_types = types.ModuleType("psycopg.types")
        fake_types.json = fake_json
        self.modules_patch = patch.dict(
            sys.modules,
            {
                "psycopg": fake_psycopg,
                "psycopg.types": fake_types,
                "psycopg.types.json": fake_json,
            },
        )
        self.modules_patch.start()
        self.psycopg_patch = patch.object(storage, "psycopg", fake_psycopg)
        self.jsonb_patch = patch.object(storage, "Jsonb", FakeJsonb)
        self.psycopg_patch.start()
        self.jsonb_patch.start()

    def tearDown(self):
        self.jsonb_patch.stop()
        self.psycopg_patch.stop()
        self.modules_patch.stop()

    def test_connection_check_creates_tables_and_verifies_sql_round_trip(self):
        self.assertTrue(storage.check_provider_storage_connection("postgresql://example"))

    def test_connection_check_requires_database_url(self):
        with self.assertRaises(ValueError):
            storage.check_provider_storage_connection("")

    def test_cache_key_is_stable_and_provider_scoped(self):
        params = {"season": 2026, "team_id": 123}
        first = storage.build_provider_cache_key("Sportmonks", "fixtures", params)
        second = storage.build_provider_cache_key("sportmonks", "fixtures", {"team_id": 123, "season": 2026})
        other_provider = storage.build_provider_cache_key("highlightly", "fixtures", params)
        self.assertEqual(first, second)
        self.assertNotEqual(first, other_provider)

    def test_cache_key_requires_provider_and_resource(self):
        with self.assertRaises(ValueError):
            storage.build_provider_cache_key("", "fixtures", {})

    def test_save_appends_immutable_snapshot_and_hashes_payload(self):
        captured = datetime(2026, 11, 8, tzinfo=timezone.utc)
        snapshot_id = storage.save_provider_snapshot(
            "postgresql://example",
            provider="Sportmonks",
            resource_type="fixture",
            cache_key="sportmonks:fixture:abc",
            request_params={"fixture_id": 123},
            payload={"data": [{"id": 123}]},
            source_ids=[123],
            ttl_seconds=600,
            retrieved_at=captured,
        )
        self.assertTrue(snapshot_id)
        self.assertEqual(len(self.connection.snapshots), 1)
        row = self.connection.snapshots[0]
        self.assertEqual(row[2:4], ("sportmonks", "fixture"))
        self.assertEqual(row[6].obj, {"data": [{"id": 123}]})
        self.assertEqual(row[7], captured)
        self.assertEqual(row[8], captured + timedelta(seconds=600))
        self.assertEqual(len(row[9]), 64)

    def test_schema_initialization_is_reused_after_first_write(self):
        kwargs = {
            "provider": "sportmonks",
            "resource_type": "fixtures",
            "cache_key": "sportmonks:fixtures:abc",
            "request_params": {"season_id": 2026},
            "payload": [{"id": 1}],
        }
        storage.save_provider_snapshot("postgresql://example", **kwargs)
        first_write_connections = self.connect_calls
        storage.save_provider_snapshot("postgresql://example", **kwargs)
        self.assertEqual(first_write_connections, 2)  # one schema setup + one insert
        self.assertEqual(self.connect_calls, 3)  # second insert skips repeated DDL setup

    def test_snapshot_and_success_audit_share_one_connection(self):
        database_url = "postgresql://example"
        storage._INITIALIZED_DATABASES.add(storage._database_fingerprint(database_url))
        result = storage.save_provider_snapshot_and_record_run(
            database_url,
            provider="sportmonks",
            resource_type="fixtures",
            cache_key="sportmonks:fixtures:combined",
            request_params={"season_id": 2026},
            payload=[{"id": 123}],
            source_ids=[123],
            ttl_seconds=300,
        )
        self.assertEqual(self.connect_calls, 1)
        self.assertTrue(result["snapshot_id"])
        self.assertTrue(result["run_recorded"])
        self.assertEqual(len(self.connection.snapshots), 1)
        self.assertEqual(len(self.connection.runs), 1)
        self.assertTrue(self.connection.runs[0][5])
        self.assertEqual(self.connection.commit_calls, 2)

    def test_snapshot_is_preserved_when_success_audit_insert_fails(self):
        database_url = "postgresql://example"
        storage._INITIALIZED_DATABASES.add(storage._database_fingerprint(database_url))
        self.connection.fail_run_insert = True
        result = storage.save_provider_snapshot_and_record_run(
            database_url,
            provider="sportmonks",
            resource_type="fixtures",
            cache_key="sportmonks:fixtures:audit-failure",
            request_params={"season_id": 2026},
            payload=[{"id": 123}],
        )
        self.assertTrue(result["snapshot_id"])
        self.assertFalse(result["run_recorded"])
        self.assertEqual(result["run_error_type"], "RuntimeError")
        self.assertEqual(len(self.connection.snapshots), 1)
        self.assertEqual(self.connection.runs, [])
        self.assertEqual(self.connection.commit_calls, 1)
        self.assertEqual(self.connection.rollback_calls, 1)

    def test_failed_collection_diagnostic_does_not_write_snapshot(self):
        run_id = storage.record_provider_collection_run(
            "postgresql://example",
            provider="highlightly",
            resource_type="matches",
            cache_key="highlightly:matches:abc",
            succeeded=False,
            http_status=429,
            error_type="RateLimitError",
            error_message="quota exhausted",
        )
        self.assertTrue(run_id)
        self.assertEqual(len(self.connection.runs), 1)
        self.assertEqual(self.connection.snapshots, [])
        self.assertEqual(self.connection.runs[0][6], 429)

    def test_load_fresh_and_stale_snapshots_use_separate_queries(self):
        fresh_row = ("fresh", "sportmonks", "fixtures", {}, [], {"data": []}, None, None, "a" * 64)
        stale_row = ("stale", "sportmonks", "fixtures", {}, [], {"data": [1]}, None, "b" * 64)
        self.connection.fresh = fresh_row
        self.connection.latest = stale_row
        self.assertEqual(
            storage.load_provider_snapshot("postgresql://example", "key")["snapshot_id"],
            "fresh",
        )
        self.assertEqual(
            storage.load_provider_snapshot("postgresql://example", "key", allow_stale=True)["snapshot_id"],
            "stale",
        )

    def test_invalid_payload_or_ttl_is_rejected(self):
        base = {
            "provider": "sportmonks",
            "resource_type": "fixtures",
            "cache_key": "key",
            "request_params": {},
        }
        with self.assertRaises(ValueError):
            storage.save_provider_snapshot("postgresql://example", payload="not-json-object", **base)
        with self.assertRaises(ValueError):
            storage.save_provider_snapshot("postgresql://example", payload={}, ttl_seconds=-1, **base)


if __name__ == "__main__":
    unittest.main()
