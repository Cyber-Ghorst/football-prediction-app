import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from free_fixture_provider_refresh import _rotate_batch, main, refresh_free_fixture_sources


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
        self.assertEqual(collect_bzz.call_args.kwargs["params"], {
            "date_from": "2026-11-11", "date_to": "2026-11-18",
        })

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
        collect_bzz.assert_called_once_with(
            "provider-db",
            params={"date_from": "2026-11-11", "date_to": "2026-11-18"},
            max_pages=20,
        )
        bzz_cls.assert_not_called()

    def test_terms_acknowledgements_are_required_before_restricted_provider_collection(self):
        from unittest.mock import patch

        with patch("free_fixture_provider_refresh.OpenLigaDBAdapter") as openliga_cls, \
             patch("free_fixture_provider_refresh.OpenFootballAdapter") as openfootball_cls, \
             patch("free_fixture_provider_refresh.LiveScoreFootballClient") as livescore_cls, \
             patch("free_fixture_provider_refresh.collect_highlightly_observations") as collect_highlightly, \
             patch("free_fixture_provider_refresh.collect_api_ninjas_observations") as collect_ninjas:
            openliga_cls.return_value.__enter__.return_value.discover_scopes.return_value = []
            openfootball_cls.return_value.__enter__.return_value.discover_season_files.return_value = []
            livescore_cls.return_value.leagues.return_value = []
            report = refresh_free_fixture_sources(
                "provider-db",
                today=datetime(2026, 11, 11, tzinfo=timezone.utc),
                highlightly_token="highlightly-test-key",
                api_ninjas_token="api-ninjas-test-key",
            )

        collect_highlightly.assert_not_called()
        collect_ninjas.assert_not_called()
        self.assertIn("will not use its data to support betting", report["providers"]["highlightly"]["skipped"])
        self.assertIn("non-commercial-use confirmation", report["providers"]["api_ninjas"]["skipped"])


    @patch.dict("os.environ", {"PROVIDER_DATABASE_URL": "provider-db"}, clear=True)
    @patch("free_fixture_provider_refresh.refresh_free_fixture_sources")
    def test_main_defaults_openligadb_batch_to_80(self, refresh):
        from contextlib import redirect_stdout
        import io
        refresh.return_value = {"providers": {}}
        with redirect_stdout(io.StringIO()):
            main()
        self.assertEqual(refresh.call_args.kwargs["max_openligadb_scopes"], 80)

    def test_rotation_covers_different_league_batches(self):
        items = list(range(10))
        self.assertEqual(_rotate_batch(items, 3, 0), [0, 1, 2])
        self.assertEqual(_rotate_batch(items, 3, 1), [3, 4, 5])
        self.assertEqual(_rotate_batch(items, 3, 4), [2, 3, 4])

    @patch("free_fixture_provider_refresh.collect_bzzoiro_observations")
    @patch("free_fixture_provider_refresh.BzzoiroAdapter")
    @patch("free_fixture_provider_refresh.collect_livescore_observations")
    @patch("free_fixture_provider_refresh.LiveScoreFootballClient")
    @patch("free_fixture_provider_refresh.collect_openfootball_observations")
    @patch("free_fixture_provider_refresh.OpenFootballAdapter")
    @patch("free_fixture_provider_refresh.collect_openligadb_observations")
    @patch("free_fixture_provider_refresh.OpenLigaDBAdapter")
    def test_openligadb_default_batch_expands_to_80_scopes_below_rate_limit(
        self, openliga_cls, collect_openliga, openfootball_cls, collect_openfootball,
        livescore_cls, collect_livescore, bzz_cls, collect_bzz,
    ):
        openliga = openliga_cls.return_value.__enter__.return_value
        openliga.discover_scopes.return_value = [
            {"league_shortcut": f"league-{index}", "season": 2026}
            for index in range(70)
        ]
        collect_openliga.return_value = {"provider": "openligadb", "archived": True}
        openfootball_cls.return_value.__enter__.return_value.discover_season_files.return_value = []
        livescore_cls.return_value.leagues.return_value = []
        report = refresh_free_fixture_sources(
            "provider-db", today=datetime(2026, 11, 11, tzinfo=timezone.utc),
        )
        selected_scopes = collect_openliga.call_args.args[1]
        self.assertEqual(len(selected_scopes), 70)
        self.assertEqual(collect_openliga.call_args.kwargs["request_delay_seconds"], 1.05)
        self.assertTrue(report["providers"]["openligadb"]["archived"])


    def test_requires_provider_database_url(self):
        with self.assertRaisesRegex(ValueError, "PROVIDER_DATABASE_URL"):
            refresh_free_fixture_sources("")


    def test_highlightly_and_api_ninjas_use_configured_tokens(self):
        from unittest.mock import patch

        with patch("free_fixture_provider_refresh.OpenLigaDBAdapter") as openliga_cls, \
             patch("free_fixture_provider_refresh.OpenFootballAdapter") as openfootball_cls, \
             patch("free_fixture_provider_refresh.LiveScoreFootballClient") as livescore_cls, \
             patch("free_fixture_provider_refresh.collect_highlightly_observations") as collect_highlightly, \
             patch("free_fixture_provider_refresh.collect_api_ninjas_observations") as collect_ninjas:
            openliga_cls.return_value.__enter__.return_value.discover_scopes.return_value = []
            openfootball_cls.return_value.__enter__.return_value.discover_season_files.return_value = []
            livescore_cls.return_value.leagues.return_value = []
            collect_highlightly.return_value = {"provider": "highlightly", "archived": True}
            collect_ninjas.return_value = {"provider": "api_ninjas", "archived": True}

            report = refresh_free_fixture_sources(
                "provider-db",
                today=datetime(2026, 11, 11, tzinfo=timezone.utc),
                highlightly_token="highlightly-test-key",
                highlightly_use_allowed=True,
                api_ninjas_token="api-ninjas-test-key",
                api_ninjas_noncommercial_confirmed=True,
            )

        collect_highlightly.assert_called_once_with(
            "provider-db", date_from="2026-11-11", days=7,
            api_key="highlightly-test-key",
        )
        collect_ninjas.assert_called_once_with(
            "provider-db", season=2026, api_key="api-ninjas-test-key",
        )
        self.assertTrue(report["providers"]["highlightly"]["archived"])
        self.assertTrue(report["providers"]["api_ninjas"]["archived"])
        self.assertEqual(report["canonical_fixture_writes"], 0)
        self.assertEqual(report["prediction_ledger_writes"], 0)

if __name__ == "__main__":
    unittest.main()
