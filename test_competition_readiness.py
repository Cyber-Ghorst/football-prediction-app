import unittest
from datetime import datetime, timezone

from competition_readiness import (
    build_competition_readiness_report,
    evaluate_competition_readiness,
)

NOW = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)


def ready_evidence():
    return {
        "competition": {
            "name": "Premier League",
            "country": "England",
            "type": "league",
            "identity_verified": True,
        },
        "season": {
            "id": "canonical-season-2026-27",
            "name": "2026/2027",
            "active": True,
            "identity_verified": True,
        },
        "teams": {
            "participating_count": 2,
            "approved_mapping_count": 2,
            "history_by_team": {"team-home": 10, "team-away": 10},
            "statistics_complete_by_team": {"team-home": True, "team-away": True},
            "tactical_components_by_team": {
                "team-home": {
                    "playing_style": "possession",
                    "defensive_structure": "mid-block",
                    "attacking_approach": "wide-overloads",
                },
                "team-away": {
                    "playing_style": "transition",
                    "defensive_structure": "low-block",
                    "attacking_approach": "direct",
                },
            },
        },
        "fixture": {"upcoming_valid": True, "source_freshness": "fresh"},
        "evidence_generated_at": "2026-11-17T11:00:00Z",
    }


class CompetitionReadinessTests(unittest.TestCase):
    def test_fully_verified_competition_season_passes(self):
        result = evaluate_competition_readiness(ready_evidence(), now=NOW)
        self.assertEqual(result["status"], "prediction_ready")
        self.assertTrue(result["prediction_ready"])
        self.assertEqual(result["hard_blockers"], [])
        self.assertEqual(result["improvement_blockers"], [])
        self.assertFalse(result["writes_performed"])

    def test_name_country_and_season_overlap_do_not_replace_explicit_identity(self):
        evidence = ready_evidence()
        evidence["competition"]["identity_verified"] = False
        evidence["season"]["identity_verified"] = False
        result = evaluate_competition_readiness(evidence, now=NOW)
        self.assertEqual(result["status"], "not_ready")
        self.assertIn("competition_identity_not_explicitly_verified", result["hard_blockers"])
        self.assertIn("season_identity_not_explicitly_verified", result["hard_blockers"])

    def test_unmapped_team_blocks_readiness(self):
        evidence = ready_evidence()
        evidence["teams"]["approved_mapping_count"] = 1
        result = evaluate_competition_readiness(evidence, now=NOW)
        self.assertEqual(result["status"], "not_ready")
        self.assertIn("not_all_participating_teams_have_approved_mappings", result["hard_blockers"])

    def test_inactive_season_blocks_readiness(self):
        evidence = ready_evidence()
        evidence["season"]["active"] = False
        self.assertEqual(evaluate_competition_readiness(evidence, now=NOW)["status"], "not_ready")

    def test_five_to_nine_matches_are_partial_not_full_readiness(self):
        evidence = ready_evidence()
        evidence["teams"]["history_by_team"]["team-home"] = 7
        result = evaluate_competition_readiness(evidence, now=NOW)
        self.assertEqual(result["status"], "partially_ready")
        self.assertFalse(result["prediction_ready"])
        self.assertIn("history_below_target:team-home", result["improvement_blockers"])

    def test_less_than_five_matches_is_partial_with_explicit_blocker(self):
        evidence = ready_evidence()
        evidence["teams"]["history_by_team"]["team-away"] = 4
        result = evaluate_competition_readiness(evidence, now=NOW)
        self.assertEqual(result["status"], "partially_ready")
        self.assertIn("insufficient_history:team-away", result["improvement_blockers"])

    def test_missing_core_statistics_prevents_full_readiness(self):
        evidence = ready_evidence()
        evidence["teams"]["statistics_complete_by_team"]["team-home"] = False
        result = evaluate_competition_readiness(evidence, now=NOW)
        self.assertEqual(result["status"], "partially_ready")
        self.assertFalse(result["statistics_complete"])

    def test_missing_tactical_component_prevents_full_readiness(self):
        evidence = ready_evidence()
        evidence["teams"]["tactical_components_by_team"]["team-away"]["defensive_structure"] = None
        result = evaluate_competition_readiness(evidence, now=NOW)
        self.assertEqual(result["status"], "partially_ready")
        self.assertFalse(result["tactical_components_complete"])

    def test_stale_fixture_data_prevents_full_readiness(self):
        evidence = ready_evidence()
        evidence["fixture"]["source_freshness"] = "stale"
        result = evaluate_competition_readiness(evidence, now=NOW)
        self.assertEqual(result["status"], "partially_ready")
        self.assertIn("fixture_source_not_confirmed_fresh", result["improvement_blockers"])

    def test_missing_fixture_or_type_is_not_ready(self):
        evidence = ready_evidence()
        evidence["fixture"]["upcoming_valid"] = False
        evidence["competition"]["type"] = None
        result = evaluate_competition_readiness(evidence, now=NOW)
        self.assertEqual(result["status"], "not_ready")
        self.assertIn("no_verified_upcoming_fixture", result["hard_blockers"])
        self.assertIn("competition_name_country_or_type_missing", result["hard_blockers"])

    def test_missing_timestamp_is_reported(self):
        evidence = ready_evidence()
        evidence["evidence_generated_at"] = None
        result = evaluate_competition_readiness(evidence, now=NOW)
        self.assertEqual(result["status"], "partially_ready")
        self.assertIn("evidence_timestamp_missing_or_invalid", result["improvement_blockers"])

    def test_naive_clock_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_competition_readiness(ready_evidence(), now=datetime(2026, 11, 17, 12))

    def test_report_counts_statuses_and_never_writes(self):
        ready = ready_evidence()
        partial = ready_evidence()
        partial["teams"]["history_by_team"]["team-home"] = 8
        blocked = ready_evidence()
        blocked["competition"]["identity_verified"] = False
        report = build_competition_readiness_report([ready, partial, blocked], now=NOW)
        self.assertEqual(report["summary"], {
            "total_competition_seasons": 3,
            "not_ready": 1,
            "partially_ready": 1,
            "prediction_ready": 1,
        })
        self.assertFalse(report["policy"]["missing_data_imputed"])
        self.assertFalse(report["policy"]["canonical_identity_or_fixture_writes"])
        self.assertFalse(report["policy"]["prediction_ledger_writes"])
        self.assertFalse(report["policy"]["model_weights_changed"])


if __name__ == "__main__":
    unittest.main()
