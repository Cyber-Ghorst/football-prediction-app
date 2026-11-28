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
        self.assertIn(
            "home:recent_history:freshness_policy_not_supplied", report["blockers"]
        )
        self.assertFalse(report["freshness_policy_complete"])

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


    def test_stale_recent_match_evidence_is_blocked(self):
        payload = _payload()
        payload["team_profiles"]["home"]["recent_matches"][0][
            "source_provenance"
        ][0]["retrieved_at_utc"] = "2026-11-20T07:45:00Z"
        report = assess_openfooty_readiness(
            payload,
            expected_request_id=payload["request_id"],
            now_utc="2026-11-28T08:00:00Z",
            freshness_limits_hours={
                "fixture": 36,
                "availability": 24,
                "history": 36,
            },
        )
        self.assertIn(
            "home:recent_match[0]:stale_evidence[0]", report["blockers"]
        )
        self.assertEqual(report["status"], "blocked")

    def test_future_dated_recent_match_evidence_is_blocked(self):
        payload = _payload()
        payload["team_profiles"]["home"]["recent_matches"][0][
            "source_provenance"
        ][0]["retrieved_at_utc"] = "2026-11-28T09:00:00Z"
        report = assess_openfooty_readiness(
            payload,
            expected_request_id=payload["request_id"],
            now_utc="2026-11-28T08:00:00Z",
            freshness_limits_hours={
                "fixture": 36,
                "availability": 24,
                "history": 36,
            },
        )
        self.assertIn(
            "home:recent_match[0]:future_retrieval_timestamp[0]",
            report["blockers"],
        )
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

    def test_stale_fixture_evidence_is_blocked(self):
        payload = _payload()
        payload["fixture"]["source_provenance"][0]["retrieved_at_utc"] = (
            "2026-11-20T07:45:00Z"
        )
        report = assess_openfooty_readiness(
            payload,
            expected_request_id=payload["request_id"],
            now_utc="2026-11-28T08:00:00Z",
            freshness_limits_hours={"fixture": 36, "availability": 24},
        )
        self.assertIn("fixture:stale_evidence[0]", report["blockers"])
        self.assertEqual(report["status"], "blocked")

    def test_future_dated_fixture_evidence_is_blocked(self):
        payload = _payload()
        payload["fixture"]["source_provenance"][0]["retrieved_at_utc"] = (
            "2026-11-28T09:00:00Z"
        )
        report = assess_openfooty_readiness(
            payload,
            expected_request_id=payload["request_id"],
            now_utc="2026-11-28T08:00:00Z",
            freshness_limits_hours={"fixture": 36, "availability": 24},
        )
        self.assertIn("fixture:future_retrieval_timestamp[0]", report["blockers"])
        self.assertEqual(report["status"], "blocked")

    def test_unknown_fixture_lifecycle_is_blocked(self):
        payload = _payload()
        payload["fixture"]["status"] = "unknown"
        report = assess_openfooty_readiness(
            payload,
            expected_request_id=payload["request_id"],
            now_utc="2026-11-28T08:00:00Z",
            freshness_limits_hours={"fixture": 36, "availability": 24},
        )
        self.assertIn(
            "fixture:lifecycle_not_scheduled:unknown", report["blockers"]
        )
        self.assertEqual(report["status"], "blocked")

    def test_missing_opponent_strength_stays_missing(self):
        payload = _payload()
        payload["team_profiles"]["home"]["recent_matches"][0][
            "opponent_strength"
        ] = None
        report = assess_openfooty_readiness(
            payload,
            expected_request_id=payload["request_id"],
            now_utc="2026-11-28T08:00:00Z",
            freshness_limits_hours={"fixture": 36, "availability": 24},
        )
        self.assertEqual(
            report["teams"]["home"]["opponent_strength_observation_count"], 0
        )
        self.assertIn(
            "opponent_strength_evidence_insufficient",
            report["teams"]["home"]["blockers"],
        )
        self.assertEqual(report["status"], "blocked")

    def test_invalid_fixture_utc_is_rejected_by_contract(self):
        payload = _payload()
        payload["fixture"]["kickoff_at_utc"] = "2026-11-29T15:00:00+03:00"
        with self.assertRaisesRegex(OpenFootyContractError, "UTC"):
            assess_openfooty_readiness(
                payload,
                expected_request_id=payload["request_id"],
                now_utc="2026-11-28T08:00:00Z",
                freshness_limits_hours={"fixture": 36, "availability": 24},
            )

    def test_verified_availability_is_not_an_impact_score(self):
        payload = _payload()
        evidence = {
            "source_id": "club-announcement",
            "source_record_id": "availability-001",
            "source_url": "https://example.invalid/availability",
            "retrieved_at_utc": "2026-11-28T07:30:00Z",
            "source_updated_at_utc": None,
            "payload_sha256": None,
            "parser_version": "test-v1",
            "validation_status": "verified",
            "raw_evidence_ref": "artifact://availability/001",
        }
        profile = payload["team_profiles"]["home"]
        profile["availability"] = {
            "status": "verified",
            "players": [{"player_id": "player-1", "status": "injured"}],
            "source_provenance": [evidence],
        }
        report = assess_openfooty_readiness(
            payload,
            expected_request_id=payload["request_id"],
            now_utc="2026-11-28T08:00:00Z",
            freshness_limits_hours={"fixture": 36, "availability": 24},
        )
        self.assertTrue(report["teams"]["home"]["availability_evidence_verified"])
        self.assertFalse(
            report["teams"]["home"]["top_level_components"]["player_availability"]
        )
        self.assertIn(
            "availability_impact_score_not_defined_in_v1",
            report["teams"]["home"]["blockers"],
        )
        self.assertEqual(report["status"], "blocked")

