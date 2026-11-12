import unittest
from unittest.mock import patch

from provider_entity_crosswalk import (
    build_entity_crosswalk_candidates,
    extract_provider_entities_from_observations,
    normalize_entity_name,
    load_provider_entity_links_by_type,
    save_explicit_provider_entity_links,
)


class FakeCursor:
    def __init__(self, *, canonical_exists=True, existing_link=None):
        self.canonical_exists = canonical_exists
        self.existing_link = existing_link
        self.last_result = None
        self.executed = []
        self.rows = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if "SELECT team_id FROM football_teams" in sql:
            self.last_result = (params[0],) if self.canonical_exists else None
        elif "SELECT canonical_entity_id FROM provider_entity_links" in sql:
            self.last_result = self.existing_link
        else:
            self.last_result = None

    def fetchone(self):
        return self.last_result

    def fetchall(self):
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class ProviderEntityCrosswalkTests(unittest.TestCase):
    def test_loads_all_provider_link_types_in_one_query(self):
        cursor = FakeCursor()
        cursor.rows = [
            ("league", "league-1", "canonical-league-1"),
            ("season", "season-1", "canonical-season-1"),
            ("team", "team-1", "canonical-team-1"),
        ]
        with patch("provider_entity_crosswalk.ensure_football_repository") as ensure, \
             patch("provider_entity_crosswalk._connect", return_value=FakeConnection(cursor)):
            links = load_provider_entity_links_by_type(
                "provider-db", provider="highlightly",
            )
        ensure.assert_called_once_with("provider-db")
        self.assertEqual(links["league"], {"league-1": "canonical-league-1"})
        self.assertEqual(links["season"], {"season-1": "canonical-season-1"})
        self.assertEqual(links["team"], {"team-1": "canonical-team-1"})
        self.assertEqual(len(cursor.executed), 1)
        self.assertEqual(cursor.executed[0][1], ("highlightly",))

    def test_openligadb_laliga_stable_id_alias_is_only_a_manual_candidate(self):
        source = [{
            "provider_competition_id": "4936",
            "competition_name": "LaLiga EA Sports",
            "country": "Spain",
        }]
        canonical = [{
            "league_id": "sportmonks:564",
            "name": "La Liga",
            "country": "Spain",
        }]
        result = build_entity_crosswalk_candidates(
            "openligadb", "league", source, canonical,
        )[0]
        self.assertEqual(result["status"], "candidate_requires_manual_approval")
        self.assertEqual(result["canonical_entity_id"], "sportmonks:564")
        self.assertEqual(result["match_method"], "curated_provider_id_alias")
        self.assertIn("explicit review is still mandatory", result["reason"])

    def test_livescore_spanish_laliga2_alias_is_only_a_manual_candidate(self):
        source = [{
            "provider_competition_id": "3921",
            "competition_name": "Spanish LALIGA 2",
            "country": "Spain",
        }]
        canonical = [{
            "league_id": "sportmonks:567",
            "name": "La Liga 2",
            "country": "Spain",
        }]
        row = build_entity_crosswalk_candidates(
            "livescore_football", "league", source, canonical,
        )[0]
        self.assertEqual(row["status"], "candidate_requires_manual_approval")
        self.assertEqual(row["canonical_entity_id"], "sportmonks:567")
        self.assertEqual(row["match_method"], "curated_provider_id_alias")
        self.assertIn("explicit review is still mandatory", row["reason"])

    def test_livescore_spanish_laliga2_alias_requires_known_id_and_exact_country(self):
        canonical = [{
            "league_id": "sportmonks:567",
            "name": "La Liga 2",
            "country": "Spain",
        }]
        unknown_id = build_entity_crosswalk_candidates(
            "livescore_football", "league",
            [{"provider_competition_id": "9999", "competition_name": "Spanish LALIGA 2", "country": "Spain"}],
            canonical,
        )[0]
        wrong_country = build_entity_crosswalk_candidates(
            "livescore_football", "league",
            [{"provider_competition_id": "3921", "competition_name": "Spanish LALIGA 2", "country": "Mexico"}],
            canonical,
        )[0]
        self.assertEqual(unknown_id["status"], "no_exact_contextual_match")
        self.assertEqual(wrong_country["status"], "no_exact_contextual_match")

    def test_openligadb_laliga_alias_requires_known_id_and_exact_country(self):
        canonical = [{
            "league_id": "sportmonks:564",
            "name": "La Liga",
            "country": "Spain",
        }]
        unknown_id = build_entity_crosswalk_candidates(
            "openligadb", "league",
            [{"provider_competition_id": "9999", "competition_name": "LaLiga EA Sports", "country": "Spain"}],
            canonical,
        )[0]
        wrong_country = build_entity_crosswalk_candidates(
            "openligadb", "league",
            [{"provider_competition_id": "4936", "competition_name": "LaLiga EA Sports", "country": "Portugal"}],
            canonical,
        )[0]
        self.assertEqual(unknown_id["status"], "no_exact_contextual_match")
        self.assertEqual(wrong_country["status"], "no_exact_contextual_match")

    def test_name_normalization_removes_accents_and_punctuation(self):
        self.assertEqual(normalize_entity_name("Atlético-Madrid"), "atletico madrid")
        self.assertEqual(normalize_entity_name("A&B FC"), "a and b fc")

    def test_team_exact_name_and_country_is_only_a_candidate(self):
        rows = build_entity_crosswalk_candidates(
            "openligadb", "team",
            [{"id": 99, "name": "Arsenal FC", "country": "England"}],
            [{"team_id": "sportmonks:1", "name": "Arsenal FC", "country": "England"}],
        )
        self.assertEqual(rows[0]["status"], "candidate_requires_manual_approval")
        self.assertEqual(rows[0]["canonical_entity_id"], "sportmonks:1")
        self.assertIn("explicit review", rows[0]["reason"])
        
    def test_openligadb_season_suffixed_league_uses_safe_country_alias(self):
        rows = build_entity_crosswalk_candidates(
            "openligadb", "league",
            [{
                "id": "4937",
                "name": "1. Fußball-Bundesliga 2026/2027",
                "country": "Deutschland",
            }],
            [{
                "league_id": "sportmonks:bundesliga",
                "name": "Bundesliga",
                "country": "Germany",
            }],
        )
        self.assertEqual(rows[0]["status"], "candidate_requires_manual_approval")
        self.assertEqual(rows[0]["canonical_entity_id"], "sportmonks:bundesliga")
        self.assertEqual(rows[0]["provider_country"], "Deutschland")

    def test_openfootball_league_requires_and_uses_country_context(self):
        rows = build_entity_crosswalk_candidates(
            "openfootball", "league",
            [{"id": "en.1", "name": "Premier League", "country": "England"}],
            [{"league_id": "sportmonks:8", "name": "Premier League", "country": "England"}],
        )
        self.assertEqual(rows[0]["status"], "candidate_requires_manual_approval")
        self.assertEqual(rows[0]["provider_country"], "England")

    def test_missing_country_never_creates_automatic_team_candidate(self):
        rows = build_entity_crosswalk_candidates(
            "openfootball", "team",
            [{"name": "Arsenal FC", "id": "team-a"}],
            [{"team_id": "sportmonks:1", "name": "Arsenal FC", "country": "England"}],
        )
        self.assertEqual(rows[0]["status"], "no_exact_contextual_match")
        self.assertIsNone(rows[0]["canonical_entity_id"])

    def test_duplicate_exact_matches_are_flagged_ambiguous(self):
        rows = build_entity_crosswalk_candidates(
            "livescore_football", "team",
            [{"id": "t-1", "name": "United FC", "country": "England"}],
            [
                {"team_id": "sportmonks:1", "name": "United FC", "country": "England"},
                {"team_id": "sportmonks:2", "name": "United FC", "country": "England"},
            ],
        )
        self.assertEqual(rows[0]["status"], "ambiguous_multiple_canonical_matches")
        self.assertIsNone(rows[0]["canonical_entity_id"])

    def test_season_requires_a_previously_verified_parent_competition(self):
        source = [{"id": "s-26", "name": "2026/27", "league_id": "league-9"}]
        canonical = [{"season_id": "sportmonks:2026", "name": "2026/27",
                      "league_id": "sportmonks:league-1"}]
        missing = build_entity_crosswalk_candidates(
            "openligadb", "season", source, canonical,
        )
        self.assertEqual(missing[0]["status"], "parent_competition_unmapped")
        mapped = build_entity_crosswalk_candidates(
            "openligadb", "season", source, canonical,
            canonical_parent_ids={"league-9": "sportmonks:league-1"},
        )
        self.assertEqual(mapped[0]["status"], "candidate_requires_manual_approval")

    def test_season_start_year_alias_is_a_manual_candidate_only(self):
        source = [{"id": "2026", "name": "2026", "league_id": "openliga:pl"}]
        canonical = [{
            "season_id": "sportmonks:28083",
            "name": "2026/2027",
            "league_id": "sportmonks:8",
        }]
        rows = build_entity_crosswalk_candidates(
            "openligadb", "season", source, canonical,
            canonical_parent_ids={"openliga:pl": "sportmonks:8"},
        )
        self.assertEqual(rows[0]["status"], "candidate_requires_manual_approval")
        self.assertEqual(rows[0]["canonical_entity_id"], "sportmonks:28083")
        self.assertEqual(rows[0]["match_method"], "exact_start_year_and_parent")
        self.assertIn("explicit review is still mandatory", rows[0]["reason"])

    def test_season_candidate_exposes_both_parent_competition_ids(self):
        source = [{
            "id": "bl1::2026",
            "name": "2026",
            "provider_competition_id": "bl1",
            "provider_competition_name": "Bundesliga",
        }]
        canonical = [{
            "season_id": "sportmonks:season-2026",
            "name": "2026/2027",
            "league_id": "sportmonks:league-bl1",
        }]
        row = build_entity_crosswalk_candidates(
            "openligadb", "season", source, canonical,
            canonical_parent_ids={"bl1": "sportmonks:league-bl1"},
        )[0]
        self.assertEqual(row["provider_parent_id"], "bl1")
        self.assertEqual(row["provider_parent_name"], "Bundesliga")
        self.assertEqual(row["canonical_parent_id"], "sportmonks:league-bl1")


    def test_season_start_year_alias_never_crosses_parent_or_year(self):
        source = [{"id": "2026", "name": "2026", "league_id": "openliga:pl"}]
        wrong_parent = [{
            "season_id": "sportmonks:28083",
            "name": "2026/2027",
            "league_id": "sportmonks:564",
        }]
        wrong_year = [{
            "season_id": "sportmonks:2025",
            "name": "2025/2026",
            "league_id": "sportmonks:8",
        }]
        parent_result = build_entity_crosswalk_candidates(
            "openligadb", "season", source, wrong_parent,
            canonical_parent_ids={"openliga:pl": "sportmonks:8"},
        )[0]
        year_result = build_entity_crosswalk_candidates(
            "openligadb", "season", source, wrong_year,
            canonical_parent_ids={"openliga:pl": "sportmonks:8"},
        )[0]
        self.assertEqual(parent_result["status"], "no_exact_contextual_match")
        self.assertEqual(year_result["status"], "no_exact_contextual_match")



    def test_extracts_unique_source_entities_from_archived_observations(self):
        observations = [
            {
                "competition_key": "bl1", "competition_name": "Bundesliga",
                "season_key": "2026", "season_name": "2026",
                "home_team_key": "openligadb:team:1", "home_team_name": "Home FC",
                "away_team_key": "openligadb:team:2", "away_team_name": "Away FC",
                "raw_payload": {
                    "leagueCountry": "Germany",
                    "team1": {"teamName": "Home FC", "teamCountry": "Germany"},
                    "team2": {"teamName": "Away FC", "teamCountry": "Germany"},
                },
            },
            {
                "competition_key": "bl1", "competition_name": "Bundesliga",
                "season_key": "2026", "season_name": "2026",
                "home_team_key": "openligadb:team:1", "home_team_name": "Home FC",
                "away_team_key": "openligadb:team:3", "away_team_name": "Third FC",
                "raw_payload": {"leagueCountry": "Germany"},
            },
        ]
        entities = extract_provider_entities_from_observations("openligadb", observations)
        self.assertEqual(len(entities["leagues"]), 1)
        self.assertEqual(len(entities["seasons"]), 1)
        self.assertEqual(entities["seasons"][0]["id"], "bl1::2026")
        self.assertEqual(len(entities["teams"]), 3)
        home = next(row for row in entities["teams"] if row["id"] == "openligadb:team:1")
        self.assertEqual(home["country"], "Germany")
        self.assertEqual(home["observation_count"], 2)

    def test_football_data_org_extracts_competition_and_team_country_context(self):
        entities = extract_provider_entities_from_observations("football_data_org", [{
            "competition_key": "PL",
            "competition_name": "Premier League",
            "season_key": "2026-08-01",
            "season_name": "2026-08-01",
            "home_team_key": "57",
            "home_team_name": "Arsenal FC",
            "away_team_key": "61",
            "away_team_name": "Chelsea FC",
            "raw_payload": {
                "competition": {"id": 2021, "name": "Premier League",
                                "area": {"id": 2072, "name": "England"}},
                "homeTeam": {"id": 57, "name": "Arsenal FC",
                             "area": {"id": 2072, "name": "England"}},
                "awayTeam": {"id": 61, "name": "Chelsea FC",
                             "area": {"id": 2072, "name": "England"}},
            },
        }])
        self.assertEqual(entities["leagues"][0]["country"], "England")
        self.assertEqual(
            {row["country"] for row in entities["teams"]},
            {"England"},
        )
        self.assertEqual(entities["leagues"][0]["id"], "PL")

    def test_numeric_provider_league_id_is_not_used_as_display_name(self):
        entities = extract_provider_entities_from_observations("bzzoiro", [{
            "competition_key": "101", "competition_name": None,
            "season_key": "2026", "season_name": "2026",
            "home_team_key": "h1", "home_team_name": "Home FC",
            "away_team_key": "a1", "away_team_name": "Away FC",
            "raw_payload": {"league": 101},
        }])
        self.assertEqual(entities["leagues"], [])

    def test_numeric_league_name_is_rejected_from_crosswalk_candidates(self):
        row = build_entity_crosswalk_candidates(
            "bzzoiro", "league",
            [{"id": "101", "name": "101"}],
            [{"league_id": "canonical:101", "name": "101", "country": "England"}],
        )[0]
        self.assertEqual(row["status"], "invalid_source_identity")
        self.assertIsNone(row["canonical_entity_id"])
        self.assertIn("Numeric provider league ID", row["reason"])

    def test_reused_season_ids_are_scoped_to_their_provider_competition(self):
        observations = [
            {
                "competition_key": "bl1", "competition_name": "Bundesliga",
                "season_key": "2026", "season_name": "2026",
            },
            {
                "competition_key": "bl2", "competition_name": "2. Bundesliga",
                "season_key": "2026", "season_name": "2026",
            },
        ]
        entities = extract_provider_entities_from_observations("openligadb", observations)
        self.assertEqual(
            {row["id"] for row in entities["seasons"]},
            {"bl1::2026", "bl2::2026"},
        )
        self.assertEqual(
            {row["provider_competition_id"] for row in entities["seasons"]},
            {"bl1", "bl2"},
        )


    def test_explicit_link_requires_reason_and_existing_canonical_entity(self):
        with self.assertRaisesRegex(ValueError, "approval_reason"):
            save_explicit_provider_entity_links(
                "provider-db",
                links=[{"provider": "openligadb", "entity_type": "team",
                        "provider_entity_id": "99", "canonical_entity_id": "sportmonks:1"}],
                approval_reason="approved",
            )
        cursor = FakeCursor(canonical_exists=False)
        with patch("provider_entity_crosswalk.ensure_football_repository"),              patch("provider_entity_crosswalk._connect", return_value=FakeConnection(cursor)):
            with self.assertRaisesRegex(ValueError, "does not exist"):
                save_explicit_provider_entity_links(
                    "provider-db",
                    links=[{"provider": "openligadb", "entity_type": "team",
                            "provider_entity_id": "99", "canonical_entity_id": "sportmonks:1"}],
                    approval_reason="Reviewed against the official club identity.",
                )

    def test_explicit_link_inserts_only_after_manual_approval(self):
        cursor = FakeCursor(canonical_exists=True)
        with patch("provider_entity_crosswalk.ensure_football_repository"),              patch("provider_entity_crosswalk._connect", return_value=FakeConnection(cursor)):
            saved = save_explicit_provider_entity_links(
                "provider-db",
                links=[{"provider": "openligadb", "entity_type": "team",
                        "provider_entity_id": "99", "canonical_entity_id": "sportmonks:1"}],
                approval_reason="Reviewed against the official club identity.",
            )
        self.assertEqual(saved, 1)
        self.assertTrue(any("INSERT INTO provider_entity_links" in sql for sql, _ in cursor.executed))
        audit = next(params for sql, params in cursor.executed if "INSERT INTO provider_entity_link_approval_audit" in sql)
        self.assertEqual(audit[-1], "Reviewed against the official club identity.")

    def test_conflicting_existing_link_is_not_overwritten(self):
        cursor = FakeCursor(canonical_exists=True, existing_link=("sportmonks:other",))
        with patch("provider_entity_crosswalk.ensure_football_repository"),              patch("provider_entity_crosswalk._connect", return_value=FakeConnection(cursor)):
            with self.assertRaisesRegex(ValueError, "Conflicting existing link"):
                save_explicit_provider_entity_links(
                    "provider-db",
                    links=[{"provider": "openligadb", "entity_type": "team",
                            "provider_entity_id": "99", "canonical_entity_id": "sportmonks:1"}],
                    approval_reason="Reviewed against the official club identity.",
                )
        self.assertFalse(any("INSERT INTO provider_entity_links" in sql for sql, _ in cursor.executed))


    def test_highlightly_and_api_ninjas_entities_retain_country_context(self):
        highlightly = extract_provider_entities_from_observations("highlightly", [{
            "competition_key": "8", "competition_name": "Premier League",
            "season_key": "2026", "season_name": "2026",
            "home_team_key": "10", "home_team_name": "Arsenal",
            "away_team_key": "20", "away_team_name": "Chelsea",
            "raw_payload": {
                "country": {"code": "GB", "name": "England"},
                "league": {"id": 8, "name": "Premier League", "season": 2026},
            },
        }])
        ninjas = extract_provider_entities_from_observations("api_ninjas", [{
            "competition_key": "epl", "competition_name": "Premier League",
            "season_key": "2026", "season_name": "2026-27",
            "home_team_key": "soccer-arsenal", "home_team_name": "Arsenal",
            "away_team_key": "soccer-chelsea", "away_team_name": "Chelsea",
            "raw_payload": {
                "country": "England",
                "league": {"id": "epl", "name": "Premier League", "country": "England"},
            },
        }])
        self.assertEqual(highlightly["leagues"][0]["country"], "England")
        self.assertEqual(highlightly["teams"][0]["country"], "England")
        self.assertEqual(ninjas["leagues"][0]["country"], "England")
        self.assertEqual(ninjas["teams"][0]["country"], "England")

if __name__ == "__main__":
    unittest.main()
