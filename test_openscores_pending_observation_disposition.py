import unittest
from unittest.mock import patch

import openscores_observation_store as store


EXPECTED = {("4", "4"): 50, ("6", "6"): 50, ("7", "7"): 50}
LINKS = {"fixture": 150, "league": 3, "season": 3, "team": 60}


def snapshot(*, unresolved=150, linked=150, discarded=0, unresolved_groups=None, discarded_groups=None):
    outside = 300 - discarded
    return {
        "total_observations": 300,
        "status_counts": {
            "outside_upcoming_window": outside,
            "discarded_by_operator": discarded,
        },
        "unresolved_unlinked_observations": unresolved,
        "linked_observations": linked,
        "discarded_by_operator": discarded,
        "unresolved_groups": [
            {"league_id": k[0], "season_id": k[1], "count": v}
            for k, v in sorted((unresolved_groups or {}).items())
        ],
        "unresolved_group_map": dict(unresolved_groups or {}),
        "discarded_groups": [
            {"league_id": k[0], "season_id": k[1], "count": v}
            for k, v in sorted((discarded_groups or {}).items())
        ],
        "discarded_group_map": dict(discarded_groups or {}),
        "openscores_provider_link_counts": dict(LINKS),
    }

class FakeCursor:
    def __init__(self, rowcount=150):
        self.rowcount = rowcount
        self.statements = []

    def execute(self, sql, params=None):
        self.statements.append((sql, params))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self._cursor


class OpenScoresPendingDispositionTests(unittest.TestCase):
    def test_read_only_preflight_requires_exact_150_pending_rows(self):
        with patch.object(
            store, "_openscores_observation_snapshot",
            return_value=snapshot(unresolved_groups=EXPECTED),
        ), patch.object(store, "_connect"):
            report = store.audit_pending_openscores_observations("postgres://test")
        self.assertTrue(report["read_only"])
        self.assertTrue(report["preflight_passed"])
        self.assertEqual(report["unresolved_unlinked_observations"], 150)
        self.assertEqual(report["matched"], 150)
        self.assertEqual(report["total_observations"], 300)

    def test_discard_updates_only_pending_rows_and_preserves_links_and_raw_rows(self):
        cursor = FakeCursor()
        before = snapshot(unresolved_groups=EXPECTED)
        after = snapshot(
            unresolved=0, linked=150, discarded=150,
            unresolved_groups={}, discarded_groups=EXPECTED,
        )
        with patch.object(
            store, "_openscores_observation_snapshot",
            side_effect=[before, after],
        ), patch.object(store, "_connect", return_value=FakeConnection(cursor)):
            report = store.discard_pending_openscores_observations("postgres://test")
        self.assertEqual(report["status"], "discarded_by_operator")
        self.assertEqual(report["updated"], 150)
        self.assertTrue(report["raw_records_retained"])
        self.assertTrue(report["provider_links_unchanged"])
        self.assertEqual(len(cursor.statements), 1)
        sql, params = cursor.statements[0]
        self.assertIn("reconciliation_status = 'discarded_by_operator'", sql)
        self.assertIn("reconciliation_status = 'pending_entity_mapping'", sql)
        self.assertIn("canonical_fixture_id IS NULL", sql)
        self.assertIn("raw provider observation retained for audit", params[0])

    def test_discard_fails_closed_if_pending_cohort_is_not_exactly_150(self):
        cursor = FakeCursor()
        before = snapshot(
            unresolved=149,
            unresolved_groups={("4", "4"): 50, ("6", "6"): 50, ("7", "7"): 49},
        )
        with patch.object(
            store, "_openscores_observation_snapshot", return_value=before,
        ), patch.object(store, "_connect", return_value=FakeConnection(cursor)):
            with self.assertRaises(RuntimeError):
                store.discard_pending_openscores_observations("postgres://test")
        self.assertFalse(any("UPDATE provider_fixture_observations" in sql for sql, _ in cursor.statements))

    def test_reconciliation_and_upsert_preserve_discarded_terminal_status(self):
        source = open(store.__file__, encoding="utf-8").read()
        self.assertIn("reconciliation_status NOT IN ('matched', 'discarded_by_operator')", source)
        self.assertIn("provider_fixture_observations.reconciliation_status = 'discarded_by_operator'", source)


if __name__ == "__main__":
    unittest.main()
