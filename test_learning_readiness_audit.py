import unittest
from unittest.mock import patch

from learning_readiness_audit import build_learning_readiness_audit


class LearningReadinessAuditTests(unittest.TestCase):
    @patch("learning_readiness_audit.load_prediction_ledger", return_value=[])
    def test_empty_live_ledger_fails_closed_without_changing_model(self, loader):
        report = build_learning_readiness_audit("neon-db")
        loader.assert_called_once_with("neon-db")
        self.assertEqual(report["ledger_record_count"], 0)
        self.assertEqual(report["sample_gate"]["status"], "insufficient_sample")
        self.assertEqual(report["offline_experiment"]["status"], "blocked_insufficient_sample")
        self.assertFalse(report["safety"]["live_model_modified"])
        self.assertFalse(report["safety"]["model_weights_modified"])
        self.assertFalse(report["safety"]["tvd_modified"])
        self.assertEqual(report["safety"]["prediction_ledger_writes"], 0)
        self.assertFalse(report["safety"]["production_promotion_permitted"])

    def test_requires_live_ledger_database_url(self):
        with self.assertRaisesRegex(ValueError, "DATABASE_URL"):
            build_learning_readiness_audit("")


if __name__ == "__main__":
    unittest.main()
