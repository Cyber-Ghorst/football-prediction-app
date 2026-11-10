import unittest
from datetime import datetime, timezone

from conflict_audit import build_conflict_resolution_audit


class ConflictAuditTests(unittest.TestCase):
    def setUp(self):
        self.match = {
            "kickoff_utc": "2026-11-10T19:00:00Z",
            "home": {"name": "Arsenal"},
            "away": {"name": "Chelsea"},
            "source_ids": {"sportmonks": "sm-1", "highlightly": "hl-1"},
            "reconciliation": {
                "home_score": {
                    "status": "conflict",
                    "provider": "sportmonks",
                    "observations": [
                        {"provider": "sportmonks", "value": 2, "source_id": "sm-1"},
                        {"provider": "highlightly", "value": 3, "source_id": "hl-1"},
                    ],
                    "corroborating_providers": [],
                    "conflicting_providers": ["highlightly"],
                    "message": "Selected sportmonks by configured results priority.",
                },
                "away_score": {
                    "status": "corroborated",
                    "provider": "sportmonks",
                    "observations": [],
                },
            },
        }

    def test_conflict_event_retains_all_observations_and_policy_decision(self):
        events = build_conflict_resolution_audit(
            [self.match], competition="Premier League", season=2026,
            recorded_at=datetime(2026, 11, 10, tzinfo=timezone.utc),
        )
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["triage_status"], "resolved_by_configured_priority")
        self.assertEqual(event["selected_provider"], "sportmonks")
        self.assertEqual(event["selected_value"], 2)
        self.assertEqual(len(event["observations"]), 2)
        self.assertEqual(event["conflicting_providers"], ["highlightly"])
        self.assertFalse(event["manual_override"])
        self.assertFalse(event["prediction_inputs_modified"])
        self.assertEqual(event["fixture_identity"]["home_team"], "Arsenal")

    def test_missing_unique_selected_observation_remains_unresolved(self):
        match = dict(self.match)
        match["reconciliation"] = {
            "home_score": {
                "status": "conflict", "provider": None,
                "observations": [{"provider": "highlightly", "value": 3}],
            }
        }
        event = build_conflict_resolution_audit(
            [match], competition="Premier League", season=2026
        )[0]
        self.assertEqual(event["triage_status"], "unresolved")
        self.assertIsNone(event["selected_value"])
        self.assertEqual(len(event["observations"]), 1)

    def test_non_conflicted_fields_are_not_audited(self):
        match = dict(self.match)
        match["reconciliation"] = {
            "home_score": {"status": "single_source", "provider": "sportmonks"}
        }
        self.assertEqual(
            build_conflict_resolution_audit(
                [match], competition="Premier League", season=2026
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
