import unittest

from highlightly_world_cup_official_roster_audit import (
    FIFA_OFFICIAL_TEAMS,
    HIGHLIGHTLY_PARTICIPANTS,
    build_official_matches,
    verify_provider_detail,
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

    def test_provider_detail_requires_id_name_and_national_type(self):
        result = verify_provider_detail(
            "10145", "Panama",
            [{"id": 10145, "name": "Panama", "type": "national"}],
        )
        self.assertEqual(result["status"], "provider_detail_confirmed")
        wrong_type = verify_provider_detail(
            "10145", "Panama",
            {"id": 10145, "name": "Panama", "type": "club"},
        )
        self.assertEqual(wrong_type["status"], "held_provider_detail_mismatch")

    def test_provider_detail_does_not_infer_country(self):
        result = verify_provider_detail(
            "10145", "Panama",
            {"id": 10145, "name": "Panama", "type": "national"},
        )
        self.assertFalse(result["country_field_available"])
        self.assertIsNone(result["country_value"])

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
