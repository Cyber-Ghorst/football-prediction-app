"""Tests for searchable, bounded upcoming fixture catalogue queries."""
from contextlib import contextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import football_repository


class FakeCursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.description = [
            SimpleNamespace(name=name)
            for name in (
                "fixture_id", "season_id", "league_id", "home_team_id",
                "away_team_id", "home_team", "away_team", "competition",
                "country", "starting_at", "status", "venue", "source_provider",
                "provider_updated_at",
            )
        ]
        self.query = None
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params):
        self.query = query
        self.params = params

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self._cursor


class UpcomingFixtureSearchTests(unittest.TestCase):
    def test_search_uses_seven_day_window_and_exact_competition(self):
        cursor = FakeCursor([
            (
                "fixture_v1_example", "season_v1_example", "competition_v1_example",
                "team_v1_home", "team_v1_away", "Arsenal", "Chelsea",
                "Premier League", "England", None, "Not Started", None,
                "openligadb", None,
            )
        ])
        connection = FakeConnection(cursor)

        @contextmanager
        def fake_connect(_database_url):
            yield connection

        with patch.object(football_repository, "_connect", fake_connect):
            rows = football_repository.search_upcoming_repository_fixtures(
                "postgresql://example",
                search_term="Arsenal",
                league_id="competition_v1_example",
                season_id="season_v1_example",
                window_days=7,
                limit=300,
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["home_team"], "Arsenal")
        self.assertIn("INTERVAL '7 days'", cursor.query)
        self.assertNotIn("f.source_provider =", cursor.query)
        self.assertEqual(rows[0]["source_provider"], "openligadb")
        self.assertIn("f.starting_at > NOW()", cursor.query)
        self.assertIn("ht.name ILIKE %s", cursor.query)
        self.assertIn("JOIN football_teams AS ht", cursor.query)
        self.assertIn("JOIN football_teams AS at", cursor.query)
        self.assertIn("JOIN football_leagues AS l", cursor.query)
        self.assertEqual(
            cursor.params,
            (
                "competition_v1_example", "season_v1_example", "%Arsenal%",
                "%Arsenal%", "%Arsenal%", "%Arsenal%", 300,
            ),
        )

    def test_invalid_windows_are_rejected_before_database_access(self):
        def unexpected_connect(_database_url):
            raise AssertionError("Database must not be accessed for an invalid window.")

        invalid_windows = (0, 8, -1, True, 7.0)
        with patch.object(football_repository, "_connect", unexpected_connect):
            for window_days in invalid_windows:
                with self.subTest(window_days=window_days):
                    with self.assertRaisesRegex(ValueError, "1 through 7"):
                        football_repository.search_upcoming_repository_fixtures(
                            "postgresql://example", window_days=window_days
                        )

    def test_requested_limit_is_capped(self):
        cursor = FakeCursor([])
        connection = FakeConnection(cursor)

        @contextmanager
        def fake_connect(_database_url):
            yield connection

        with patch.object(football_repository, "_connect", fake_connect):
            football_repository.search_upcoming_repository_fixtures(
                "postgresql://example", limit=5000
            )
        self.assertEqual(cursor.params, (500,))


if __name__ == "__main__":
    unittest.main()
