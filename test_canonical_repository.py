import unittest
from unittest.mock import patch

from canonical_repository import (
    classify_approved_link_rows,
    resolve_approved_legacy_source_id,
)


class CanonicalRepositoryResolverTests(unittest.TestCase):
    def test_no_approval_audit_match_is_unresolved(self):
        self.assertEqual(classify_approved_link_rows([])["status"], "unresolved")

    def test_one_audited_link_resolves_to_provider_id_not_canonical_id(self):
        result = classify_approved_link_rows([
            ("provider-team-77", "sportmonks:10", "openligadb", "team"),
        ])
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["source_entity_id"], "provider-team-77")
        self.assertNotEqual(result["source_entity_id"], result["canonical_entity_id"])

    def test_multiple_source_links_are_ambiguous(self):
        result = classify_approved_link_rows([
            ("provider-team-77", "sportmonks:10", "openligadb", "team"),
            ("provider-team-78", "sportmonks:10", "openligadb", "team"),
        ])
        self.assertEqual(result["status"], "ambiguous")
        self.assertIsNone(result["source_entity_id"])

    def test_duplicate_audit_rows_for_same_link_do_not_create_ambiguity(self):
        rows = [
            ("provider-team-77", "sportmonks:10", "openligadb", "team"),
            ("provider-team-77", "sportmonks:10", "openligadb", "team"),
        ]
        self.assertEqual(classify_approved_link_rows(rows)["status"], "resolved")

    def test_invalid_entity_type_fails_before_database_access(self):
        with self.assertRaisesRegex(ValueError, "Unsupported entity_type"):
            resolve_approved_legacy_source_id(
                "db", provider="openligadb", entity_type="stadium",
                canonical_entity_id="canonical:1",
            )

    def test_database_query_requires_exact_approval_audit_join(self):
        class Cursor:
            def __init__(self):
                self.query = ""
                self.params = None
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def execute(self, query, params):
                self.query, self.params = query, params
            def fetchall(self):
                return [("team-9", "sportmonks:1", "openligadb", "team")]

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
        with patch("canonical_repository._connect", return_value=Connection(cursor)):
            result = resolve_approved_legacy_source_id(
                "db", provider="openligadb", entity_type="team",
                canonical_entity_id="sportmonks:1",
            )
        self.assertEqual(result["status"], "resolved")
        self.assertIn("INNER JOIN provider_entity_link_approval_audit", cursor.query)
        self.assertIn("INNER JOIN football_teams", cursor.query)
        self.assertEqual(cursor.params, ("openligadb", "team", "sportmonks:1"))
        self.assertFalse(cursor.query.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER")))


if __name__ == "__main__":
    unittest.main()
