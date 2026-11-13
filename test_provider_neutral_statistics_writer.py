import unittest
from contextlib import contextmanager
from unittest.mock import patch

import football_repository


class FakeCursor:
    def __init__(self, fixtures):
        self.fixtures = fixtures
        self.query = None
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.query = query
        self.params = params

    def fetchall(self):
        return self.fixtures


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self._cursor


class ProviderNeutralStatisticsWriterTests(unittest.TestCase):
    def test_writes_normalized_rows_with_provider_and_raw_provenance(self):
        cursor = FakeCursor([("fixture-1", "home-1", "away-1")])
        connection = FakeConnection(cursor)
        captured = {}

        @contextmanager
        def fake_connect(*_args, **_kwargs):
            yield connection

        def capture_upsert(_cursor, **kwargs):
            captured.update(kwargs)

        with patch.object(football_repository, "_connect", fake_connect), patch.object(
            football_repository, "_execute_batched_upsert", capture_upsert
        ):
            result = football_repository.save_normalized_fixture_statistics(
                "postgresql://cockroach",
                provider="OpenLigaDB",
                statistics=[{
                    "fixture_id": "fixture-1",
                    "team_id": "home-1",
                    "statistic_type": "shots",
                    "statistic_value": 8,
                    "provider_statistic_id": "shots-home",
                    "provider_updated_at": None,
                    "raw_payload": {"source_metric": "shots"},
                }],
            )

        self.assertEqual(result["statistics_rows_written"], 1)
        self.assertEqual(result["provider"], "openligadb")
        self.assertIn("WHERE fixture_id = ANY(%s)", cursor.query)
        self.assertEqual(captured["table"], "football_fixture_statistics")
        row = captured["rows"][0]
        self.assertEqual(row[1:4], ("fixture-1", "home-1", "shots"))
        self.assertEqual(row[5:7], ("openligadb", "shots-home"))
        self.assertEqual(row[8].obj, {"source_metric": "shots"})
        self.assertFalse(result["prediction_engine_modified"])
        self.assertFalse(result["neon_prediction_ledger_modified"])

    def test_rejects_unknown_fixture_and_nonparticipant_team(self):
        cursor = FakeCursor([("fixture-1", "home-1", "away-1")])
        connection = FakeConnection(cursor)
        captured = {}

        @contextmanager
        def fake_connect(*_args, **_kwargs):
            yield connection

        def capture_upsert(_cursor, **kwargs):
            captured.update(kwargs)

        rows = [
            {
                "fixture_id": "missing",
                "team_id": None,
                "statistic_type": "possession",
                "statistic_value": 55,
            },
            {
                "fixture_id": "fixture-1",
                "team_id": "other-team",
                "statistic_type": "shots",
                "statistic_value": 4,
            },
        ]
        with patch.object(football_repository, "_connect", fake_connect), patch.object(
            football_repository, "_execute_batched_upsert", capture_upsert
        ):
            result = football_repository.save_normalized_fixture_statistics(
                "postgresql://cockroach", provider="highlightly", statistics=rows
            )

        self.assertEqual(result["statistics_rows_written"], 0)
        self.assertEqual(
            [item["reason"] for item in result["skipped"]],
            ["canonical_fixture_not_found", "team_not_a_fixture_participant"],
        )
        self.assertEqual(captured, {})

    def test_requires_provider_and_canonical_identifiers(self):
        with self.assertRaises(ValueError):
            football_repository.save_normalized_fixture_statistics(
                "postgresql://cockroach", provider="", statistics=[]
            )
        with self.assertRaises(ValueError):
            football_repository.save_normalized_fixture_statistics(
                "", provider="highlightly", statistics=[]
            )


if __name__ == "__main__":
    unittest.main()
