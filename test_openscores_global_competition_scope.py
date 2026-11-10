import unittest
from unittest.mock import Mock

from openscores_fixture_observation_sync import run_sync


class OpenScoresGlobalCompetitionScopeTests(unittest.TestCase):
    def test_global_fixture_sync_is_disabled_before_any_league_or_season_query(self):
        client_factory = Mock()
        with self.assertRaisesRegex(RuntimeError, "not a future-fixture provider"):
            run_sync(
                client_factory=client_factory,
                database_url="postgresql://db",
            )
        client_factory.assert_not_called()

    def test_global_fixture_sync_cannot_be_enabled_with_league_limit_or_window(self):
        client_factory = Mock()
        with self.assertRaisesRegex(RuntimeError, "scheduled-fixture observation sync is disabled"):
            run_sync(
                client_factory=client_factory,
                database_url="postgresql://db",
                max_leagues=8,
                now="2026-11-11T00:00:00Z",
            )
        client_factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
