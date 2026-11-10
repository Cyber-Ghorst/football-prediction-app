import unittest
from unittest.mock import Mock

from openscores_fixture_observation_sync import run_sync


class OpenScoresFutureFixtureSyncDisabledTests(unittest.TestCase):
    def test_legacy_sync_fails_closed_before_provider_or_database_access(self):
        client_factory = Mock()
        with self.assertRaisesRegex(RuntimeError, "not a future-fixture provider"):
            run_sync(
                client_factory=client_factory,
                database_url="postgresql://db",
            )
        client_factory.assert_not_called()

    def test_legacy_sync_cannot_be_reenabled_by_passing_a_window(self):
        client_factory = Mock()
        with self.assertRaisesRegex(RuntimeError, "scheduled-fixture observation sync is disabled"):
            run_sync(
                client_factory=client_factory,
                database_url="postgresql://db",
                max_leagues=1,
            )
        client_factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
