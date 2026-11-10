import unittest
from contextlib import contextmanager
from unittest.mock import patch

import temporary_fixture_store


def fixture(fid, status="Not Started"):
    return {
        "id": str(fid),
        "league_id": "8",
        "season_id": "2026",
        "starting_at": "2026-11-12T18:00:00+00:00",
        "state": {"name": status},
        "league": {"id": 8, "name": "Premier League", "country": {"name": "England"}},
        "season": {"id": 2026, "name": "2026/2027"},
        "participants": [
            {"id": 1, "name": "Home", "meta": {"location": "home"}},
            {"id": 2, "name": "Away", "meta": {"location": "away"}},
        ],
    }


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.rowcount = 2

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.calls.append((query, params))
        if query.startswith("SELECT COUNT"):
            self.fetchone_result = (1,)

    def executemany(self, query, params):
        self.calls.append((query, params))

    def fetchone(self):
        return self.fetchone_result


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self._cursor


class TemporaryFixtureStoreTests(unittest.TestCase):
    def test_refresh_upserts_same_provider_ids_and_deletes_missing_rows(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)

        @contextmanager
        def fake_connect(*_args, **_kwargs):
            yield connection

        with patch.object(temporary_fixture_store.psycopg, "connect", fake_connect):
            result = temporary_fixture_store.sync_temporary_upcoming_fixtures(
                "postgresql://neon", [fixture(100)]
            )

        self.assertEqual(result["fixtures_upserted"], 1)
        self.assertEqual(result["fixtures_removed"], 2)
        self.assertEqual(result["active_fixtures"], 1)
        self.assertEqual(result["prediction_ledger_modified"], 0)
        sql = "\n".join(call[0] for call in cursor.calls)
        self.assertIn("CREATE TABLE IF NOT EXISTS upcoming_fixture_staging", sql)
        self.assertIn("ON CONFLICT (fixture_id) DO UPDATE", sql)
        self.assertIn("DELETE FROM upcoming_fixture_staging WHERE NOT", sql)
        self.assertNotIn("prediction_ledger", sql)

    def test_empty_successful_refresh_cleans_completed_cancelled_and_expired_rows(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)

        @contextmanager
        def fake_connect(*_args, **_kwargs):
            yield connection

        with patch.object(temporary_fixture_store.psycopg, "connect", fake_connect):
            result = temporary_fixture_store.sync_temporary_upcoming_fixtures(
                "postgresql://neon", []
            )

        self.assertEqual(result["active_fixtures"], 1)
        self.assertTrue(any(
            query == "DELETE FROM upcoming_fixture_staging"
            for query, _params in cursor.calls
        ))

    def test_duplicate_provider_fixture_ids_are_rejected_before_database_access(self):
        with patch.object(
            temporary_fixture_store.psycopg,
            "connect",
            side_effect=AssertionError("Should not connect"),
        ):
            with self.assertRaisesRegex(ValueError, "Duplicate provider fixture IDs"):
                temporary_fixture_store.sync_temporary_upcoming_fixtures(
                    "postgresql://neon", [fixture(7), fixture(7)]
                )

    def test_neon_database_url_is_required(self):
        with self.assertRaisesRegex(ValueError, "DATABASE_URL"):
            temporary_fixture_store.sync_temporary_upcoming_fixtures("", [])


if __name__ == "__main__":
    unittest.main()
