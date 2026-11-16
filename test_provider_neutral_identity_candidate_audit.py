import unittest
from unittest.mock import Mock, patch

from provider_neutral_identity_candidate_audit import (
    build_identity_candidate_report,
    audit_provider_neutral_identity_candidates,
)


class ProviderNeutralIdentityCandidateAuditTests(unittest.TestCase):
    def test_competition_key_candidate_requires_all_identity_dimensions(self):
        report = build_identity_candidate_report([
            {"provider": "sportmonks", "entity_type": "competition",
             "provider_entity_id": "8", "name": "Premier League",
             "country": "England", "competition_type": "league"},
            {"provider": "livescore_football", "entity_type": "competition",
             "provider_entity_id": "eng.1", "name": "Premier League",
             "country": "England", "competition_type": None},
        ])
        self.assertEqual(report["summary"]["competition_identity_keys_candidate"], 1)
        held = next(row for row in report["competition_candidates"]
                    if row["provider"] == "livescore_football")
        self.assertEqual(held["status"], "held_missing_identity_dimensions")
        self.assertEqual(held["missing_dimensions"], ["competition_type"])
        self.assertEqual(report["shared_competition_candidates"], [])


    def test_official_competition_references_fill_only_missing_competition_type(self):
        api_football_anchors = [
            ("39", "Premier League", "England"),
            ("140", "La Liga", "Spain"),
            ("135", "Serie A", "Italy"),
            ("78", "Bundesliga", "Germany"),
            ("61", "Ligue 1", "France"),
        ]
        rows = [
            {"provider": "api_football", "entity_type": "competition",
             "provider_entity_id": provider_id, "name": name,
             "country": country, "competition_type": "League"}
            for provider_id, name, country in api_football_anchors
        ]
        for provider_id, name, country in [
            ("33973", "Premier League", "England"),
            ("119924", "La Liga", "Spain"),
            ("115669", "Serie A", "Italy"),
            ("67162", "Bundesliga", "Germany"),
            ("52695", "Ligue 1", "France"),
        ]:
            rows.append({
                "provider": "highlightly", "entity_type": "competition",
                "provider_entity_id": provider_id, "name": name,
                "country": country, "competition_type": None,
            })
        rows.extend([
            {"provider": "livescore_football", "entity_type": "competition",
             "provider_entity_id": "ger.1", "name": "German Bundesliga",
             "country": "Germany", "competition_type": None},
            {"provider": "livescore_football", "entity_type": "competition",
             "provider_entity_id": "fra.1", "name": "French Ligue 1",
             "country": "France", "competition_type": None},
        ])
        for provider_id, name in [
            ("epl", "Premier League"),
            ("laliga", "La Liga"),
            ("seriea", "Serie A"),
            ("bundesliga", "Bundesliga"),
            ("ligue1", "Ligue 1"),
        ]:
            rows.append({
                "provider": "api_ninjas", "entity_type": "competition",
                "provider_entity_id": provider_id, "name": name,
                "country": None, "competition_type": None,
            })
        report = build_identity_candidate_report(rows)

        official_rows = [
            row for row in report["competition_candidates"]
            if row["provider"] in {"highlightly", "livescore_football", "api_ninjas"}
        ]
        self.assertEqual(len(official_rows), 12)
        self.assertTrue(all(row["identity_key_candidate"] for row in official_rows))
        self.assertTrue(all(row["missing_dimensions"] == [] for row in official_rows))
        ninjas = {row["provider_entity_id"]: row for row in official_rows
                  if row["provider"] == "api_ninjas"}
        self.assertEqual(set(ninjas), {"epl", "laliga", "seriea", "bundesliga", "ligue1"})
        self.assertTrue(all(row["source_missing_dimensions"] == ["country", "competition_type"]
                            for row in ninjas.values()))
        self.assertTrue(all(set(row["corroborated_dimensions"]) == {"country", "competition_type"}
                            for row in ninjas.values()))
        self.assertEqual(ninjas["epl"]["country"], "England")
        self.assertEqual(ninjas["laliga"]["country"], "Spain")
        self.assertEqual(ninjas["seriea"]["country"], "Italy")
        self.assertEqual(ninjas["ligue1"]["country"], "France")
        self.assertEqual(ninjas["bundesliga"]["country"], "Germany")
        self.assertTrue(all(row["corroborated_dimensions"] and
                            row["scope_evidence_source"] == "official_competition_reference" and
                            row["official_reference_urls"]
                            for row in official_rows))
        livescore = {row["provider_entity_id"]: row for row in official_rows
                     if row["provider"] == "livescore_football"}
        self.assertEqual(livescore["ger.1"]["identity_name_candidate"], "Bundesliga")
        self.assertEqual(livescore["fra.1"]["identity_name_candidate"], "Ligue 1")
        self.assertEqual(report["summary"]["competitions_with_official_type_corroboration"], 12)
        self.assertEqual(len(report["shared_competition_candidates"]), 5)
        for group in report["shared_competition_candidates"]:
            self.assertIn("api_ninjas", {source["provider"] for source in group["source_entities"]})
        self.assertEqual(report["canonical_ids_assigned"], 0)
        self.assertEqual(report["provider_links_created"], 0)

    def test_unknown_api_ninjas_competition_slug_remains_held(self):
        report = build_identity_candidate_report([{
            "provider": "api_ninjas", "entity_type": "competition",
            "provider_entity_id": "unknown", "name": "Unknown Competition",
            "country": None, "competition_type": None,
        }])
        candidate = report["competition_candidates"][0]
        self.assertEqual(candidate["status"], "held_missing_identity_dimensions")
        self.assertEqual(candidate["missing_dimensions"], ["country", "competition_type"])
        self.assertIsNone(candidate["identity_key_candidate"])

    def test_exact_cross_provider_competition_identity_is_candidate_not_approved_link(self):
        report = build_identity_candidate_report([
            {"provider": "sportmonks", "entity_type": "competition",
             "provider_entity_id": "8", "name": "Premier League",
             "country": "England", "competition_type": "league"},
            {"provider": "highlightly", "entity_type": "competition",
             "provider_entity_id": "pl-1", "name": "Premier League",
             "country": "England", "competition_type": "league"},
        ])
        self.assertEqual(len(report["shared_competition_candidates"]), 1)
        self.assertEqual(
            {row["status"] for row in report["competition_candidates"]},
            {"shared_identity_candidate_requires_manual_review"},
        )
        self.assertEqual(report["canonical_ids_assigned"], 0)
        self.assertEqual(report["provider_links_created"], 0)

    def test_seasons_and_teams_are_held_without_parent_and_team_scope_evidence(self):
        report = build_identity_candidate_report([
            {"provider": "sportmonks", "entity_type": "season",
             "provider_entity_id": "28083", "name": "2026/27",
             "season_label": "2026/27", "parent_competition_provider_id": "8"},
            {"provider": "livescore_football", "entity_type": "team",
             "provider_entity_id": "123", "name": "Bayern Munich",
             "country": None, "team_type": None, "gender_scope": None,
             "age_group": None, "squad_scope": None},
        ])
        self.assertEqual(
            report["season_candidates"][0]["status"],
            "held_until_parent_competition_is_approved",
        )
        self.assertEqual(
            report["team_candidates"][0]["missing_dimensions"],
            ["country", "team_type", "gender_scope", "age_group", "squad_scope"],
        )
        self.assertEqual(report["summary"]["teams_held_for_scope_evidence"], 1)

    def test_date_objects_are_serialized_to_iso_strings(self):
        from datetime import date
        report = build_identity_candidate_report([
            {"provider": "api_football", "entity_type": "season",
             "provider_entity_id": "39:2024", "name": "2024",
             "season_label": "2024", "parent_competition_provider_id": "39",
             "start_date": date(2024, 8, 16), "end_date": date(2025, 5, 25)},
        ], {("api_football", "39"): "sportmonks:8"})
        season = report["season_candidates"][0]
        self.assertEqual(season["start_date"], "2024-08-16")
        self.assertEqual(season["end_date"], "2025-05-25")

    def test_season_date_range_is_reported_without_rewriting_provider_label(self):
        report = build_identity_candidate_report([
            {"provider": "api_football", "entity_type": "season",
             "provider_entity_id": "39:2024", "name": "2024",
             "season_label": "2024", "parent_competition_provider_id": "39",
             "start_date": "2024-08-16", "end_date": "2025-05-25"},
        ], {("api_football", "39"): "sportmonks:8"})
        season = report["season_candidates"][0]
        self.assertEqual(season["season_label"], "2024")
        self.assertEqual(season["start_date"], "2024-08-16")
        self.assertEqual(season["end_date"], "2025-05-25")
        self.assertEqual(season["season_date_range_status"], "complete")
        self.assertEqual(report["summary"]["seasons_with_complete_date_range"], 1)

    def test_season_key_candidate_is_released_only_for_approved_parent(self):
        rows = [
            {"provider": "api_football", "entity_type": "season",
             "provider_entity_id": "39:2024", "name": "2024",
             "season_label": "2024", "parent_competition_provider_id": "39"},
            {"provider": "highlightly", "entity_type": "season",
             "provider_entity_id": "67162:2026", "name": "2026",
             "season_label": "2026", "parent_competition_provider_id": "67162"},
        ]
        report = build_identity_candidate_report(
            rows, {("api_football", "39"): "sportmonks:8"}
        )
        api_season = next(row for row in report["season_candidates"]
                          if row["provider"] == "api_football")
        highlightly_season = next(row for row in report["season_candidates"]
                                  if row["provider"] == "highlightly")
        self.assertEqual(
            api_season["status"],
            "season_key_candidate_parent_approved_review_required",
        )
        self.assertTrue(api_season["identity_key_candidate"].startswith("season_v1_"))
        self.assertEqual(
            highlightly_season["status"],
            "held_until_parent_competition_is_approved",
        )
        self.assertEqual(
            report["summary"]["seasons_with_approved_parent_candidate"], 1
        )
        self.assertEqual(report["summary"]["seasons_held_for_parent_approval"], 1)

    def test_same_provider_duplicate_is_not_misreported_as_cross_provider_match(self):
        report = build_identity_candidate_report([
            {"provider": "sportmonks", "entity_type": "competition",
             "provider_entity_id": "8", "name": "Premier League",
             "country": "England", "competition_type": "league"},
            {"provider": "sportmonks", "entity_type": "competition",
             "provider_entity_id": "80", "name": "Premier League",
             "country": "England", "competition_type": "league"},
        ])
        self.assertEqual(report["shared_competition_candidates"], [])
        self.assertEqual(len(report["duplicate_competition_candidates"]), 1)


    def test_approved_scope_corroborations_fill_only_missing_dimensions(self):
        rows = [
            {"provider": "highlightly", "entity_type": "team",
             "provider_entity_id": "h-1", "name": "Lyon",
             "country": None, "team_type": None, "gender_scope": None,
             "age_group": None, "squad_scope": None},
            {"provider": "api_football", "entity_type": "team",
             "provider_entity_id": "a-1", "name": "Arsenal",
             "country": "England", "team_type": "club", "gender_scope": None,
             "age_group": None, "squad_scope": None},
        ]
        corroborations = {
            ("highlightly", "h-1"): {
                "country": "France", "team_type": "club", "gender_scope": "male",
            },
            ("api_football", "a-1"): {
                "country": "United Kingdom", "team_type": "club", "gender_scope": "male",
            },
        }
        report = build_identity_candidate_report(
            rows, approved_team_scope_corroborations=corroborations
        )
        highlightly = next(row for row in report["team_candidates"]
                           if row["provider"] == "highlightly")
        api_football = next(row for row in report["team_candidates"]
                            if row["provider"] == "api_football")

        self.assertEqual(
            highlightly["corroborated_dimensions"],
            ["country", "gender_scope", "team_type"],
        )
        self.assertEqual(
            highlightly["missing_dimensions"], ["age_group", "squad_scope"]
        )
        self.assertEqual(
            highlightly["source_missing_dimensions"],
            ["country", "team_type", "gender_scope", "age_group", "squad_scope"],
        )
        self.assertEqual(api_football["corroborated_dimensions"], ["gender_scope"])
        self.assertEqual(api_football["missing_dimensions"], ["age_group", "squad_scope"])
        self.assertEqual(api_football["source_missing_dimensions"],
                         ["gender_scope", "age_group", "squad_scope"])
        self.assertEqual(highlightly["status"], "held_missing_team_scope")
        self.assertIsNone(highlightly["identity_key_candidate"])
        self.assertEqual(report["summary"]["teams_with_approved_scope_corroboration"], 2)
        self.assertEqual(report["summary"]["teams_held_for_scope_evidence"], 2)


    @patch("provider_neutral_identity_candidate_audit._connect")
    def test_legacy_provisional_scope_rows_are_ignored(self, connect):
        source_row = (
            "highlightly", "team", "h-1", "Lyon", None,
            None, None, None, None, None, None, None, None, None,
        )
        legacy_snapshot = {
            "season_match_verified": False,
            "target_season_label": "2026/27",
            "api_ninjas_season_label": None,
        }
        verified_snapshot = {
            "season_match_verified": True,
            "target_season_label": "2026/27",
            "api_ninjas_season_label": "2026/27",
        }
        corroborations = [
            ("highlightly", "h-1", "Wrongland", "club", "male", legacy_snapshot),
            ("highlightly", "h-1", "France", "club", "male", verified_snapshot),
        ]
        cursor = Mock()
        cursor.fetchall.side_effect = [[source_row], [], corroborations]
        connection = Mock()
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=False)
        connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        connection.cursor.return_value.__exit__ = Mock(return_value=False)
        connect.return_value = connection

        report = audit_provider_neutral_identity_candidates("postgresql://readonly")
        team = report["team_candidates"][0]
        self.assertEqual(report["approved_team_scope_corroborations_read"], 1)
        self.assertEqual(report["legacy_provisional_scope_corroborations_ignored"], 1)
        self.assertEqual(team["corroborated_dimensions"], ["country", "gender_scope", "team_type"])
        self.assertEqual(team["missing_dimensions"], ["age_group", "squad_scope"])
        self.assertEqual(team["scope_evidence_source"], "provider_team_scope_corroborations")

    @patch("provider_neutral_identity_candidate_audit._connect")
    def test_database_audit_is_select_only(self, connect):
        cursor = Mock()
        cursor.fetchall.side_effect = [
            [("sportmonks", "competition", "8", "Premier League", "England",
              "league", None, None, None, None, None, None, None, None)],
            [("sportmonks", "8", "sportmonks:8")],
            [],
        ]
        connection = Mock()
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=False)
        connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        connection.cursor.return_value.__exit__ = Mock(return_value=False)
        connect.return_value = connection
        report = audit_provider_neutral_identity_candidates("postgresql://readonly")
        self.assertTrue(report["database_read_only"])
        self.assertFalse(report["database_writes"])
        self.assertEqual(report["approved_team_scope_corroborations_read"], 0)
        statements = [str(call.args[0]).strip().upper()
                      for call in cursor.execute.call_args_list]
        self.assertTrue(statements[0].startswith("SET TRANSACTION READ ONLY"))
        self.assertTrue(all(statement.startswith("SELECT") for statement in statements[1:]))


if __name__ == "__main__":
    unittest.main()
