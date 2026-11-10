import unittest
from unittest.mock import patch

from openscores_observation_store import upsert_openscores_observations


class FakeCursor:
    def __init__(self):
        self.calls = []
    def execute(self, sql, params=None):
        self.calls.append((sql, params))


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self.cursor_obj


class OpenScoresObservationStoreTests(unittest.TestCase):
    def test_upsert_stages_only_provider_observations(self):
        connection = FakeConnection()
        with patch("openscores_observation_store.ensure_observation_store"), \
             patch("openscores_observation_store._connect", return_value=connection):
            result = upsert_openscores_observations("postgresql://db", [{
                "provider": "openscores",
                "provider_fixture_id": "f1",
                "provider_league_id": "l1",
                "provider_season_id": "s1",
                "provider_home_team_id": "h1",
                "provider_away_team_id": "a1",
                "home_team_name": "Home",
                "away_team_name": "Away",
                "kickoff_utc": "2026-11-12T18:30:00Z",
                "status": "scheduled",
                "source_ids": {"flashscore": "fs1"},
                "raw_payload": {"id": "f1"},
                "reconciliation_status": "pending_entity_mapping",
            }])
        self.assertEqual(result, {
            "observations_upserted": 1, "canonical_fixtures_written": 0
        })
        sql = "\n".join(call[0] for call in connection.cursor_obj.calls)
        self.assertIn("provider_fixture_observations", sql)
        self.assertNotIn("INSERT INTO football_fixtures", sql)

    def test_empty_observation_list_is_safe(self):
        connection = FakeConnection()
        with patch("openscores_observation_store.ensure_observation_store"), \
             patch("openscores_observation_store._connect", return_value=connection):
            result = upsert_openscores_observations("postgresql://db", [])
        self.assertEqual(result["observations_upserted"], 0)


if __name__ == "__main__":
    unittest.main()
