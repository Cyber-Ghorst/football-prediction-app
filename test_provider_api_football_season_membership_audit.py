import unittest

from provider_api_football_season_membership_audit import (
    build_season_membership_report,
)


class ProviderAPIFootballSeasonMembershipAuditTests(unittest.TestCase):
    def test_live_response_presence_is_reported_without_approving_links(self):
        report = build_season_membership_report({
            "39": [{"team": {"id": 46, "name": "Leicester"}}],
        })
        premier_league = next(
            row for row in report["competitions"]
            if row["league_provider_id"] == "39"
        )
        self.assertEqual(len(premier_league["suspect_ids_returned"]), 1)
        self.assertEqual(premier_league["suspect_ids_returned"][0]["name"], "Leicester")
        self.assertEqual(report["provider_links_created"], 0)
        self.assertTrue(report["read_only"])

    def test_absent_ids_are_reported_as_stale_candidates_not_deleted(self):
        report = build_season_membership_report({"39": []})
        premier_league = next(
            row for row in report["competitions"]
            if row["league_provider_id"] == "39"
        )
        self.assertEqual(premier_league["status"], "suspect_records_absent_from_requested_season_endpoint")
        self.assertEqual(len(premier_league["suspect_ids_absent_from_response"]), 4)
        self.assertEqual(report["canonical_ids_assigned"], 0)
        self.assertEqual(report["provider_scope_fields_updated"], 0)

    def test_request_errors_do_not_misclassify_suspects_as_absent(self):
        report = build_season_membership_report(
            {}, {"39": "rate limit"}
        )
        premier_league = next(
            row for row in report["competitions"]
            if row["league_provider_id"] == "39"
        )
        self.assertEqual(premier_league["status"], "provider_request_error")
        self.assertEqual(premier_league["suspect_ids_absent_from_response"], [])
        self.assertEqual(report["suspect_records_absent_from_successful_responses"], 0)


if __name__ == "__main__":
    unittest.main()
