import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import temporary_fixture_store


class FakeCursor:
    def __init__(self):
        self.query = None
        self.params = None
        self.connection_calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.connection_calls.append((query, params))
        self.query = query
        self.params = params

    def fetchall(self):
        return [(
            "sportmonks:900", "sportmonks:2026", "sportmonks:8",
            "sportmonks:1", "sportmonks:2", "Arsenal", "Chelsea",
            "Premier League", "England", None, "Not Started", None,
            "sportmonks", None,
        )]


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self._cursor


class TemporaryFixtureSearchTests(unittest.TestCase):
    def test_search_reads_neon_active_window_with_exact_league_and_team_term(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)

        @contextmanager
        def fake_connect(*_args, **_kwargs):
            yield connection

        with patch.object(temporary_fixture_store.psycopg, "connect", fake_connect):
            rows = temporary_fixture_store.search_temporary_upcoming_fixtures(
                "postgresql://neon",
                search_term="Arsenal",
                league_id="sportmonks:8",
                season_id="sportmonks:2026",
                window_days=7,
                limit=300,
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["home_team"], "Arsenal")
        self.assertIn(
            "CREATE TABLE IF NOT EXISTS upcoming_fixture_staging",
            cursor.connection_calls[0][0],
        )
        self.assertIn("FROM upcoming_fixture_staging", cursor.query)
        self.assertIn("INTERVAL '7 days'", cursor.query)
        self.assertIn("home_team ILIKE %s", cursor.query)
        self.assertIn("'postponed'", cursor.query)
        self.assertEqual(
            cursor.params,
            (
                "sportmonks:8", "sportmonks:2026",
                "%Arsenal%", "%Arsenal%", "%Arsenal%", "%Arsenal%", 300,
            ),
        )

    def test_search_rejects_invalid_window_before_database_access(self):
        with patch.object(
            temporary_fixture_store.psycopg,
            "connect",
            side_effect=AssertionError("Should not connect"),
        ):
            for window_days in (0, 8, -1, True, 7.0):
                with self.subTest(window_days=window_days):
                    with self.assertRaisesRegex(ValueError, "1 through 7"):
                        temporary_fixture_store.search_temporary_upcoming_fixtures(
                            "postgresql://neon", window_days=window_days
                        )

    def test_search_caps_result_limit(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)

        @contextmanager
        def fake_connect(*_args, **_kwargs):
            yield connection

        with patch.object(temporary_fixture_store.psycopg, "connect", fake_connect):
            temporary_fixture_store.search_temporary_upcoming_fixtures(
                "postgresql://neon", limit=9000
            )
        self.assertEqual(cursor.params, (500,))


if __name__ == "__main__":
    unittest.main()
