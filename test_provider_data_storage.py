"""Tests for CockroachDB provider snapshot persistence."""
import sys
import types
from datetime import datetime, timedelta, timezone

import pytest

import provider_data_storage as storage


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.result = None

    def execute(self, query, params=None):
        normalized = " ".join(query.split())
        if normalized.startswith("INSERT INTO provider_api_snapshots"):
            self.connection.snapshots.append(params)
        elif normalized.startswith("INSERT INTO provider_collection_runs"):
            self.connection.runs.append(params)
        elif normalized.startswith("SELECT snapshot_id"):
            self.result = self.connection.fresh if "expires_at > NOW()" in normalized else self.connection.latest
        else:
            self.result = None

    def fetchone(self):
        return self.result

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeConnection:
    def __init__(self):
        self.snapshots = []
        self.runs = []
        self.fresh = None
        self.latest = None

    def cursor(self):
        return FakeCursor(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def fake_db(monkeypatch):
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


def test_cache_key_is_stable_and_provider_scoped():
    params = {"season": 2026, "team_id": 123}
    first = storage.build_provider_cache_key("Sportmonks", "fixtures", params)
    second = storage.build_provider_cache_key("sportmonks", "fixtures", {"team_id": 123, "season": 2026})
    other_provider = storage.build_provider_cache_key("highlightly", "fixtures", params)
    assert first == second
    assert first != other_provider


def test_cache_key_requires_provider_and_resource():
    with pytest.raises(ValueError):
        storage.build_provider_cache_key("", "fixtures", {})


def test_save_appends_immutable_snapshot_and_hashes_payload(fake_db):
    captured = datetime(2026, 11, 8, tzinfo=timezone.utc)
    snapshot_id = storage.save_provider_snapshot(
        "postgresql://example",
        provider="Sportmonks",
        resource_type="fixture",
        cache_key="sportmonks:fixture:abc",
        request_params={"fixture_id": 123},
        payload={"data": [{"id": 123}]},
        source_ids=[123],
        ttl_seconds=600,
        retrieved_at=captured,
    )
    assert snapshot_id
    assert len(fake_db.snapshots) == 1
    row = fake_db.snapshots[0]
    assert row[2:4] == ("sportmonks", "fixture")
    assert row[6].obj == {"data": [{"id": 123}]}
    assert row[7] == captured
    assert row[8] == captured + timedelta(seconds=600)
    assert len(row[9]) == 64


def test_failed_collection_diagnostic_does_not_write_snapshot(fake_db):
    run_id = storage.record_provider_collection_run(
        "postgresql://example",
        provider="highlightly",
        resource_type="matches",
        cache_key="highlightly:matches:abc",
        succeeded=False,
        http_status=429,
        error_type="RateLimitError",
        error_message="quota exhausted",
    )
    assert run_id
    assert len(fake_db.runs) == 1
    assert fake_db.snapshots == []
    assert fake_db.runs[0][6] == 429


def test_load_fresh_and_stale_snapshots_use_separate_queries(fake_db, monkeypatch):
    fresh_row = ("fresh", "sportmonks", "fixtures", {}, [], {"data": []}, None, None, "a" * 64)
    stale_row = ("stale", "sportmonks", "fixtures", {}, [], {"data": [1]}, None, "b" * 64)
    fake_db.fresh = fresh_row
    fake_db.latest = stale_row
    assert storage.load_provider_snapshot("postgresql://example", "key")["snapshot_id"] == "fresh"
    assert storage.load_provider_snapshot("postgresql://example", "key", allow_stale=True)["snapshot_id"] == "stale"


def test_invalid_payload_or_ttl_is_rejected(fake_db):
    base = {
        "provider": "sportmonks",
        "resource_type": "fixtures",
        "cache_key": "key",
        "request_params": {},
    }
    with pytest.raises(ValueError):
        storage.save_provider_snapshot("postgresql://example", payload="not-json-object", **base)
    with pytest.raises(ValueError):
        storage.save_provider_snapshot("postgresql://example", payload={}, ttl_seconds=-1, **base)
