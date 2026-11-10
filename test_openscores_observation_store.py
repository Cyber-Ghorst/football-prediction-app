import unittest
from unittest.mock import patch

from openscores_observation_store import (
    reconcile_openscores_observations,
    upsert_openscores_observations,
)


class FakeCursor:
    def __init__(self):
        self.calls = []
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params=None):
        self.calls.append((sql, params))


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self.cursor_obj


class ReconcileCursor:
    def __init__(self, *, links, fixtures, existing_fixture_link=None):
        self.calls = []
        self.fetchall_count = 0
        self.links = links
        self.fixtures = fixtures
        self.existing_fixture_link = existing_fixture_link
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params=None):
        self.calls.append((sql, params))
    def fetchall(self):
        self.fetchall_count += 1
        if self.fetchall_count == 1:
            return [("obs-1", "os-fixture-1", "os-league-1", "os-season-1",
                     "os-home-1", "os-away-1", "2026-11-12T18:30:00Z")]
        if self.fetchall_count == 2:
            return self.links
        if self.fetchall_count == 3:
            return self.fixtures
        return []
    def fetchone(self):
        return (self.existing_fixture_link,) if self.existing_fixture_link else None


class ReconcileConnection:
    def __init__(self, cursor):
        self.cursor_obj = cursor
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

    def _run_reconciliation(self, *, links, fixtures, existing_fixture_link=None):
        cursor = ReconcileCursor(
            links=links, fixtures=fixtures,
            existing_fixture_link=existing_fixture_link,
        )
        with patch(
            "openscores_observation_store._connect",
            return_value=ReconcileConnection(cursor),
        ):
            report = reconcile_openscores_observations("postgresql://db")
        return report, cursor

    @staticmethod
    def _complete_links():
        return [
            ("league", "os-league-1", "sportmonks:8"),
            ("season", "os-season-1", "sportmonks:28083"),
            ("team", "os-home-1", "sportmonks:team-home"),
            ("team", "os-away-1", "sportmonks:team-away"),
        ]

    def test_missing_explicit_entity_crosswalks_stay_pending(self):
        report, cursor = self._run_reconciliation(links=[], fixtures=[])
        self.assertEqual(report["pending_entity_mapping"], 1)
        self.assertEqual(report["matched"], 0)
        sql = "\n".join(call[0] for call in cursor.calls)
        self.assertIn("pending_entity_mapping", sql)
        self.assertNotIn("INSERT INTO football_fixtures", sql)

    def test_unique_sportmonks_fixture_fingerprint_is_linked(self):
        report, cursor = self._run_reconciliation(
            links=self._complete_links(), fixtures=[("sportmonks-fixture-99",)]
        )
        self.assertEqual(report["matched"], 1)
        sql = "\n".join(call[0] for call in cursor.calls)
        self.assertIn("INSERT INTO provider_entity_links", sql)
        self.assertIn("UPDATE provider_fixture_observations", sql)
        self.assertNotIn("INSERT INTO football_fixtures", sql)
        self.assertNotIn("UPDATE football_fixtures", sql)

    def test_zero_canonical_fixture_matches_remain_unmatched(self):
        report, _ = self._run_reconciliation(
            links=self._complete_links(), fixtures=[]
        )
        self.assertEqual(report["no_canonical_fixture_match"], 1)
        self.assertEqual(report["matched"], 0)

    def test_multiple_canonical_fixture_matches_are_ambiguous(self):
        report, _ = self._run_reconciliation(
            links=self._complete_links(),
            fixtures=[("sportmonks-fixture-99",), ("sportmonks-fixture-100",)],
        )
        self.assertEqual(report["ambiguous_canonical_fixture_match"], 1)
        self.assertEqual(report["matched"], 0)

    def test_conflicting_existing_fixture_crosswalk_is_preserved(self):
        report, cursor = self._run_reconciliation(
            links=self._complete_links(),
            fixtures=[("sportmonks-fixture-99",)],
            existing_fixture_link="sportmonks-fixture-other",
        )
        self.assertEqual(report["fixture_crosswalk_conflict"], 1)
        self.assertEqual(report["matched"], 0)
        sql = "\n".join(call[0] for call in cursor.calls)
        self.assertIn("fixture_crosswalk_conflict", sql)


if __name__ == "__main__":
    unittest.main()
