import unittest

from openscores_sportmonks_reconciliation import (
    find_unique_sportmonks_league,
    find_unique_sportmonks_season,
    unique_team_crosswalks,
    write_explicit_openscores_links,
)


class OpenScoresSportmonksReconciliationTests(unittest.TestCase):
    def test_league_mapping_requires_exact_name_and_country(self):
        result = find_unique_sportmonks_league(
            {"id": 2, "name": "Premier League", "country_code": "ENG"},
            [
                {"id": 8, "name": "Premier League", "country": {"name": "England"}},
                {"id": 564, "name": "La Liga", "country": {"name": "Spain"}},
            ],
        )
        self.assertEqual(result["status"], "unique_exact_name_country_match")
        self.assertEqual(result["league"]["id"], 8)

    def test_league_country_mismatch_is_rejected(self):
        result = find_unique_sportmonks_league(
            {"id": 2, "name": "Premier League", "country_code": "ENG"},
            [{"id": 999, "name": "Premier League", "country": {"name": "Scotland"}}],
        )
        self.assertEqual(result["status"], "no_exact_name_country_match")

    def test_ambiguous_exact_league_candidates_are_not_selected(self):
        result = find_unique_sportmonks_league(
            {"id": 2, "name": "Premier League", "country_code": "ENG"},
            [
                {"id": 8, "name": "Premier League", "country": {"name": "England"}},
                {"id": 9, "name": "Premier League", "country": {"name": "England"}},
            ],
        )
        self.assertEqual(result["status"], "ambiguous_exact_name_country_match")
        self.assertIsNone(result["league"])

    def test_season_mapping_requires_same_league_and_year_pair(self):
        result = find_unique_sportmonks_season(
            {"id": 2, "name": "Premier League 2025/2026"},
            [
                {"id": 28083, "league_id": 8, "name": "2026/2027"},
                {"id": 28082, "league_id": 8, "name": "2025/2026"},
                {"id": 38082, "league_id": 9, "name": "2025/2026"},
            ],
            8,
        )
        self.assertEqual(result["status"], "unique_exact_league_year_match")
        self.assertEqual(result["season"]["id"], 28082)

    def test_season_year_mismatch_is_not_cross_mapped(self):
        result = find_unique_sportmonks_season(
            {"id": 2, "name": "Premier League 2025/2026"},
            [{"id": 28083, "league_id": 8, "name": "2026/2027"}],
            8,
        )
        self.assertEqual(result["status"], "no_matching_league_year")

    def test_curated_team_alias_requires_unique_roster_target(self):
        mappings = unique_team_crosswalks(
            [
                {"provider_team_id": "os-mu", "name": "Manchester Utd"},
                {"provider_team_id": "os-ath", "name": "Ath Bilbao"},
                {"provider_team_id": "os-wolves", "name": "Wolves"},
            ],
            [
                {"id": 14, "name": "Manchester United"},
                {"id": 15, "name": "Athletic Club"},
                {"id": 16, "name": "Wolverhampton Wanderers"},
            ],
        )
        self.assertEqual(len(mappings), 3)
        self.assertEqual(
            {item["provider_entity_id"]: item["canonical_entity_id"] for item in mappings},
            {
                "os-mu": "sportmonks:14",
                "os-ath": "sportmonks:15",
                "os-wolves": "sportmonks:16",
            },
        )
        self.assertTrue(all(
            item["verification_method"] == "curated_name_alias_unique_within_matched_season_roster"
            for item in mappings
        ))

    def test_curated_team_alias_does_not_resolve_ambiguous_roster(self):
        mappings = unique_team_crosswalks(
            [{"provider_team_id": "os-mu", "name": "Manchester Utd"}],
            [
                {"id": 14, "name": "Manchester United"},
                {"id": 15, "name": "Manchester United"},
            ],
        )
        self.assertEqual(mappings, [])

    def test_team_mapping_requires_one_exact_name_in_matched_roster(self):
        mappings = unique_team_crosswalks(
            [
                {"provider_team_id": "os-1", "name": "Arsenal"},
                {"provider_team_id": "os-2", "name": "United"},
                {"provider_team_id": "os-3", "name": "Unknown FC"},
            ],
            [
                {"id": 19, "name": "Arsenal"},
                {"id": 20, "name": "United"},
                {"id": 21, "name": "United"},
            ],
        )
        self.assertEqual(len(mappings), 1)
        self.assertEqual(mappings[0]["provider_entity_id"], "os-1")
        self.assertEqual(mappings[0]["canonical_entity_id"], "sportmonks:19")


class MappingWriterCursor:
    def __init__(self, preflight_row=None, existing_link_row=None):
        self.calls = []
        self.fetchone_rows = [preflight_row, existing_link_row]
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params=None):
        self.calls.append((sql, params))
    def fetchone(self):
        return self.fetchone_rows.pop(0) if self.fetchone_rows else None


class MappingWriterConnection:
    def __init__(self, cursor):
        self.cursor_obj = cursor
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self.cursor_obj


class OpenScoresMappingVerificationTests(unittest.TestCase):
    def test_mapping_writer_creates_verification_record_with_evidence(self):
        from unittest.mock import patch
        cursor = MappingWriterCursor()
        connection = MappingWriterConnection(cursor)
        mapping = {
            "entity_type": "league",
            "provider_entity_id": "os-league-2",
            "canonical_entity_id": "sportmonks:8",
            "verification_method": "exact_competition_name_and_country",
            "evidence": {"openscores_name": "Premier League", "sportmonks_id": 8},
        }
        with patch(
            "openscores_sportmonks_reconciliation.ensure_provider_entity_link_verifications"
        ), patch(
            "openscores_sportmonks_reconciliation._connect",
            return_value=connection,
        ):
            result = write_explicit_openscores_links("postgresql://db", [mapping])
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(result["verified"], 1)
        sql = "\\n".join(call[0] for call in cursor.calls)
        self.assertIn("INSERT INTO provider_entity_links", sql)
        self.assertIn("INSERT INTO provider_entity_link_verifications", sql)
        self.assertIn("'verified'", sql)
        self.assertTrue(any(
            params and "exact_competition_name_and_country" in params
            for _, params in cursor.calls
        ))

    def test_conflicting_existing_mapping_is_not_overwritten(self):
        from unittest.mock import patch
        cursor = MappingWriterCursor(
            preflight_row=("existing-link", "sportmonks:999", "verified", "sportmonks:999")
        )
        connection = MappingWriterConnection(cursor)
        mapping = {
            "entity_type": "league",
            "provider_entity_id": "os-league-2",
            "canonical_entity_id": "sportmonks:8",
        }
        with patch(
            "openscores_sportmonks_reconciliation.ensure_provider_entity_link_verifications"
        ), patch(
            "openscores_sportmonks_reconciliation._connect",
            return_value=connection,
        ):
            result = write_explicit_openscores_links("postgresql://db", [mapping])
        self.assertEqual(result["status"], "conflict_no_writes")
        self.assertEqual(result["inserted"], 0)
        self.assertEqual(result["verified"], 0)
        self.assertEqual(len(cursor.calls), 1)


if __name__ == "__main__":
    unittest.main()
