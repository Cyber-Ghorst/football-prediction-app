"""Offline tests for the fail-closed OpenFooty readiness adapter."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from openfooty_contract import OpenFootyContractError
from openfooty_readiness import assess_openfooty_readiness


GOLDEN = (
    Path(__file__).parents[1]
    / "contracts"
    / "examples"
    / "prediction-data-response.v1.example.json"
)


def _payload():
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


class OpenFootyReadinessTests(unittest.TestCase):
    def test_golden_data_available_is_not_model_ready(self):
        report = assess_openfooty_readiness(
            _payload(),
            expected_request_id="request-20261128-001",
            now_utc="2026-11-28T08:00:00Z",
            freshness_limits_hours={"fixture": 36, "availability": 24},
        )
        self.assertEqual(report["response_status"], "DATA_AVAILABLE")
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["prediction_enabled"])
        self.assertFalse(report["prediction_executed"])
        self.assertFalse(report["ledger_write_performed"])
        self.assertFalse(report["weights_redistributed"])
        self.assertFalse(report["missing_data_imputed"])
        self.assertIn("home_away", report["teams"]["home"]["missing_components"])
        self.assertFalse(report["teams"]["home"]["availability_evidence_verified"])
        self.assertIn(
            "fixture_specific_tactical_compatibility_not_supplied",
            report["teams"]["home"]["blockers"],
        )

    def test_request_correlation_is_mandatory(self):
        with self.assertRaisesRegex(OpenFootyContractError, "request_id"):
            assess_openfooty_readiness(
                _payload(), expected_request_id="request-20261128-999"
            )

    def test_unknown_availability_is_not_available(self):
        payload = _payload()
        report = assess_openfooty_readiness(
            payload,
            expected_request_id=payload["request_id"],
            now_utc="2026-11-28T08:00:00Z",
            freshness_limits_hours={"fixture": 36, "availability": 24},
        )
        self.assertFalse(report["teams"]["home"]["availability_evidence_verified"])
        self.assertFalse(report["teams"]["away"]["availability_evidence_verified"])
        self.assertFalse(
            report["teams"]["home"]["top_level_components"]["player_availability"]
        )

    def test_missing_freshness_policy_fails_closed(self):
        payload = _payload()
        report = assess_openfooty_readiness(
            payload,
            expected_request_id=payload["request_id"],
            now_utc="2026-11-28T08:00:00Z",
        )
        self.assertEqual(report["status"], "blocked")
        self.assertIn("fixture:freshness_policy_not_supplied", report["blockers"])
        self.assertIn(
            "home:availability:freshness_policy_not_supplied", report["blockers"]
        )

    def test_post_kickoff_history_is_blocked(self):
        payload = _payload()
        payload["team_profiles"]["home"]["recent_matches"] = [
            {
                "fixture_id": "future-history",
                "kickoff_at_utc": "2026-11-30T12:00:00Z",
                "venue": "home",
                "opponent_id": "opponent",
                "opponent_name": "Opponent",
                "goals_for": 1,
                "goals_against": 0,
                "opponent_strength": 50,
                "statistics": {"Shots": 1},
                "source_provenance": [{
                    "source_id": "source",
                    "source_record_id": "record",
                    "source_url": None,
                    "retrieved_at_utc": "2026-11-28T07:00:00Z",
                    "source_updated_at_utc": None,
                    "payload_sha256": None,
                    "parser_version": "test",
                    "validation_status": "verified",
                    "raw_evidence_ref": None,
                }],
            }
        ]
        report = assess_openfooty_readiness(
            payload,
            expected_request_id=payload["request_id"],
            now_utc="2026-11-28T08:00:00Z",
            freshness_limits_hours={"fixture": 36, "availability": 24},
        )
        self.assertTrue(any(
            item.startswith("home:recent_match_not_pre_kickoff")
            for item in report["blockers"]
        ))
        self.assertEqual(report["status"], "blocked")

    def test_conflict_diagnostics_block_readiness(self):
        payload = _payload()
        payload["diagnostics"]["conflicts"] = [
            {"field": "fixture.kickoff_at_utc", "reason": "competing source values"}
        ]
        report = assess_openfooty_readiness(
            payload,
            expected_request_id=payload["request_id"],
            now_utc="2026-11-28T08:00:00Z",
            freshness_limits_hours={"fixture": 36, "availability": 24},
        )
        self.assertIn("engine_diagnostics:conflicts", report["blockers"])
        self.assertEqual(report["status"], "blocked")
