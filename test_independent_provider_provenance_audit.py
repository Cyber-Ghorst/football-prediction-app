"""Tests for the independent provider provenance inventory."""
import unittest
from unittest.mock import patch

import independent_provider_provenance_audit as audit


class _Column:
    def __init__(self, name):
        self.name = name


class _Cursor:
    def __init__(self):
        self.description = []
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql):
        self.calls.append(sql)
        self.description = []

    def fetchall(self):
        return []


class _Connection:
    def __init__(self):
        self.fake_cursor = _Cursor()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self.fake_cursor


class IndependentProviderAuditTests(unittest.TestCase):
    def test_report_distinguishes_canonical_and_snapshot_providers(self):
        report = audit.build_report({
            "canonical_fixture_provenance": [
                {"source_provider": "sportmonks"},
                {"source_provider": "OpenLigaDB"},
            ],
            "canonical_statistics_provenance": [
                {"source_provider": "sportmonks"},
                {"source_provider": "Highlightly"},
            ],
            "archived_provider_snapshots": [
                {"provider": "OpenFootball"},
            ],
            "approved_entity_links": [],
            "provider_sync_state": [],
        })
        self.assertEqual(
            report["canonical_fixture_providers"], ["OpenLigaDB", "sportmonks"]
        )
        self.assertEqual(
            report["canonical_statistics_providers"], ["Highlightly", "sportmonks"]
        )
        self.assertEqual(report["archived_snapshot_providers"], ["OpenFootball"])
        self.assertTrue(report["independent_canonical_fixture_provider_present"])
        self.assertTrue(report["independent_canonical_statistics_provider_present"])
        self.assertFalse(report["database_writes"])

    def test_report_does_not_treat_snapshot_only_provider_as_canonical(self):
        report = audit.build_report({
            "canonical_fixture_provenance": [{"source_provider": "sportmonks"}],
            "canonical_statistics_provenance": [],
            "archived_provider_snapshots": [{"provider": "OpenFootball"}],
            "approved_entity_links": [],
            "provider_sync_state": [],
        })
        self.assertFalse(report["independent_canonical_fixture_provider_present"])
        self.assertEqual(report["archived_snapshot_providers"], ["OpenFootball"])

    def test_empty_database_url_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "PROVIDER_DATABASE_URL"):
            audit.collect_provider_provenance("")


if __name__ == "__main__":
    unittest.main()
