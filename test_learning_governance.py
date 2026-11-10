import unittest

from learning_governance import assess_promotion, evaluate_monitoring_window


def _report():
    return {
        "status": "ready_for_offline_comparison",
        "sample_gate": {
            "valid_targets_by_split": {"train": 140, "validation": 50, "test": 50}
        },
        "results": {
            "validation": {
                "incumbent": {"multiclass_brier": 0.60, "log_loss": 1.10, "top_outcome_calibration_error": 0.20},
                "candidate": {"multiclass_brier": 0.57, "log_loss": 1.10, "top_outcome_calibration_error": 0.205},
            },
            "test": {
                "incumbent": {"multiclass_brier": 0.60, "log_loss": 1.10, "top_outcome_calibration_error": 0.20},
                "candidate": {"multiclass_brier": 0.57, "log_loss": 1.10, "top_outcome_calibration_error": 0.205},
            },
        },
    }


def _candidate():
    return {
        "candidate_type": "trained_feature_model",
        "model_version": "candidate-v2",
        "artifact_sha256": "a" * 64,
    }


def _approval():
    return {
        "approved_by": "release-owner",
        "approved_at": "2026-11-10T12:00:00+00:00",
        "rollback_plan_confirmed": True,
        "monitoring_plan_confirmed": True,
    }


class PromotionGovernanceTests(unittest.TestCase):
    def test_valid_candidate_is_only_eligible_for_manual_review(self):
        result = assess_promotion(_report(), _candidate(), _approval())
        self.assertEqual(result["decision"], "eligible_for_manual_release_review")
        self.assertFalse(result["promotion_authorized"])
        self.assertEqual(result["reasons"], [])

    def test_diagnostic_prior_baseline_can_never_pass_as_trained_candidate(self):
        candidate = _candidate()
        candidate["candidate_type"] = "diagnostic_baseline"
        result = assess_promotion(_report(), candidate, _approval())
        self.assertEqual(result["decision"], "blocked")
        self.assertIn("candidate_is_not_a_trained_feature_model", result["reasons"])

    def test_small_sample_blocks_promotion(self):
        report = _report()
        report["sample_gate"]["valid_targets_by_split"]["test"] = 10
        result = assess_promotion(report, _candidate(), _approval())
        self.assertIn("insufficient_test_fixtures", result["reasons"])

    def test_brier_improvement_must_hold_on_validation_and_test(self):
        report = _report()
        report["results"]["test"]["candidate"]["multiclass_brier"] = 0.61
        result = assess_promotion(report, _candidate(), _approval())
        self.assertIn("test_performance_gate_failed", result["reasons"])

    def test_log_loss_and_calibration_regressions_are_bounded(self):
        report = _report()
        report["results"]["validation"]["candidate"]["log_loss"] = 1.3
        report["results"]["test"]["candidate"]["top_outcome_calibration_error"] = 0.30
        result = assess_promotion(report, _candidate(), _approval())
        self.assertIn("validation_performance_gate_failed", result["reasons"])
        self.assertIn("test_performance_gate_failed", result["reasons"])

    def test_missing_approval_and_rollback_confirmation_fail_closed(self):
        result = assess_promotion(_report(), _candidate())
        self.assertIn("missing_human_approval", result["reasons"])
        self.assertIn("rollback_plan_not_confirmed", result["reasons"])
        self.assertFalse(result["promotion_authorized"])

    def test_invalid_artifact_digest_is_rejected(self):
        candidate = _candidate()
        candidate["artifact_sha256"] = "not-a-sha"
        result = assess_promotion(_report(), candidate, _approval())
        self.assertIn("missing_or_invalid_candidate_artifact_sha256", result["reasons"])

    def test_monitoring_insufficient_window_does_not_claim_health(self):
        result = evaluate_monitoring_window({
            "model_version": "champion-v1", "matches": 12,
            "multiclass_brier": 0.5, "reference_multiclass_brier": 0.5,
            "log_loss": 0.9, "reference_log_loss": 0.9,
        })
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertFalse(result["rollback_recommended"])

    def test_monitoring_warns_on_material_degradation(self):
        result = evaluate_monitoring_window({
            "model_version": "champion-v1", "matches": 30,
            "multiclass_brier": 0.58, "reference_multiclass_brier": 0.50,
            "log_loss": 0.90, "reference_log_loss": 0.90,
        })
        self.assertEqual(result["status"], "degradation_warning")
        self.assertFalse(result["rollback_recommended"])

    def test_monitoring_recommends_rollback_review_on_severe_degradation(self):
        result = evaluate_monitoring_window({
            "model_version": "champion-v1", "matches": 40,
            "multiclass_brier": 0.70, "reference_multiclass_brier": 0.50,
            "log_loss": 1.30, "reference_log_loss": 1.00,
        })
        self.assertEqual(result["status"], "rollback_review_required")
        self.assertTrue(result["rollback_recommended"])
        self.assertFalse(result["automatic_rollback_performed"])

    def test_monitoring_rejects_non_finite_metrics(self):
        result = evaluate_monitoring_window({
            "model_version": "champion-v1", "matches": 40,
            "multiclass_brier": float("nan"), "reference_multiclass_brier": 0.5,
            "log_loss": 0.9, "reference_log_loss": 0.9,
        })
        self.assertEqual(result["status"], "insufficient_evidence")


if __name__ == "__main__":
    unittest.main()
