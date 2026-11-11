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

    def test_additive_free_provider_staging_never_deletes_existing_catalogue_rows(self):
        cursor = FakeCursor()
        cursor.rowcount = 1
        connection = FakeConnection(cursor)

        @contextmanager
        def fake_connect(*_args, **_kwargs):
            yield connection

        canonical_fixture = {
            "fixture_id": "openligadb:match-42",
            "source_provider": "openligadb",
            "league_id": "sportmonks:8",
            "season_id": "sportmonks:2026",
            "starting_at": "2026-11-12T18:00:00+00:00",
            "status": "scheduled",
            "home_team_id": "sportmonks:1",
            "away_team_id": "sportmonks:2",
            "home_team": "Home",
            "away_team": "Away",
            "competition": "Premier League",
            "country": "England",
        }
        with patch.object(temporary_fixture_store.psycopg, "connect", fake_connect):
            result = temporary_fixture_store.add_temporary_upcoming_fixtures(
                "postgresql://neon", [canonical_fixture]
            )

        self.assertEqual(result["fixtures_inserted"], 1)
        self.assertEqual(result["fixtures_removed"], 0)
        self.assertEqual(result["prediction_ledger_modified"], 0)
        sql = "\\n".join(call[0] for call in cursor.calls)
        self.assertIn("ON CONFLICT (fixture_id) DO NOTHING", sql)
        self.assertNotIn("DELETE FROM upcoming_fixture_staging", sql)
        self.assertNotIn("DO UPDATE", sql)

    def test_additive_staging_accepts_reviewed_highlightly_and_api_ninjas_fixtures(self):
        for provider in ("highlightly", "api_ninjas"):
            cursor = FakeCursor()
            connection = FakeConnection(cursor)

            @contextmanager
            def fake_connect(*_args, **_kwargs):
                yield connection

            canonical_fixture = {
                "fixture_id": f"{provider}:match-42",
                "source_provider": provider,
                "league_id": "sportmonks:8",
                "season_id": "sportmonks:2026",
                "starting_at": "2026-11-12T18:00:00+00:00",
                "status": "scheduled",
                "home_team_id": "sportmonks:1",
                "away_team_id": "sportmonks:2",
                "home_team": "Home",
                "away_team": "Away",
                "competition": "Premier League",
                "country": "England",
            }
            with patch.object(temporary_fixture_store.psycopg, "connect", fake_connect):
                result = temporary_fixture_store.add_temporary_upcoming_fixtures(
                    "postgresql://neon", [canonical_fixture]
                )
            self.assertEqual(result["fixtures_inserted"], 1)
            self.assertEqual(result["fixtures_removed"], 0)
            self.assertEqual(result["prediction_ledger_modified"], 0)

    def test_additive_free_provider_staging_rejects_unmapped_canonical_ids(self):
        invalid = {
            "fixture_id": "openligadb:42",
            "source_provider": "openligadb",
            "league_id": "openligadb:league",
            "season_id": "sportmonks:2026",
            "starting_at": "2026-11-12T18:00:00+00:00",
            "status": "scheduled",
            "home_team_id": "sportmonks:1",
            "away_team_id": "sportmonks:2",
            "home_team": "Home",
            "away_team": "Away",
            "competition": "Premier League",
        }
        with patch.object(
            temporary_fixture_store.psycopg, "connect",
            side_effect=AssertionError("Must reject before connecting"),
        ):
            with self.assertRaisesRegex(ValueError, "Sportmonks identity links"):
                temporary_fixture_store.add_temporary_upcoming_fixtures(
                    "postgresql://neon", [invalid]
                )

    def test_neon_database_url_is_required(self):
        with self.assertRaisesRegex(ValueError, "DATABASE_URL"):
            temporary_fixture_store.sync_temporary_upcoming_fixtures("", [])


if __name__ == "__main__":
    unittest.main()
