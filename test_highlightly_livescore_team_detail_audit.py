import unittest

from highlightly import HighlightlyError
from highlightly_livescore_team_detail_audit import (
    _highlightly_team_record,
    _safe_highlightly_request_failure,
    _verify_highlightly_detail,
    _verify_livescore_detail,
    build_exact_candidates,
)


class HighlightlyLiveScoreTeamDetailAuditTests(unittest.TestCase):
    def test_exact_candidate_requires_same_competition_and_2026_27_evidence(self):
        highlightly = [{
            "provider_entity_id": "143752",
            "name": "Bayer Leverkusen",
            "raw_payload": {
                "competition_provider_ids": ["67162"],
                "season_label": "2026/27",
            },
        }]
        livescore = [{
            "competition_provider_id": "ger.1",
            "provider_team_id": "131",
            "team_name": "Bayer Leverkusen",
            "season_label": "2026/27",
            "evidence_complete": True,
        }]
        candidates = build_exact_candidates(highlightly, livescore)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["highlightly_team_id"], "143752")
        self.assertEqual(candidates[0]["livescore_team_id"], "131")

    def test_wrong_season_and_incomplete_standings_are_held(self):
        highlightly = [{
            "provider_entity_id": "143752",
            "name": "Bayer Leverkusen",
            "raw_payload": {
                "competition_provider_ids": ["67162"],
                "season_label": "2025/26",
            },
        }]
        livescore = [{
            "competition_provider_id": "ger.1",
            "provider_team_id": "131",
            "team_name": "Bayer Leverkusen",
            "season_label": "2026/27",
            "evidence_complete": False,
        }]
        self.assertEqual(build_exact_candidates(highlightly, livescore), [])

    def test_duplicate_names_are_not_emitted_as_candidates(self):
        highlightly = [
            {"provider_entity_id": "1", "name": "Club A",
             "raw_payload": {"competition_provider_ids": ["67162"], "season_label": "2026/27"}},
            {"provider_entity_id": "2", "name": "Club A",
             "raw_payload": {"competition_provider_ids": ["67162"], "season_label": "2026/27"}},
        ]
        livescore = [{
            "competition_provider_id": "ger.1", "provider_team_id": "3",
            "team_name": "Club A", "season_label": "2026/27", "evidence_complete": True,
        }]
        self.assertEqual(build_exact_candidates(highlightly, livescore), [])

    def test_highlightly_detail_requires_exact_id_name_and_club_type(self):
        payload = [{"id": 143752, "name": "Bayer Leverkusen", "type": "club"}]
        record = _highlightly_team_record(payload)
        result = _verify_highlightly_detail("143752", "Bayer Leverkusen", record)
        self.assertEqual(result["status"], "provider_detail_confirmed")
        wrong_type = _verify_highlightly_detail(
            "143752", "Bayer Leverkusen",
            {"id": 143752, "name": "Bayer Leverkusen", "type": "national"},
        )
        self.assertEqual(wrong_type["status"], "held_detail_mismatch")

    def test_livescore_detail_requires_exact_provider_id_and_name(self):
        payload = {"club": {
            "id": "131", "displayName": "Bayer Leverkusen",
            "country": None, "catalogSource": "club-catalog",
        }}
        result = _verify_livescore_detail("131", "Bayer Leverkusen", payload)
        self.assertEqual(result["status"], "provider_detail_confirmed")
        self.assertIsNone(result["country_value"])
        wrong_id = _verify_livescore_detail("999", "Bayer Leverkusen", payload)
        self.assertEqual(wrong_id["status"], "held_detail_mismatch")

    def test_highlightly_failure_records_safe_http_status_and_quota_metadata(self):
        class Client:
            last_metadata = {
                "http_status": 429,
                "requests_limit": "1000",
                "requests_remaining": "0",
                "authorization": "must-not-be-recorded",
            }

        detail = _safe_highlightly_request_failure(
            HighlightlyError("Highlightly rate limit or daily quota reached (HTTP 429)."),
            Client(),
        )
        self.assertEqual(detail["status"], "provider_request_failed")
        self.assertEqual(detail["safe_error"], "Highlightly rate limit or daily quota reached (HTTP 429).")
        self.assertEqual(detail["response_metadata"], {
            "http_status": 429, "requests_limit": "1000", "requests_remaining": "0",
        })
        self.assertNotIn("authorization", detail["response_metadata"])

    def test_non_adapter_exception_does_not_persist_arbitrary_message(self):
        class Client:
            last_metadata = {}

        detail = _safe_highlightly_request_failure(
            RuntimeError("sensitive request detail"), Client(),
        )
        self.assertEqual(detail["error_type"], "RuntimeError")
        self.assertNotIn("safe_error", detail)


if __name__ == "__main__":
    unittest.main()
