import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from tipmaster_benchmark import (
    TIPMASTER_CONSENSUS_URL,
    TipMasterError,
    fetch_tipmaster_consensus,
    normalize_tipmaster_match,
    normalize_tipmaster_payload,
)


def _row(**overrides):
    row = {
        "id": "daily:4821",
        "mode": "national",
        "competition": "Premier League",
        "home": "Arsenal",
        "away": "Chelsea",
        "status": "locked",
        "kickoffUtc": 1794312000,
        "deadlineUtc": 1794308400,
        "updatedAt": "2026-11-10T10:00:00Z",
        "result": None,
        "bands": {
            "basis": "national_hit_rate_8_weeks_before_week",
            "items": [
                {
                    "id": "top20",
                    "label": "Top 20%",
                    "sample": 96,
                    "majority": "home",
                    "outcome": {"home": 0.83, "draw": 0.12, "away": 0.05},
                },
                {
                    "id": "top25",
                    "label": "Top 25%",
                    "sample": 120,
                    "majority": "home",
                    "outcome": {"home": 0.81, "draw": 0.13, "away": 0.06},
                },
                {
                    "id": "all",
                    "label": "All players",
                    "sample": 480,
                    "majority": "home",
                    "outcome": {"home": 0.74, "draw": 0.16, "away": 0.10},
                },
            ],
        },
        "source": "https://tipmaster.de/agents/",
    }
    row.update(overrides)
    return row


class TipMasterBenchmarkTests(unittest.TestCase):
    def test_normalizes_frozen_national_consensus_and_keeps_provenance(self):
        item = normalize_tipmaster_match(
            _row(), fetched_at="2026-11-10T10:01:00+00:00"
        )
        self.assertIsNotNone(item)
        self.assertEqual(item["source"], "tipmaster")
        self.assertEqual(item["source_match_id"], "daily:4821")
        self.assertEqual(item["groups"]["top20"]["sample"], 96)
        self.assertAlmostEqual(item["groups"]["top20"]["shares"]["home"], 0.83)
        self.assertEqual(item["prediction_locked_at"], datetime.fromtimestamp(
            1794308400, tz=timezone.utc
        ).isoformat())
        self.assertEqual(item["fetched_at"], "2026-11-10T10:01:00+00:00")
        self.assertFalse(item["prediction_inputs_eligible"])
        self.assertNotIn("result", item)
        self.assertNotIn("score", item)

    def test_rejects_open_or_cancelled_matches(self):
        self.assertIsNone(normalize_tipmaster_match(_row(status="open")))
        self.assertIsNone(normalize_tipmaster_match(_row(status="cancelled")))

    def test_rejects_non_national_mode(self):
        self.assertIsNone(normalize_tipmaster_match(_row(mode="classic")))

    def test_rejects_deadline_at_or_after_kickoff(self):
        row = _row(deadlineUtc=1794312000)
        self.assertIsNone(normalize_tipmaster_match(row))
        row = _row(deadlineUtc=1794312001)
        self.assertIsNone(normalize_tipmaster_match(row))

    def test_rejects_missing_identity_or_invalid_kickoff(self):
        self.assertIsNone(normalize_tipmaster_match(_row(home=" ")))
        self.assertIsNone(normalize_tipmaster_match(_row(kickoffUtc=None)))

    def test_rejects_invalid_share_distribution(self):
        bands = _row()["bands"]
        bands["items"][0]["outcome"] = {"home": 0.8, "draw": 0.1, "away": 0.2}
        self.assertNotIn(
            "top20",
            normalize_tipmaster_match(_row(bands=bands))["groups"],
        )

    def test_ignores_group_below_minimum_cohort(self):
        bands = _row()["bands"]
        bands["items"][0]["sample"] = 19
        item = normalize_tipmaster_match(_row(bands=bands))
        self.assertNotIn("top20", item["groups"])
        self.assertIn("all", item["groups"])

    def test_payload_counts_rejected_and_duplicate_rows(self):
        payload = {
            "ok": True,
            "generatedAt": "2026-11-10T10:00:00Z",
            "matches": [
                _row(),
                _row(),
                _row(id="daily:4822", status="open"),
            ],
        }
        result = normalize_tipmaster_payload(payload)
        self.assertEqual(result["counts"], {
            "received": 3, "accepted": 1, "rejected": 1, "duplicates": 1
        })
        self.assertEqual(len(result["matches"]), 1)

    def test_invalid_response_envelope_raises(self):
        with self.assertRaises(TipMasterError):
            normalize_tipmaster_payload({"ok": False, "matches": []})
        with self.assertRaises(TipMasterError):
            normalize_tipmaster_payload({"ok": True, "matches": None})

    def test_fetch_uses_public_endpoint_and_user_agent(self):
        response = Mock()
        response.json.return_value = {
            "ok": True, "generatedAt": "2026-11-10T10:00:00Z", "matches": [_row()]
        }
        response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = response

        result = fetch_tipmaster_consensus(session=session)
        args, kwargs = session.get.call_args
        self.assertEqual(args[0], TIPMASTER_CONSENSUS_URL)
        self.assertEqual(kwargs["params"], {"mode": "national"})
        self.assertIn("User-Agent", kwargs["headers"])
        self.assertEqual(result["counts"]["accepted"], 1)

    def test_fetch_failure_is_wrapped_without_exposing_response_body(self):
        session = Mock()
        session.get.side_effect = RuntimeError("private response body")
        with self.assertRaises(TipMasterError) as raised:
            fetch_tipmaster_consensus(session=session)
        self.assertNotIn("private response body", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
