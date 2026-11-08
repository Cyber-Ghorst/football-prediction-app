import unittest
from datetime import datetime, timezone

from system_diagnostics import build_system_diagnostics


def profile(name, count=10, stats=True):
    matches = [
        {
            "fixture_id": index,
            "goals_for": 1,
            "goals_against": 0,
            "statistics": {"Ball Possession": 55} if stats else {},
        }
        for index in range(count)
    ]
    return {
        "name": name,
        "matches": matches,
        "data_quality": {"matches_returned": count},
        "history_collection_diagnostics": {"fixtures_scanned": count},
        "tactical_summary": {
            "recency_weighting": {
                "matches_used": min(count, 10),
                "recent_matches": min(count, 5),
                "recent_weight": 0.60,
                "previous_matches": max(0, min(count, 10) - 5),
                "previous_weight": 0.40,
            }
        },
    }


def readiness(status="ready", verified=True, freshness="fresh"):
    return {
        "overall_status": status,
        "fixture": {
            "verified": verified,
            "reason": "Exact fixture not found." if not verified else "Exact fixture verified.",
            "source_freshness": freshness,
        },
    }


class SystemDiagnosticsTests(unittest.TestCase):
    NOW = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)

    def build(self, **overrides):
        args = {
            "season": 2026,
            "competition": "Premier League — England",
            "home_profile": profile("Home FC"),
            "away_profile": profile("Away FC"),
            "readiness": readiness(),
            "statistics_coverage": {
                "Home FC": {"core_metrics_with_any_data": 8, "core_metrics_total": 8},
                "Away FC": {"core_metrics_with_any_data": 8, "core_metrics_total": 8},
            },
            "provider_configuration": [
                {
                    "provider_id": "sportmonks",
                    "provider": "Sportmonks",
                    "credential_configured": True,
                    "credential_required": True,
                }
            ],
            "corroboration": None,
            "model_weights": {
                "recent_form": 0.20,
                "goals_scored": 0.10,
                "goals_conceded": 0.10,
                "home_away": 0.10,
                "strength_of_schedule": 0.15,
                "player_availability": 0.05,
                "tactical": 0.30,
            },
            "generated_at": self.NOW,
        }
        args.update(overrides)
        return build_system_diagnostics(**args)

    def test_all_checks_healthy_when_inputs_are_complete(self):
        report = self.build()
        self.assertEqual(report["overall_status"], "healthy")
        self.assertEqual(report["summary"]["failed"], 0)
        self.assertEqual(report["selected_context"]["primary_provider"], "sportmonks")

    def test_tactical_recency_metadata_is_exposed_and_audited(self):
        report = self.build()
        home = report["teams"]["home"]
        self.assertEqual(home["tactical_recency_weighting"]["recent_weight"], 0.60)
        self.assertEqual(home["tactical_recency_weighting"]["previous_weight"], 0.40)
        check = next(row for row in report["checks"] if row["id"] == "home_tactical_recency_weighting")
        self.assertEqual(check["status"], "pass")

    def test_incorrect_tactical_recency_metadata_fails_audit(self):
        home = profile("Home FC")
        home["tactical_summary"]["recency_weighting"]["recent_weight"] = 0.50
        report = self.build(home_profile=home)
        check = next(row for row in report["checks"] if row["id"] == "home_tactical_recency_weighting")
        self.assertEqual(check["status"], "fail")
        self.assertEqual(report["overall_status"], "blocked")

    def test_missing_tactical_recency_metadata_is_not_assumed_valid(self):
        home = profile("Home FC")
        home.pop("tactical_summary")
        report = self.build(home_profile=home)
        check = next(row for row in report["checks"] if row["id"] == "home_tactical_recency_weighting")
        self.assertEqual(check["status"], "info")
        self.assertIsNone(report["teams"]["home"]["tactical_recency_weighting"])

    def test_unverified_fixture_requires_attention_not_fake_verification(self):
        report = self.build(
            readiness=readiness("fixture_unverified", verified=False, freshness="unknown")
        )
        self.assertEqual(report["overall_status"], "attention_required")
        check = next(row for row in report["checks"] if row["id"] == "fixture_identity")
        self.assertEqual(check["status"], "warning")
        self.assertFalse(report["fixture"]["verified"])

    def test_insufficient_history_blocks_readiness(self):
        report = self.build(
            home_profile=profile("Home FC", count=4),
            readiness=readiness("insufficient_history"),
        )
        self.assertEqual(report["overall_status"], "blocked")
        self.assertEqual(report["summary"]["failed"] >= 1, True)

    def test_missing_primary_credential_is_reported(self):
        report = self.build(provider_configuration=[
            {
                "provider_id": "sportmonks",
                "provider": "Sportmonks",
                "credential_configured": False,
                "credential_required": True,
                "credential_name": "SPORTMONKS_API_TOKEN",
            }
        ])
        self.assertEqual(report["overall_status"], "blocked")
        check = next(row for row in report["checks"] if row["id"] == "primary_provider_configuration")
        self.assertEqual(check["status"], "fail")
        self.assertIn("SPORTMONKS_API_TOKEN", check["recommendation"])

    def test_duplicate_fixture_and_bad_score_are_flagged(self):
        home = profile("Home FC", count=2)
        home["matches"][1]["fixture_id"] = home["matches"][0]["fixture_id"]
        home["matches"][1]["goals_for"] = None
        report = self.build(home_profile=home)
        check = next(row for row in report["checks"] if row["id"] == "home_history_integrity")
        self.assertEqual(check["status"], "fail")
        self.assertEqual(report["teams"]["home"]["integrity"]["duplicate_fixture_ids"], ["0"])

    def test_unmatched_highlightly_candidate_is_review_only(self):
        corroboration = {
            "errors": {},
            "highlightly_diagnostics": {"records_normalized": 10},
            "team_history_coverage": {
                "Home FC": {
                    "unmatched_completed_candidates": [{"home": "Other", "away": "Home FC"}]
                }
            },
            "candidate_verification": [
                {"verification_status": "no_same_season_competition_fixture_returned_for_date"}
            ],
            "providers_matched": ["sportmonks", "highlightly"],
        }
        report = self.build(corroboration=corroboration)
        check = next(row for row in report["checks"] if row["id"] == "unmatched_external_results")
        self.assertEqual(check["status"], "warning")
        self.assertEqual(len(report["corroboration"]["candidate_verification"]), 1)

    def test_provider_record_counts_are_preserved_in_report(self):
        report = self.build(corroboration={
            "errors": {},
            "provider_records_returned": {"highlightly": 10, "api_ninjas": 8},
            "team_history_coverage": {
                "Home FC": {
                    "highlightly_completed_score_valid": 7,
                    "api_ninjas_completed_score_valid": 6,
                    "api_ninjas_exact_matches": 5,
                    "api_ninjas_unmatched_count": 1,
                }
            },
        })
        self.assertEqual(
            report["corroboration"]["provider_records_returned"],
            {"highlightly": 10, "api_ninjas": 8},
        )
        home = report["corroboration"]["team_history_coverage"]["Home FC"]
        self.assertEqual(home["api_ninjas_completed_score_valid"], 6)
        self.assertEqual(home["api_ninjas_exact_matches"], 5)

    def test_highlightly_selected_team_breakdown_is_preserved_in_report(self):
        breakdown = {
            "Brighton": {
                "normalized_team_records": 9,
                "status_counts": {"finished": 9},
                "raw_state_descriptions": {"Finished": 9},
                "completed_score_valid": 0,
                "finished_missing_score": 9,
                "sample_records": [{"highlightly_match_id": "brighton-1", "raw_state": {"description": "Finished"}}],
            },
            "Fulham": {
                "normalized_team_records": 10,
                "status_counts": {"finished": 10},
                "raw_state_descriptions": {"Finished": 10},
                "completed_score_valid": 10,
                "finished_missing_score": 0,
                "sample_records": [],
            },
        }
        report = self.build(corroboration={
            "errors": {},
            "highlightly_diagnostics": {
                "records_normalized": 280,
                "selected_team_breakdown": breakdown,
            },
            "team_history_coverage": {},
        })
        exported = report["corroboration"]["highlightly_diagnostics"]["selected_team_breakdown"]
        self.assertEqual(exported, breakdown)
        self.assertEqual(exported["Brighton"]["finished_missing_score"], 9)
        self.assertEqual(exported["Brighton"]["sample_records"][0]["raw_state"]["description"], "Finished")

    def test_api_ninjas_exact_history_coverage_passes(self):
        report = self.build(corroboration={
            "errors": {},
            "team_history_coverage": {
                "Brighton": {
                    "api_ninjas_completed_score_valid": 9,
                    "api_ninjas_exact_matches": 9,
                    "highlightly_completed_score_valid": 0,
                },
                "Fulham": {
                    "api_ninjas_completed_score_valid": 10,
                    "api_ninjas_exact_matches": 10,
                    "highlightly_completed_score_valid": 10,
                    "highlightly_exact_matches": 8,
                },
            },
        })
        ninjas = next(row for row in report["checks"] if row["id"] == "api_ninjas_history_corroboration")
        highlightly = next(row for row in report["checks"] if row["id"] == "highlightly_history_coverage")
        self.assertEqual(ninjas["status"], "pass")
        self.assertIn("Brighton: 9/9", ninjas["summary"])
        self.assertIn("Fulham: 10/10", ninjas["summary"])
        self.assertEqual(highlightly["status"], "info")
        self.assertIn("Fulham: 8/10", highlightly["summary"])

    def test_api_ninjas_unmatched_history_is_warning_not_imported(self):
        report = self.build(corroboration={
            "errors": {},
            "team_history_coverage": {
                "Brighton": {
                    "api_ninjas_completed_score_valid": 9,
                    "api_ninjas_exact_matches": 8,
                },
            },
        })
        check = next(row for row in report["checks"] if row["id"] == "api_ninjas_history_corroboration")
        self.assertEqual(check["status"], "warning")
        self.assertIn("8/9", check["summary"])
        self.assertIn("Do not import", check["recommendation"])

    def test_missing_highlightly_coverage_is_informational(self):
        report = self.build(corroboration={
            "errors": {},
            "team_history_coverage": {
                "Brighton": {"api_ninjas_completed_score_valid": 9, "api_ninjas_exact_matches": 9},
            },
        })
        check = next(row for row in report["checks"] if row["id"] == "highlightly_history_coverage")
        self.assertEqual(check["status"], "info")
        self.assertIn("coverage limitation", check["summary"])

    def test_targeted_verified_candidates_are_not_left_as_unmatched_warning(self):
        corroboration = {
            "errors": {},
            "team_history_coverage": {
                "Home FC": {
                    "unmatched_completed_candidates": [
                        {
                            "home": "Other",
                            "away": "Home FC",
                            "kickoff_utc": "2026-10-24T14:00:00+00:00",
                            "score": [0, 1],
                            "highlightly_match_id": "verified-1",
                        }
                    ]
                }
            },
            "candidate_verification": [
                {
                    "highlightly_candidate": {"highlightly_match_id": "verified-1"},
                    "verification_status": "exact_fixture_and_score_agree",
                }
            ],
        }
        report = self.build(corroboration=corroboration)
        check = next(row for row in report["checks"] if row["id"] == "unmatched_external_results")
        self.assertEqual(check["status"], "info")
        review = report["corroboration"]["candidate_review_summary"]
        self.assertEqual(len(review["verified_exact_fixture_and_score"]), 1)
        self.assertEqual(review["unresolved_candidates"], [])
        self.assertEqual(review["verified_candidates_added_to_prediction_history"], 0)

    def test_only_unresolved_candidates_remain_in_warning_count(self):
        corroboration = {
            "errors": {},
            "team_history_coverage": {
                "Home FC": {
                    "unmatched_completed_candidates": [
                        {"home": "A", "away": "Home FC", "highlightly_match_id": "verified-1"},
                        {"home": "B", "away": "Home FC", "highlightly_match_id": "unresolved-1"},
                    ]
                }
            },
            "candidate_verification": [
                {
                    "highlightly_candidate": {"highlightly_match_id": "verified-1"},
                    "verification_status": "exact_fixture_and_score_agree",
                },
                {
                    "highlightly_candidate": {"highlightly_match_id": "unresolved-1"},
                    "verification_status": "exact_fixture_found_score_disagrees",
                },
            ],
        }
        report = self.build(corroboration=corroboration)
        check = next(row for row in report["checks"] if row["id"] == "unmatched_external_results")
        self.assertEqual(check["status"], "warning")
        self.assertIn("1 unmatched Highlightly candidate", check["summary"])
        review = report["corroboration"]["candidate_review_summary"]
        self.assertEqual(len(review["verified_exact_fixture_and_score"]), 1)
        self.assertEqual(len(review["unresolved_candidates"]), 1)

    def test_five_to_nine_matches_are_informational_not_a_blocker(self):
        report = self.build(
            home_profile=profile("Home FC", count=9),
            readiness=readiness("limited_history"),
        )
        check = next(row for row in report["checks"] if row["id"] == "home_history_depth")
        self.assertEqual(check["status"], "info")
        self.assertIsNone(check["recommendation"])
        readiness_check = next(row for row in report["checks"] if row["id"] == "prediction_readiness")
        self.assertEqual(readiness_check["status"], "pass")
        self.assertNotEqual(report["overall_status"], "blocked")

    def test_historical_season_selects_api_football_as_primary(self):
        report = self.build(season=2024, provider_configuration=[
            {"provider_id": "api_football", "credential_configured": True}
        ])
        self.assertEqual(report["selected_context"]["primary_provider"], "api_football")

    def test_missing_statistics_are_warning_and_not_imputed(self):
        report = self.build(statistics_coverage={
            "Home FC": {"core_metrics_with_any_data": 0, "core_metrics_total": 8},
            "Away FC": {"core_metrics_with_any_data": 2, "core_metrics_total": 8},
        })
        check = next(row for row in report["checks"] if row["id"] == "home_statistics_coverage")
        self.assertEqual(check["status"], "warning")
        self.assertEqual(report["teams"]["home"]["statistics_coverage"]["core_metrics_with_any_data"], 0)

    def test_weights_are_checked_but_not_changed(self):
        weights = {"recent_form": 0.2, "tactical": 0.3}
        report = self.build(model_weights=weights)
        self.assertEqual(report["model_configuration"]["weights"], weights)
        self.assertEqual(report["model_configuration"]["weights_total"], 0.5)
        self.assertEqual(report["overall_status"], "attention_required")

    def test_recommended_actions_prioritize_failures_before_warnings(self):
        report = self.build(
            home_profile=profile("Home FC", count=4),
            readiness=readiness("insufficient_history", verified=False, freshness="stale"),
        )
        actions = report["recommended_actions"]
        self.assertTrue(actions)
        self.assertEqual(actions[0]["priority"], "urgent")
        self.assertTrue(any(row["priority"] == "next" for row in actions))
        self.assertTrue(all(row["action"] for row in actions))

    def test_healthy_report_has_no_corrective_actions(self):
        report = self.build()
        self.assertEqual(report["recommended_actions"], [])


if __name__ == "__main__":
    unittest.main()
