import unittest
from contextlib import contextmanager
from unittest.mock import patch

from football_repository import get_repository_teams


class FakeCursor:
    def __init__(self):
        self.sql = ""
        self.params = None

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return [("sportmonks:1", "Arsenal", "ARS", "England", "sportmonks", None, None)]

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


class FootballRepositoryTeamCountryTests(unittest.TestCase):
    def test_team_country_falls_back_to_one_unambiguous_domestic_league_country(self):
        cursor = FakeCursor()

        @contextmanager
        def fake_connect(*_args, **_kwargs):
            yield FakeConnection(cursor)

        with patch("football_repository._connect", fake_connect):
            rows = get_repository_teams("provider-db")

        self.assertEqual(rows[0]["country"], "England")
        self.assertIn("COUNT(DISTINCT LOWER(BTRIM(l.country))) = 1", cursor.sql)
        self.assertIn("country_fixtures.home_team_id = t.team_id", cursor.sql)
        self.assertIn("country_fixtures.away_team_id = t.team_id", cursor.sql)
        self.assertIn("NOT IN ('world', 'europe', 'international')", cursor.sql)

    def test_team_country_query_preserves_explicit_team_country(self):
        cursor = FakeCursor()

        @contextmanager
        def fake_connect(*_args, **_kwargs):
            yield FakeConnection(cursor)

        with patch("football_repository._connect", fake_connect):
            get_repository_teams("provider-db", league_id="sportmonks:8")

        self.assertIn("COALESCE(", cursor.sql)
        self.assertIn("NULLIF(t.country, '')", cursor.sql)
        self.assertEqual(cursor.params, ("sportmonks:8",))


if __name__ == "__main__":
    unittest.main()
