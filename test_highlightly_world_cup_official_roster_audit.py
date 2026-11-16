import unittest

from highlightly_world_cup_official_roster_audit import (
    FIFA_OFFICIAL_TEAMS,
    HIGHLIGHTLY_PARTICIPANTS,
    build_official_matches,
    audit_world_cup_roster,
)


class HighlightlyWorldCupOfficialRosterAuditTests(unittest.TestCase):
    def test_all_48_highlightly_participants_match_fifa_official_roster(self):
        rows = build_official_matches()
        self.assertEqual(len(HIGHLIGHTLY_PARTICIPANTS), 48)
        self.assertEqual(len(FIFA_OFFICIAL_TEAMS), 48)
        self.assertEqual(len(rows), 48)
        self.assertTrue(all(row["official_roster_match"] for row in rows))
        self.assertEqual(
            len({row["fifa_official_team_name"] for row in rows}),
            48,
        )

    def test_seven_explicit_name_variants_are_reviewed_aliases(self):
        rows = build_official_matches()
        aliases = [row for row in rows if row["name_match_method"] == "explicit_official_name_alias"]
        self.assertEqual(len(aliases), 7)
        self.assertEqual(
            {row["highlightly_team_name"] for row in aliases},
            {
                "Ivory Coast", "Cape Verde", "South Korea", "Iran",
                "Czech Republic", "Turkey", "Bosnia & Herzegovina",
            },
        )

    def test_official_roster_context_produces_non_promotable_national_scope_candidates(self):
        report = audit_world_cup_roster()
        self.assertEqual(report["official_roster_matches"], 48)
        self.assertEqual(report["scope_candidate_count"], 48)
        self.assertEqual(report["provider_team_detail_lookup"]["confirmed"], 0)
        self.assertEqual(report["provider_team_detail_lookup"]["failed"], 48)
        self.assertTrue(all(row["scope_candidate"] is not None for row in report["results"]))
        self.assertTrue(all(row["promotion_allowed"] is False for row in report["results"]))
        self.assertTrue(all(
            row["scope_candidate"]["provider_team_type_field_confirmed"] is False
            for row in report["results"]
        ))

    def test_duplicate_provider_ids_fail_closed(self):
        import highlightly_world_cup_official_roster_audit as audit
        original = audit.HIGHLIGHTLY_PARTICIPANTS
        try:
            audit.HIGHLIGHTLY_PARTICIPANTS = (
                ("1", "Panama"), ("1", "Japan"),
            )
            with self.assertRaises(ValueError):
                audit.build_official_matches()
        finally:
            audit.HIGHLIGHTLY_PARTICIPANTS = original


if __name__ == "__main__":
    unittest.main()
