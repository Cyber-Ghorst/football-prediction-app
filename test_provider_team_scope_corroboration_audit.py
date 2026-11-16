import unittest

from provider_team_scope_corroboration_audit import build_corroboration_report


class ProviderTeamScopeCorroborationAuditTests(unittest.TestCase):
    def _rows(
        self,
        target_season="2026/27",
        api_season="2026/27",
        *,
        include_standings=True,
        standings_competition="bundesliga",
        returned_league="bundesliga",
        standings_team_id="soccer-bayern",
        standings_name="Bayern Munich",
        season_year=2026,
        duplicate_standings=False,
        catalogue_name="Bayern Munich",
        duplicate_catalogue=False,
    ):
        target_raw = {"competition_provider_ids": ["ger.1"]}
        if target_season is not None:
            target_raw["season_label"] = target_season
        api_raw = {"domestic_league_codes": ["bundesliga"]}
        rows = [
            {
                "provider": "api_ninjas",
                "provider_entity_id": "soccer-bayern",
                "name": catalogue_name,
                "country": "DE",
                "team_type": "club",
                "gender_scope": "men",
                "raw_payload": api_raw,
            },
            {
                "provider": "livescore_football",
                "provider_entity_id": "ls-1",
                "name": "Bayern Munich",
                "raw_payload": target_raw,
            },
        ]
        if duplicate_catalogue:
            rows.append(dict(rows[0]))
        if include_standings:
            season_raw = {
                "team_evidence_method": "season_scoped_standings_row",
                "provider_team_id": standings_team_id,
                "competition_provider_id": standings_competition,
                "season_provider_id": f"{standings_competition}:2026",
                "provider_returned_league": returned_league,
                "provider_returned_season": season_year,
                "provider_returned_season_label": api_season,
            }
            season_row = {
                "provider": "api_ninjas",
                "provider_entity_id": f"{standings_competition}:{standings_team_id}",
                "name": standings_name,
                "raw_payload": season_raw,
            }
            rows.append(season_row)
            if duplicate_standings:
                rows.append(dict(season_row))
        return rows

    def _competition(self, report):
        return next(
            row for row in report["competitions"]
            if row["target_provider"] == "livescore_football"
            and row["target_competition_provider_id"] == "ger.1"
        )

    def test_missing_standings_evidence_keeps_exact_name_held(self):
        report = build_corroboration_report(self._rows(include_standings=False))
        candidate = self._competition(report)["candidates"][0]
        self.assertEqual(candidate["status"], "held_missing_explicit_season")
        self.assertFalse(candidate["season_match_verified"])
        self.assertEqual(candidate["api_ninjas_season_evidence_join_status"], "missing_standings")
        self.assertEqual(report["approved_scope_corroborations"], 0)

    def test_catalogue_season_label_alone_cannot_verify_season(self):
        rows = self._rows(include_standings=False)
        catalogue = next(row for row in rows if row["provider"] == "api_ninjas")
        catalogue["raw_payload"]["season_label"] = "2026/27"
        report = build_corroboration_report(rows)
        candidate = self._competition(report)["candidates"][0]
        self.assertEqual(candidate["status"], "held_missing_explicit_season")
        self.assertFalse(candidate["season_match_verified"])

    def test_exact_provider_id_and_competition_join_verifies_2026_27(self):
        report = build_corroboration_report(self._rows())
        candidate = self._competition(report)["candidates"][0]
        self.assertEqual(candidate["status"], "scope_corroboration_candidate")
        self.assertTrue(candidate["season_match_verified"])
        self.assertEqual(candidate["target_season_label"], "2026/27")
        self.assertEqual(candidate["api_ninjas_season_label"], "2026/27")
        self.assertEqual(candidate["api_ninjas_team_id"], "soccer-bayern")
        self.assertEqual(
            candidate["api_ninjas_season_standings_provider_entity_id"],
            "bundesliga:soccer-bayern",
        )
        self.assertEqual(report["api_ninjas_season_evidence_join"]["joined_verified"], 1)

    def test_wrong_season_year_is_held(self):
        report = build_corroboration_report(
            self._rows(api_season="2024/25", season_year=2024)
        )
        candidate = self._competition(report)["candidates"][0]
        self.assertEqual(candidate["status"], "held_api_ninjas_invalid_season_evidence")
        self.assertFalse(candidate["season_match_verified"])

    def test_wrong_season_label_is_held(self):
        report = build_corroboration_report(
            self._rows(api_season="2026/28", season_year=2026)
        )
        candidate = self._competition(report)["candidates"][0]
        self.assertEqual(candidate["status"], "held_api_ninjas_invalid_season_evidence")
        self.assertFalse(candidate["season_match_verified"])

    def test_wrong_provider_returned_competition_is_held(self):
        report = build_corroboration_report(
            self._rows(returned_league="epl")
        )
        candidate = self._competition(report)["candidates"][0]
        self.assertEqual(candidate["status"], "held_api_ninjas_mismatched_identity_or_scope")
        self.assertFalse(candidate["season_match_verified"])

    def test_wrong_provider_team_id_does_not_join(self):
        report = build_corroboration_report(
            self._rows(standings_team_id="soccer-other")
        )
        candidate = self._competition(report)["candidates"][0]
        self.assertEqual(candidate["status"], "held_missing_explicit_season")
        self.assertFalse(candidate["season_match_verified"])

    def test_wrong_competition_does_not_join(self):
        report = build_corroboration_report(
            self._rows(standings_competition="epl", returned_league="epl")
        )
        candidate = self._competition(report)["candidates"][0]
        self.assertEqual(candidate["status"], "held_missing_explicit_season")
        self.assertFalse(candidate["season_match_verified"])

    def test_team_name_mismatch_is_held(self):
        report = build_corroboration_report(
            self._rows(standings_name="Bayern FC")
        )
        candidate = self._competition(report)["candidates"][0]
        self.assertEqual(candidate["status"], "held_api_ninjas_mismatched_identity_or_scope")
        self.assertFalse(candidate["season_match_verified"])

    def test_duplicate_standings_evidence_is_ambiguous_and_held(self):
        report = build_corroboration_report(
            self._rows(duplicate_standings=True)
        )
        candidate = self._competition(report)["candidates"][0]
        self.assertEqual(candidate["status"], "held_api_ninjas_ambiguous_standings")
        self.assertFalse(candidate["season_match_verified"])
        self.assertEqual(
            report["api_ninjas_season_evidence_join"]["ambiguous_standings"],
            1,
        )

    def test_duplicate_catalogue_identity_is_held_without_join(self):
        report = build_corroboration_report(
            self._rows(duplicate_catalogue=True)
        )
        self.assertEqual(self._competition(report)["candidates"], [])
        self.assertEqual(
            report["api_ninjas_season_evidence_join"]["ambiguous_catalogue"],
            1,
        )

    def test_scope_incomplete_even_with_season_match_is_held(self):
        rows = self._rows()
        catalogue = next(row for row in rows if row["provider"] == "api_ninjas"
                         and row["provider_entity_id"] == "soccer-bayern")
        catalogue["gender_scope"] = None
        report = build_corroboration_report(rows)
        candidate = self._competition(report)["candidates"][0]
        self.assertEqual(candidate["status"], "held_api_ninjas_scope_incomplete")
        self.assertTrue(candidate["season_match_verified"])

    def test_existing_approvals_without_verified_2026_27_snapshot_are_legacy(self):
        approved = [{"provider": "highlightly", "provider_entity_id": "1",
                     "evidence_snapshot": {"season_match_verified": False}}]
        report = build_corroboration_report([], approved)
        self.assertEqual(report["approved_scope_corroborations"], 0)
        self.assertEqual(report["legacy_provisional_scope_corroborations"], 1)

    def test_verified_2026_27_approval_is_counted_as_approved(self):
        approved = [{
            "provider": "highlightly",
            "provider_entity_id": "92692",
            "corroborating_entity_id": "soccer-aj-auxerre",
            "competition_provider_id": "52695",
            "match_method": "manual_official_competition_alias_review",
            "evidence_snapshot": {
                "target_provider": "highlightly",
                "target_provider_team_id": "92692",
                "api_ninjas_team_id": "soccer-aj-auxerre",
                "competition_provider_id": "52695",
                "season_match_verified": True,
                "target_season_label": "2026/27",
                "api_ninjas_season_label": "2026/27",
            },
        }]
        report = build_corroboration_report([], approved)
        self.assertEqual(report["approved_scope_corroborations"], 1)
        self.assertEqual(report["legacy_provisional_scope_corroborations"], 0)
        self.assertEqual(report["approved_by_provider"]["highlightly"], 1)
        self.assertEqual(
            report["approved_by_match_method"]["manual_official_competition_alias_review"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
