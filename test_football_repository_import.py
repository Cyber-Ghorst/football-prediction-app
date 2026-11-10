import unittest
from contextlib import contextmanager
from unittest.mock import patch

import football_repository


class FakeCursor:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.calls.append((query, params))


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self._cursor


class FootballRepositoryImportTests(unittest.TestCase):
    def test_season_import_collects_provider_links_in_keyed_dictionary(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)

        @contextmanager
        def fake_connect(*_args, **_kwargs):
            yield connection

        team = {"id": 31, "name": "Example FC"}
        with patch.object(football_repository, "_connect", fake_connect):
            result = football_repository.import_sportmonks_season(
                "postgresql://cockroach",
                league={"id": 8, "name": "Example League"},
                season={"id": 2026, "league_id": 8, "name": "2026/27"},
                teams=[team, dict(team)],
                fixtures=[],
            )

        self.assertEqual(result["provider_links_written"], 3)
        link_insert = next(
            (query, params) for query, params in cursor.calls
            if "INSERT INTO provider_entity_links" in query
        )
        query, params = link_insert
        self.assertIn("ON CONFLICT (provider, entity_type, provider_entity_id)", query)
        self.assertEqual(len(params), 15)
        linked_entities = {
            (params[index + 2], params[index + 3])
            for index in range(0, len(params), 5)
        }
        self.assertEqual(
            linked_entities,
            {("league", "8"), ("season", "2026"), ("team", "31")},
        )
        self.assertFalse(result["neon_prediction_ledger_modified"])


if __name__ == "__main__":
    unittest.main()
