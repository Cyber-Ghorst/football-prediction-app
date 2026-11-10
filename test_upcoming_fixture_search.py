"""Tests for searchable, bounded upcoming fixture catalogue queries."""
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

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


def test_search_upcoming_fixtures_uses_seven_day_window_and_exact_competition(monkeypatch):
    expected = (
        "sportmonks:900", "sportmonks:2026", "%Arsenal%",
        "%Arsenal%", "%Arsenal%", "%Arsenal%", 300,
    )
    cursor = FakeCursor([
        (
            "sportmonks:900", "sportmonks:2026", "sportmonks:10",
            "sportmonks:1", "sportmonks:2", "Arsenal", "Chelsea",
            "Premier League", "England", None, "Not Started", None,
            "sportmonks", None,
        )
    ])
    connection = FakeConnection(cursor)

    @contextmanager
    def fake_connect(_database_url):
        yield connection

    monkeypatch.setattr(football_repository, "_connect", fake_connect)
    rows = football_repository.search_upcoming_repository_fixtures(
        "postgresql://example",
        search_term="Arsenal",
        league_id="sportmonks:900",
        season_id="sportmonks:2026",
        window_days=7,
        limit=300,
    )

    assert len(rows) == 1
    assert rows[0]["home_team"] == "Arsenal"
    assert "INTERVAL '7 days'" in cursor.query
    assert "f.source_provider = 'sportmonks'" in cursor.query
    assert "f.starting_at > NOW()" in cursor.query
    assert "ht.name ILIKE %s" in cursor.query
    assert "JOIN football_teams AS ht" in cursor.query
    assert "JOIN football_teams AS at" in cursor.query
    assert "JOIN football_leagues AS l" in cursor.query
    assert cursor.params == expected


@pytest.mark.parametrize("window_days", [0, 8, -1, True, 7.0])
def test_search_upcoming_fixtures_rejects_invalid_window_before_database_access(
    monkeypatch, window_days
):
    def unexpected_connect(_database_url):
        raise AssertionError("Database must not be accessed for an invalid window.")

    monkeypatch.setattr(football_repository, "_connect", unexpected_connect)
    with pytest.raises(ValueError, match="1 through 7"):
        football_repository.search_upcoming_repository_fixtures(
            "postgresql://example", window_days=window_days
        )


def test_search_upcoming_fixtures_caps_requested_limit(monkeypatch):
    cursor = FakeCursor([])
    connection = FakeConnection(cursor)

    @contextmanager
    def fake_connect(_database_url):
        yield connection

    monkeypatch.setattr(football_repository, "_connect", fake_connect)
    football_repository.search_upcoming_repository_fixtures(
        "postgresql://example", limit=5000
    )
    assert cursor.params == (500,)
