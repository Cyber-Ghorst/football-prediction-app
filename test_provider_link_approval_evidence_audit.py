import unittest
from unittest.mock import patch

from provider_link_approval_evidence_audit import (
    ORPHAN_APPROVAL_SQL,
    OPENSCORES_SAMPLE_SQL,
    SUMMARY_SQL,
    UNMATCHED_SAMPLE_SQL,
    audit_provider_link_approval_evidence,
)


class ProviderLinkApprovalEvidenceAuditTests(unittest.TestCase):
    def test_read_only_audit_uses_full_identity_tuple_and_separate_evidence_paths(self):
        class Cursor:
            def __init__(self):
                self.statements = []
                self.results = [
                    [
                        ("openscores", "fixture", 150, 0, 0, 150, 0, 0, 0, 0, 150),
                        ("openscores", "team", 60, 0, 0, 0, 60, 0, 0, 0, 0),
                        ("sportmonks", "team", 88, 0, 0, 88, 0, 0, 0, 88, 0),
                    ],
                    [("other_provider", "team", 1)],
                    [("other_provider", "team", "l1", "team-1", "canonical-1",
                      "no_approval_record_for_link_id", False, False, False)],
                    [("openscores-link-1", "team", "os-team-1", "canonical-team-1",
                      False, True, False)],
                ]
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def execute(self, query, params=None):
                self.statements.append((query, params))
            def fetchall(self):
                return self.results.pop(0)

        class Connection:
            def __init__(self, cursor):
                self.cursor_value = cursor
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def cursor(self):
                return self.cursor_value

        cursor = Cursor()
        with patch("provider_link_approval_evidence_audit._connect",
                   return_value=Connection(cursor)):
            report = audit_provider_link_approval_evidence("db")

        self.assertTrue(report["read_only"])
        self.assertFalse(report["database_writes"])
        self.assertEqual(report["canonical_ids_assigned"], 0)
        self.assertEqual(report["provider_links_created"], 0)
        self.assertEqual(report["prediction_ledger_touched"], False)
        self.assertEqual(len(report["provider_entity_type_counts"]), 3)
        self.assertEqual(report["provider_entity_type_counts"][0]["exact_approval_matches"], 0)
        self.assertEqual(report["provider_entity_type_counts"][0]["reconciled_openscores_fixture_links"], 150)
        self.assertEqual(report["provider_entity_type_counts"][2]["sportmonks_native_identity_anchors"], 88)
        self.assertEqual(report["unmatched_link_samples"][0]["approval_record_state"],
                         "no_approval_record_for_link_id")
        self.assertTrue(report["openscores_link_samples"][0]["has_exact_verified_evidence"])
        self.assertEqual(cursor.statements[0], ("SET TRANSACTION READ ONLY", ()))
        self.assertEqual(cursor.statements[1][0], SUMMARY_SQL)
        self.assertEqual(cursor.statements[2][0], ORPHAN_APPROVAL_SQL)
        self.assertEqual(cursor.statements[3][0], UNMATCHED_SAMPLE_SQL)
        self.assertEqual(cursor.statements[4][0], OPENSCORES_SAMPLE_SQL)
        for query, _ in cursor.statements[1:]:
            self.assertTrue(query.lstrip().upper().startswith("SELECT"))
        for query in (SUMMARY_SQL, UNMATCHED_SAMPLE_SQL, OPENSCORES_SAMPLE_SQL):
            self.assertIn("approval.provider = link.provider", query)
            self.assertIn("approval.entity_type = link.entity_type", query)
            self.assertIn("approval.provider_entity_id = link.provider_entity_id", query)
            self.assertIn("approval.canonical_entity_id = link.canonical_entity_id", query)
            self.assertIn("LENGTH(BTRIM(approval.approval_reason)) >= 12", query)

    def test_requires_database_url_before_connecting(self):
        with patch("provider_link_approval_evidence_audit._connect") as connect:
            with self.assertRaisesRegex(ValueError, "PROVIDER_DATABASE_URL"):
                audit_provider_link_approval_evidence("")
            connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
