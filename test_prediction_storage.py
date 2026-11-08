"""Tests for Neon prediction-ledger persistence."""
import sys
import types

from prediction_storage import _clean_record, save_prediction_records


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.result = None

    def execute(self, query, params=None):
        normalized = " ".join(query.split())
        if normalized.startswith("SELECT payload FROM prediction_ledger WHERE"):
            self.result = self.connection.rows.get(params[0])
        elif normalized.startswith("INSERT INTO prediction_ledger"):
            record_id, payload = params
            self.connection.rows[record_id] = payload.obj
        elif normalized.startswith("SELECT COUNT(*)"):
            self.result = len(self.connection.rows)
        else:
            self.result = None

    def fetchone(self):
        if isinstance(self.result, int):
            return (self.result,)
        return (self.result,) if self.result is not None else None

    def fetchall(self):
        return [(payload,) for payload in self.connection.rows.values()]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeConnection:
    def __init__(self):
        self.rows = {}

    def cursor(self):
        return FakeCursor(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_clean_record_requires_stable_id():
    try:
        _clean_record({"home_team": "Brighton"})
    except ValueError as exc:
        assert "record_id" in str(exc)
    else:
        raise AssertionError("Expected missing record_id to be rejected")


def test_clean_record_normalizes_values():
    record = _clean_record({"record_id": "abc", "goals": 2})
    assert record == {"record_id": "abc", "goals": 2}


def test_database_upsert_deduplicates_and_preserves_known_values(monkeypatch):
    fake_connection = FakeConnection()
    fake_psycopg = types.ModuleType("psycopg")
    fake_psycopg.connect = lambda *args, **kwargs: fake_connection
    fake_json = types.ModuleType("psycopg.types.json")

    class FakeJsonb:
        def __init__(self, obj):
            self.obj = obj

    fake_json.Jsonb = FakeJsonb
    fake_types = types.ModuleType("psycopg.types")
    fake_types.json = fake_json
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)
    monkeypatch.setitem(sys.modules, "psycopg.types", fake_types)
    monkeypatch.setitem(sys.modules, "psycopg.types.json", fake_json)

    original = {
        "record_id": "fixture-1",
        "home_team": "Brighton",
        "actual_home_goals": 2,
        "actual_away_goals": 1,
    }
    assert save_prediction_records("postgresql://example", [original]) == 1

    partial_update = {
        "record_id": "fixture-1",
        "home_team": "Brighton",
        "actual_home_goals": "",
        "actual_away_goals": "",
    }
    assert save_prediction_records("postgresql://example", [partial_update]) == 1
    stored = fake_connection.rows["fixture-1"]
    assert stored["actual_home_goals"] == 2
    assert stored["actual_away_goals"] == 1
    assert stored["home_team"] == "Brighton"
