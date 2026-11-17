import unittest
from datetime import datetime, timezone

from competition_readiness_audit import build_candidate_readiness_records, build_readiness_audit

NOW = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)


class CompetitionReadinessAuditTests(unittest.TestCase):
    def test_review_candidate_is_not_auto_approved(self):
        source = {
            "generated_at_utc": "2026-11-16T22:34:12Z",
            "provider_independent_catalogue": {
                "canonical_seed_review_candidates": [{
                    "competition_name": "Premier League",
                    "country": "England",
                    "providers": ["provider-a", "provider-b"],
                    "competition_type_evidence": {"status": "single_provider_type_evidence"},
                    "season_evidence": {
                        "status": "cross_provider_start_year_overlap",
                        "season_records": [
                            {"season_name": "2026/2027"},
                            {"season_name": "2026/2027"},
                        ],
                    },
                    "sources": [
                        {"provider": "provider-a", "competition_type": "league"},
                        {"provider": "provider-b"},
                    ],
                }],
            },
        }
        records = build_candidate_readiness_records(source)
        self.assertEqual(len(records), 1)
        self.assertFalse(records[0]["competition"]["identity_verified"])
        self.assertFalse(records[0]["season"]["identity_verified"])
        self.assertIsNone(records[0]["season"]["id"])
        self.assertFalse(records[0]["fixture"]["upcoming_valid"])

    def test_audit_exposes_candidate_scope_and_blockers(self):
        source = {
            "generated_at_utc": "2026-11-16T22:34:12Z",
            "provider_independent_catalogue": {
                "canonical_seed_review_candidates": [{
                    "competition_name": "La Liga",
                    "country": "Spain",
                    "providers": ["provider-a", "provider-b"],
                    "competition_type_evidence": {"status": "unknown_not_supplied"},
                    "season_evidence": {"status": "cross_provider_start_year_overlap"},
                    "sources": [],
                }],
            },
        }
        report = build_readiness_audit(source, now=NOW)
        self.assertEqual(report["summary"]["total_competition_seasons"], 1)
        self.assertEqual(report["summary"]["not_ready"], 1)
        self.assertEqual(report["source_candidate_count"], 1)
        self.assertIn("canonical competition/season identity", report["report_scope"])
        self.assertIn("competition_identity_not_explicitly_verified",
                      report["competitions"][0]["hard_blockers"])


if __name__ == "__main__":
    unittest.main()
