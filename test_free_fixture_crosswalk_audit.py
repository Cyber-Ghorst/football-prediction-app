import unittest
from unittest.mock import patch

from free_fixture_crosswalk_audit import PROVIDERS, build_crosswalk_audit


class FreeFixtureCrosswalkAuditTests(unittest.TestCase):
    @patch("free_fixture_crosswalk_audit.build_provider_crosswalk_review_report")
    def test_reports_provider_entity_and_candidate_progress(self, builder):
        builder.return_value = {
            "snapshot_count": 2,
            "observation_count": 30,
            "source_entity_counts": {"leagues": 2, "seasons": 2, "teams": 20},
            "existing_link_counts": {"leagues": 1, "seasons": 1, "teams": 5},
            "candidates": {
                "leagues": [
                    {"provider_entity_id": "league-a", "status": "candidate_requires_manual_approval"},
                    {"provider_entity_id": "league-b", "status": "already_linked"},
                ],
                "seasons": [],
                "teams": [{"provider_entity_id": "team-a", "status": "no_exact_candidate"}],
            },
        }
        report = build_crosswalk_audit("provider-db")
        self.assertEqual(set(report["providers"]), set(PROVIDERS))
        first = report["providers"]["openligadb"]
        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["categories"]["leagues"]["candidate_count"], 2)
        self.assertEqual(
            first["categories"]["leagues"]["status_counts"],
            {"already_linked": 1, "candidate_requires_manual_approval": 1},
        )
        self.assertEqual(report["automatic_mapping_approvals"], 0)
        self.assertEqual(report["canonical_fixture_writes"], 0)
        self.assertEqual(report["prediction_ledger_writes"], 0)
        self.assertEqual(builder.call_count, len(PROVIDERS))

    @patch("free_fixture_crosswalk_audit.build_provider_crosswalk_review_report")
    def test_isolates_provider_failure_without_losing_other_reports(self, builder):
        builder.side_effect = [RuntimeError("db error")] + [{
            "snapshot_count": 0,
            "observation_count": 0,
            "source_entity_counts": {},
            "existing_link_counts": {},
            "candidates": {},
        }] * (len(PROVIDERS) - 1)
        report = build_crosswalk_audit("provider-db")
        self.assertEqual(report["providers"]["openligadb"]["status"], "error")
        self.assertEqual(report["providers"]["openligadb"]["error_type"], "RuntimeError")
        self.assertEqual(report["providers"]["openfootball"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
