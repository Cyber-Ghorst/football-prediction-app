import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from free_fixture_auto_promotion import run_automatic_fixture_promotion


NOW = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)


class AutomaticFixturePromotionTests(unittest.TestCase):
    def test_disabled_by_default_never_calls_promotion_or_staging(self):
        promote = Mock()
        stage = Mock()
        report = run_automatic_fixture_promotion(
            "provider-db", "neon-db", env={}, now=NOW,
            promotion_fn=promote, staging_fn=stage,
        )
        self.assertFalse(report["automatic_promotion_enabled"])
        self.assertEqual(report["canonical_fixture_writes"], 0)
        self.assertEqual(report["temporary_fixture_inserts"], 0)
        self.assertEqual(
            report["providers"]["openligadb"]["reason"],
            "global_auto_promotion_disabled",
        )
        promote.assert_not_called()
        stage.assert_not_called()

    def test_provider_requires_both_opt_in_and_terms_acknowledgement(self):
        promote = Mock()
        stage = Mock()
        env = {
            "FREE_FIXTURE_AUTO_PROMOTION_ENABLED": "true",
            "FREE_FIXTURE_AUTO_PROMOTE_OPENLIGADB": "true",
            "FREE_FIXTURE_TERMS_ACK_OPENLIGADB": "false",
        }
        report = run_automatic_fixture_promotion(
            "provider-db", "neon-db", env=env, now=NOW,
            promotion_fn=promote, staging_fn=stage,
        )
        self.assertEqual(
            report["providers"]["openligadb"]["reason"],
            "provider_terms_not_acknowledged",
        )
        promote.assert_not_called()
        stage.assert_not_called()

    def test_api_ninjas_requires_explicit_noncommercial_confirmation(self):
        promote = Mock()
        env = {
            "FREE_FIXTURE_AUTO_PROMOTION_ENABLED": "true",
            "FREE_FIXTURE_AUTO_PROMOTE_API_NINJAS": "true",
            "FREE_FIXTURE_TERMS_ACK_API_NINJAS": "true",
        }
        report = run_automatic_fixture_promotion(
            "provider-db", "neon-db", env=env, now=NOW,
            promotion_fn=promote,
        )
        self.assertEqual(
            report["providers"]["api_ninjas"]["reason"],
            "noncommercial_use_not_confirmed",
        )
        promote.assert_not_called()

    def test_only_explicitly_enabled_provider_is_promoted_and_staged(self):
        promote = Mock(return_value={
            "canonical_fixture_writes": 2,
            "decisions": {"promoted": 2, "duplicate_exact": 0, "blocked": 0},
            "staging_fixtures": [{"fixture_id": "openligadb:1"}, {"fixture_id": "openligadb:2"}],
        })
        stage = Mock(return_value={
            "fixtures_inserted": 2, "fixtures_already_present": 0,
            "fixtures_removed": 0, "prediction_ledger_modified": 0,
        })
        env = {
            "FREE_FIXTURE_AUTO_PROMOTION_ENABLED": "true",
            "FREE_FIXTURE_AUTO_PROMOTE_OPENLIGADB": "true",
            "FREE_FIXTURE_TERMS_ACK_OPENLIGADB": "true",
        }
        report = run_automatic_fixture_promotion(
            "provider-db", "neon-db", env=env, now=NOW,
            promotion_fn=promote, staging_fn=stage,
        )
        self.assertEqual(report["canonical_fixture_writes"], 2)
        self.assertEqual(report["temporary_fixture_inserts"], 2)
        self.assertEqual(report["providers"]["openligadb"]["status"], "completed")
        self.assertEqual(report["providers"]["highlightly"]["status"], "skipped")
        promote.assert_called_once()
        stage.assert_called_once_with("neon-db", [
            {"fixture_id": "openligadb:1"}, {"fixture_id": "openligadb:2"},
        ])
        self.assertEqual(promote.call_args.kwargs["licence_acknowledged"], True)

    def test_neon_failure_is_reported_without_losing_canonical_write_count(self):
        promote = Mock(return_value={
            "canonical_fixture_writes": 1,
            "decisions": {"promoted": 1},
            "staging_fixtures": [{"fixture_id": "openligadb:1"}],
        })
        stage = Mock(side_effect=RuntimeError("neon unavailable"))
        env = {
            "FREE_FIXTURE_AUTO_PROMOTION_ENABLED": "true",
            "FREE_FIXTURE_AUTO_PROMOTE_OPENLIGADB": "true",
            "FREE_FIXTURE_TERMS_ACK_OPENLIGADB": "true",
        }
        report = run_automatic_fixture_promotion(
            "provider-db", "neon-db", env=env, now=NOW,
            promotion_fn=promote, staging_fn=stage,
        )
        self.assertEqual(report["canonical_fixture_writes"], 1)
        self.assertEqual(
            report["providers"]["openligadb"]["status"],
            "canonical_promoted_staging_failed",
        )
        self.assertEqual(report["providers"]["openligadb"]["error_type"], "RuntimeError")


if __name__ == "__main__":
    unittest.main()
