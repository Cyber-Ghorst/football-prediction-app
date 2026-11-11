import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from free_fixture_provider_refresh import _rotate_batch, refresh_free_fixture_sources


class FreeFixtureProviderRefreshTests(unittest.TestCase):
    @patch("free_fixture_provider_refresh.collect_bzzoiro_observations")
    @patch("free_fixture_provider_refresh.BzzoiroAdapter")
    @patch("free_fixture_provider_refresh.collect_livescore_observations")
    @patch("free_fixture_provider_refresh.LiveScoreFootballClient")
    @patch("free_fixture_provider_refresh.collect_openfootball_observations")
    @patch("free_fixture_provider_refresh.OpenFootballAdapter")
    @patch("free_fixture_provider_refresh.collect_openligadb_observations")
    @patch("free_fixture_provider_refresh.OpenLigaDBAdapter")
    def test_discovers_and_archives_sources_without_promoting_openmatchday(
        self, openliga_cls, collect_openliga, openfootball_cls, collect_openfootball,
        livescore_cls, collect_livescore, bzz_cls, collect_bzz, 
    ):
        openliga = openliga_cls.return_value.__enter__.return_value
        openliga.discover_scopes.return_value = [
            {"league_shortcut": "bl1", "season": 2026}
        ]
        collect_openliga.return_value = {"provider": "openligadb", "archived": True}
        openfootball = openfootball_cls.return_value.__enter__.return_value
        openfootball.discover_season_files.return_value = [
            {"season_file": "2026-27/en.1.json", "competition": "Premier League"}
        ]
        collect_openfootball.return_value = {"provider": "openfootball", "archived": True}
        livescore = livescore_cls.return_value
        livescore.leagues.return_value = [{"slug": "eng.1"}]
        collect_livescore.return_value = {"provider": "livescore_football", "archived": True}
        bzz = bzz_cls.return_value.__enter__.return_value
        collect_bzz.return_value = {"provider": "bzzoiro", "archived": True}

        report = refresh_free_fixture_sources(
            "provider-db",
            today=datetime(2026, 11, 11, tzinfo=timezone.utc),
            bzzoiro_token="secret-token",
        )
        self.assertTrue(report["providers"]["openligadb"]["archived"])
        self.assertTrue(report["providers"]["openfootball"]["archived"])
        self.assertTrue(report["providers"]["livescore_football"]["archived"])
        self.assertTrue(report["providers"]["bzzoiro"]["archived"])
        self.assertIn("non-commercial-only", report["providers"]["open_matchday"]["skipped"])
        self.assertIn("not configured", report["providers"]["highlightly"]["skipped"])
        self.assertIn("not configured", report["providers"]["api_ninjas"]["skipped"])
        self.assertEqual(report["canonical_fixture_writes"], 0)
        self.assertEqual(report["prediction_ledger_writes"], 0)
        collect_livescore.assert_called_once()
        self.assertEqual(collect_livescore.call_args.kwargs["date_from"], "2026-11-11")
        self.assertEqual(collect_livescore.call_args.kwargs["date_to"], "2026-11-18")
        self.assertEqual(collect_bzz.call_args.kwargs["client"], bzz)

    @patch("free_fixture_provider_refresh.collect_bzzoiro_observations")
    @patch("free_fixture_provider_refresh.BzzoiroAdapter")
    @patch("free_fixture_provider_refresh.collect_livescore_observations")
    @patch("free_fixture_provider_refresh.LiveScoreFootballClient")
    @patch("free_fixture_provider_refresh.collect_openfootball_observations")
    @patch("free_fixture_provider_refresh.OpenFootballAdapter")
    @patch("free_fixture_provider_refresh.collect_openligadb_observations")
    @patch("free_fixture_provider_refresh.OpenLigaDBAdapter")
    def test_missing_bzzoiro_token_does_not_block_other_sources(
        self, openliga_cls, collect_openliga, openfootball_cls, collect_openfootball,
        livescore_cls, collect_livescore, bzz_cls, collect_bzz,
    ):
        openliga = openliga_cls.return_value.__enter__.return_value
        openliga.discover_scopes.return_value = []
        openfootball = openfootball_cls.return_value.__enter__.return_value
        openfootball.discover_season_files.return_value = []
        livescore_cls.return_value.leagues.return_value = []
        collect_bzz.return_value = {
            "provider": "bzzoiro", "archived": False,
            "errors": [{"scope": "upcoming", "error": "BZZOIRO_API_TOKEN is required"}],
        }
        report = refresh_free_fixture_sources(
            "provider-db", today=datetime(2026, 11, 11, tzinfo=timezone.utc),
        )
        self.assertFalse(report["providers"]["bzzoiro"]["archived"])
        collect_bzz.assert_called_once_with("provider-db", max_pages=20)
        bzz_cls.assert_not_called()

    def test_rotation_covers_different_league_batches(self):
        items = list(range(10))
        self.assertEqual(_rotate_batch(items, 3, 0), [0, 1, 2])
        self.assertEqual(_rotate_batch(items, 3, 1), [3, 4, 5])
        self.assertEqual(_rotate_batch(items, 3, 4), [2, 3, 4])

    def test_requires_provider_database_url(self):
        with self.assertRaisesRegex(ValueError, "PROVIDER_DATABASE_URL"):
            refresh_free_fixture_sources("")


if __name__ == "__main__":
    unittest.main()
