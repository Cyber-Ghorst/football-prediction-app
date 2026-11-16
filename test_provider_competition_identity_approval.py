import unittest

from provider_competition_identity_approval import build_approval_plan


class CompetitionIdentityApprovalTests(unittest.TestCase):
    def setUp(self):
        self.source = [
            {"provider":"api_football","provider_entity_id":"135","name":"Serie A","country":"Italy","competition_type":"League"},
            {"provider":"sportmonks","provider_entity_id":"384","name":"Serie A","country":"Italy","competition_type":"league"},
            {"provider":"api_football","provider_entity_id":"140","name":"La Liga","country":"Spain","competition_type":"League"},
            {"provider":"sportmonks","provider_entity_id":"564","name":"La Liga","country":"Spain","competition_type":"league"},
            {"provider":"api_football","provider_entity_id":"39","name":"Premier League","country":"England","competition_type":"League"},
            {"provider":"sportmonks","provider_entity_id":"8","name":"Premier League","country":"England","competition_type":"league"},
        ]
        self.canonical = [
            {"league_id":"sportmonks:384","name":"Serie A","country":"Italy"},
            {"league_id":"sportmonks:564","name":"La Liga","country":"Spain"},
            {"league_id":"sportmonks:8","name":"Premier League","country":"England"},
        ]

    def test_approves_only_three_exact_source_to_existing_canonical_pairs(self):
        plan, held = build_approval_plan(self.source, self.canonical, [], [])
        self.assertEqual(len(plan), 3)
        self.assertEqual(held, [])
        self.assertEqual(
            {(row["provider_entity_id"], row["canonical_entity_id"]) for row in plan},
            {("135","sportmonks:384"),("140","sportmonks:564"),("39","sportmonks:8")},
        )

    def test_holds_mismatched_country(self):
        source = [dict(row) for row in self.source]
        source[0]["country"] = "France"
        plan, held = build_approval_plan(source, self.canonical, [], [])
        self.assertEqual(len(plan), 2)
        self.assertEqual(held[0]["reason"], "normalized_identity_or_expected_name_country_mismatch")

    def test_holds_conflicting_existing_link(self):
        existing = [{
            "provider":"api_football","entity_type":"league","provider_entity_id":"135",
            "canonical_entity_id":"sportmonks:999",
        }]
        plan, held = build_approval_plan(self.source, self.canonical, existing, [])
        self.assertEqual(len(plan), 2)
        self.assertEqual(held[0]["reason"], "conflicting_existing_provider_link")

    def test_existing_link_requires_exact_approval_record(self):
        existing = [{
            "provider":"api_football","entity_type":"league","provider_entity_id":"135",
            "canonical_entity_id":"sportmonks:384",
        }]
        plan, held = build_approval_plan(self.source, self.canonical, existing, [])
        self.assertEqual(len(plan), 2)
        self.assertEqual(held[0]["reason"], "existing_link_lacks_exact_approval_record")

    def test_idempotently_skips_exactly_approved_link(self):
        existing = [{
            "provider":"api_football","entity_type":"league","provider_entity_id":"135",
            "canonical_entity_id":"sportmonks:384",
        }]
        approvals = [{
            "provider":"api_football","entity_type":"league","provider_entity_id":"135",
            "canonical_entity_id":"sportmonks:384","approval_reason":"Reviewed and approved exact match.",
        }]
        plan, held = build_approval_plan(self.source, self.canonical, existing, approvals)
        self.assertEqual(len(plan), 2)
        self.assertEqual(held[0]["reason"], "already_exactly_approved")


if __name__ == "__main__":
    unittest.main()
