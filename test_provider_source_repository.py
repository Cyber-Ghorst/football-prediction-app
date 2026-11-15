import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from provider_source_repository import (
    validate_provider_source_bundle,
    store_provider_source_bundle,
    ensure_provider_source_repository,
)


class ProviderSourceRepositoryTests(unittest.TestCase):
    def test_validates_provider_native_entities_without_assigning_canonical_ids(self):
        result = validate_provider_source_bundle(
            "Highlightly",
            entities=[
                {"entity_type": "competition", "id": 67162, "name": "Bundesliga",
                 "country": "Germany", "competition_type": "league"},
                {"entity_type": "season", "id": 2026, "name": "2026",
                 "parent_competition_provider_id": 67162},
                {"entity_type": "team", "id": 123, "name": "Bayern Munich",
                 "country": "Germany"},
            ],
        )
        self.assertEqual([row["provider"] for row in result["entities"]],
                         ["highlightly"] * 3)
        self.assertEqual(result["entities"][1]["parent_competition_provider_id"], "67162")
        self.assertNotIn("canonical_entity_id", result["entities"][0])

    def test_rejects_season_without_provider_competition_parent(self):
        with self.assertRaisesRegex(ValueError, "parent competition"):
            validate_provider_source_bundle(
                "highlightly",
                entities=[{"entity_type": "season", "id": 2026, "name": "2026"}],
            )

    def test_fixture_requires_timezone_and_distinct_ordered_teams(self):
        base = {
            "provider_fixture_id": "fixture-1",
            "competition_provider_id": "league-1",
            "season_provider_id": "season-1",
            "home_team_provider_id": "home-1",
            "away_team_provider_id": "away-1",
            "kickoff_utc": "2026-11-20T15:00:00Z",
        }
        result = validate_provider_source_bundle("livescore_football", fixtures=[base])
        self.assertEqual(result["fixtures"][0]["kickoff_utc"],
                         datetime(2026, 11, 20, 15, 0, tzinfo=timezone.utc))
        with self.assertRaisesRegex(ValueError, "include a timezone"):
            validate_provider_source_bundle(
                "livescore_football", fixtures=[{**base, "kickoff_utc": "2026-11-20T15:00:00"}],
            )
        with self.assertRaisesRegex(ValueError, "must differ"):
            validate_provider_source_bundle(
                "livescore_football",
                fixtures=[{**base, "away_team_provider_id": "home-1"}],
            )

    def test_rejects_unsupported_provider_and_invalid_source_entity_type(self):
        with self.assertRaisesRegex(ValueError, "Unsupported provider"):
            validate_provider_source_bundle("unknown_provider")
        with self.assertRaisesRegex(ValueError, "entity_type"):
            validate_provider_source_bundle(
                "highlightly",
                entities=[{"entity_type": "stadium", "id": "1", "name": "Arena"}],
            )

    def test_statistics_preserve_provider_and_source_fixture_identity(self):
        result = validate_provider_source_bundle(
            "highlightly",
            statistics=[{
                "provider_fixture_id": "match-9", "provider_statistic_id": "stat-1",
                "provider_team_id": "team-2", "statistic_type": "Ball Possession",
                "statistic_value": 57,
            }],
        )
        self.assertEqual(result["statistics"][0]["provider"], "highlightly")
        self.assertEqual(result["statistics"][0]["provider_fixture_id"], "match-9")
        self.assertEqual(result["statistics"][0]["provider_team_id"], "team-2")

    def test_store_requires_narrow_explicit_source_only_write_scope(self):
        with self.assertRaisesRegex(ValueError, "Explicit write_scope"):
            store_provider_source_bundle("postgresql://unused", "highlightly")

    @patch("provider_source_repository.ensure_provider_source_repository")
    @patch("provider_source_repository._connect")
    def test_store_writes_only_provider_source_tables(self, connect, _ensure):
        cursor = Mock()
        connection = Mock()
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=False)
        connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        connection.cursor.return_value.__exit__ = Mock(return_value=False)
        connect.return_value = connection
        result = store_provider_source_bundle(
            "postgresql://unused", "highlightly",
            entities=[{"entity_type": "team", "id": "team-1", "name": "Bayern Munich"}],
            fixtures=[{
                "provider_fixture_id": "fixture-1", "competition_provider_id": "league-1",
                "season_provider_id": "season-1", "home_team_provider_id": "team-1",
                "away_team_provider_id": "team-2", "kickoff_utc": "2026-11-20T15:00:00Z",
            }],
            write_scope="provider_source_evidence_only",
        )
        self.assertEqual(result, {"entities": 1, "fixtures": 1, "statistics": 0})
        statements = [str(call.args[0]).upper() for call in cursor.execute.call_args_list]
        self.assertTrue(all("PROVIDER_SOURCE_" in statement for statement in statements))
        self.assertFalse(any("FOOTBALL_LEAGUES" in statement for statement in statements))
        self.assertFalse(any("PROVIDER_ENTITY_LINKS" in statement for statement in statements))
        self.assertEqual(cursor.execute.call_count, 2)

    @patch("provider_source_repository._connect")
    def test_schema_is_additive_and_creates_only_source_evidence_tables(self, connect):
        cursor = Mock()
        cursor.fetchall.return_value = [
            ("provider_source_entities",), ("provider_source_fixtures",),
            ("provider_source_fixture_statistics",),
        ]
        connection = Mock()
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=False)
        connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        connection.cursor.return_value.__exit__ = Mock(return_value=False)
        connect.return_value = connection
        result = ensure_provider_source_repository("postgresql://unused")
        self.assertTrue(result["success"])
        self.assertEqual(result["canonical_entities_written"], 0)
        statements = [str(call.args[0]).upper() for call in cursor.execute.call_args_list]
        self.assertTrue(any("CREATE TABLE IF NOT EXISTS PROVIDER_SOURCE_ENTITIES" in s for s in statements))
        self.assertFalse(any("CREATE TABLE IF NOT EXISTS FOOTBALL_LEAGUES" in s for s in statements))


if __name__ == "__main__":
    unittest.main()
