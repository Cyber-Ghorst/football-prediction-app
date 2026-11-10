"""Tests for isolated TipMaster benchmark persistence."""
import sys
import types

import tipmaster_storage as storage


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def execute(self, query, params=None):
        normalized = " ".join(query.split())
        self.connection.calls.append(normalized)
        if normalized.startswith("SELECT payload"):
            self.rows = [(value[1]) for value in self.connection.records.values()]

    def executemany(self, query, params):
        self.connection.calls.append(" ".join(query.split()))
        for key, payload, kickoff, fetched in params:
            current = self.connection.records.get(key)
            if current is None or fetched >= current[2]:
                self.connection.records[key] = (key, payload.obj, fetched)

    def fetchall(self):
        return list(self.rows)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeConnection:
    def __init__(self):
        self.records = {}
        self.calls = []

    def cursor(self):
        return FakeCursor(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _record(**changes):
    row = {
        "source": "tipmaster",
        "source_match_id": "match-1",
        "kickoff_at": "2026-11-10T20:00:00+00:00",
        "fetched_at": "2026-11-10T10:00:00+00:00",
        "prediction_inputs_eligible": False,
        "groups": {"top20": {"sample": 80, "shares": {"home": .7, "draw": .2, "away": .1}}},
    }
    row.update(changes)
    return row


def _install(monkeypatch):
    connection = FakeConnection()
    fake_psycopg = types.ModuleType("psycopg")
    fake_psycopg.connect = lambda *args, **kwargs: connection
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
    monkeypatch.setattr(storage, "psycopg", fake_psycopg)
    monkeypatch.setattr(storage, "Jsonb", FakeJsonb)
    return connection


def test_save_and_load_keeps_benchmark_separate(monkeypatch):
    connection = _install(monkeypatch)
    assert storage.save_tipmaster_benchmark_records("postgresql://test", [_record()]) == 1
    loaded = storage.load_tipmaster_benchmark_records("postgresql://test")
    assert len(loaded) == 1
    assert loaded[0]["source_match_id"] == "match-1"
    assert all("prediction_ledger" not in call for call in connection.calls)


def test_rejects_records_that_could_enter_prediction_inputs(monkeypatch):
    _install(monkeypatch)
    bad = _record(prediction_inputs_eligible=True)
    try:
        storage.save_tipmaster_benchmark_records("postgresql://test", [bad])
    except ValueError:
        pass
    else:
        raise AssertionError("Expected benchmark isolation validation")


def test_rejects_duplicate_source_ids_in_batch(monkeypatch):
    _install(monkeypatch)
    try:
        storage.save_tipmaster_benchmark_records("postgresql://test", [_record(), _record()])
    except ValueError:
        pass
    else:
        raise AssertionError("Expected duplicate IDs to be rejected")


def test_rejects_missing_required_provenance(monkeypatch):
    _install(monkeypatch)
    bad = _record(fetched_at="")
    try:
        storage.save_tipmaster_benchmark_records("postgresql://test", [bad])
    except ValueError:
        pass
    else:
        raise AssertionError("Expected missing fetched_at to be rejected")
