import unittest
from unittest.mock import Mock, patch

from provider_source_repository import audit_provider_source_evidence


class ProviderSourceEvidenceAuditTests(unittest.TestCase):
    @patch("provider_source_repository._connect")
    def test_audit_reports_staged_roster_evidence_read_only(self, connect):
        cursor = Mock()
        cursor.fetchall.side_effect = [
            [
                ("competition", 2, 2, 0, 0, 0, 0, 0, 0),
                ("team", 36, 0, 0, 0, 0, 0, 0, 0),
            ],
            [],
            [
                ({"raw_team": {"country": "France", "gender": "men", "age_group": None}},),
                ({"raw_team": {"type": "club", "squad": {"name": "first"}}},),
            ],
        ]
        cursor.fetchone.side_effect = [
            (36, 36, 36),
            (0,),
            (0,),
        ]
        connection = Mock()
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=False)
        connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        connection.cursor.return_value.__exit__ = Mock(return_value=False)
        connect.return_value = connection

        report = audit_provider_source_evidence(
            "postgresql://readonly", "LiveScore_Football"
        )
        self.assertTrue(report["read_only"])
        self.assertEqual(report["entity_counts"]["competition"]["total"], 2)
        self.assertEqual(report["entity_counts"]["competition"]["competition_type_known"], 0)
        self.assertEqual(report["entity_counts"]["team"]["total"], 36)
        self.assertEqual(report["season_source_evidence"]["rows"], [])
        self.assertEqual(report["team_evidence"]["incomplete_participant_evidence_count"], 36)
        self.assertEqual(report["team_evidence"]["country_missing_count"], 36)
        self.assertEqual(report["raw_team_payload_rows_scanned"], 2)
        self.assertEqual(report["raw_scope_key_path_counts"]["country"], {"raw_team.country": 1})
        self.assertEqual(report["raw_scope_key_path_counts"]["team_type"], {"raw_team.type": 1})
        self.assertEqual(report["raw_scope_key_path_counts"]["gender_scope"], {"raw_team.gender": 1})
        self.assertEqual(report["raw_scope_key_path_counts"]["age_group"], {})
        self.assertEqual(report["raw_scope_key_path_counts"]["squad_scope"], {"raw_team.squad": 1})
        self.assertEqual(report["fixture_rows"], 0)
        self.assertEqual(report["statistic_rows"], 0)
        self.assertEqual(report["canonical_entities_created"], 0)
        statements = [str(call.args[0]).strip().upper() for call in cursor.execute.call_args_list]
        self.assertTrue(statements[0].startswith("SET TRANSACTION READ ONLY"))
        self.assertTrue(all(
            statement.startswith("SELECT")
            for statement in statements[1:]
        ))
        self.assertFalse(any(
            statement.startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP"))
            for statement in statements
        ))


if __name__ == "__main__":
    unittest.main()
