import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import MagicMock, patch

from sportmonks_catalogue_sync import main, select_current_seasons, sync_sportmonks_catalogue


class SportmonksCatalogueSelectionTests(unittest.TestCase):
    def setUp(self):
        self.leagues = [
            {"id": 8, "name": "Premier League", "country": {"name": "England"}},
            {"id": 564, "name": "La Liga", "country": {"name": "Spain"}},
            {"id": 999, "name": "Minor League", "country": {"name": "Somewhere"}},
        ]
        self.seasons = [
            {"id": 80, "league_id": 8, "name": "2026/27", "starting_at": "2026-08-01"},
            {"id": 5640, "league_id": 564, "name": "2026/27", "starting_at": "2026-08-10"},
            {"id": 9990, "league_id": 999, "name": "2026", "starting_at": "2026-01-01"},
            {"id": 70, "league_id": 8, "name": "2025/26", "starting_at": "2025-08-01"},
            {"id": 123, "league_id": 777, "name": "2026/27", "starting_at": "2026-08-01"},
        ]

    def test_selects_only_current_year_seasons_with_known_leagues(self):
        selected = select_current_seasons(self.leagues, self.seasons, target_year=2026)
        self.assertEqual([season["id"] for _, season in selected], [80, 5640, 9990])

    def test_prioritises_major_competitions_and_applies_cap(self):
        selected = select_current_seasons(self.leagues, self.seasons, target_year=2026, max_seasons=2)
        self.assertEqual([league["name"] for league, _ in selected], ["Premier League", "La Liga"])

    def test_rejects_invalid_cap(self):
        for value in (0, 101, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                select_current_seasons(self.leagues, self.seasons, target_year=2026, max_seasons=value)


class SportmonksCatalogueSyncTests(unittest.TestCase):
    def test_imports_teams_only_and_never_fetches_fixtures(self):
        client = MagicMock()
        client.__enter__.return_value = client
        client.available_leagues.return_value = [
            {"id": 8, "name": "Premier League", "country": {"name": "England"}}
        ]
        client.available_seasons.return_value = [
            {"id": 80, "league_id": 8, "name": "2026/27", "starting_at": "2026-08-01"}
        ]
        client.teams_by_season.return_value = [{"id": 1, "name": "Arsenal"}]
        importer = MagicMock(return_value={"upserted": {"teams": 1, "fixtures": 0}, "provider_links_written": 3})
        initializer = MagicMock()
        report = sync_sportmonks_catalogue(
            "cockroach-url", target_year=2026, max_seasons=1, pause_seconds=0,
            client_factory=lambda: client, importer=importer, repository_initializer=initializer,
        )
        initializer.assert_called_once_with("cockroach-url")
        importer.assert_called_once_with(
            "cockroach-url", league=client.available_leagues.return_value[0],
            season=client.available_seasons.return_value[0],
            teams=client.teams_by_season.return_value, fixtures=[],
        )
        self.assertEqual(report["teams_upserted"], 1)
        self.assertEqual(report["fixtures_upserted"], 0)
        self.assertFalse(report["neon_prediction_ledger_modified"])
        self.assertTrue(report["success"])

    def test_empty_team_season_is_not_imported(self):
        client = MagicMock()
        client.__enter__.return_value = client
        client.available_leagues.return_value = [
            {"id": 8, "name": "Premier League", "country": {"name": "England"}}
        ]
        client.available_seasons.return_value = [
            {"id": 80, "league_id": 8, "name": "2026/27", "starting_at": "2026-08-01"}
        ]
        client.teams_by_season.return_value = []
        importer = MagicMock()
        report = sync_sportmonks_catalogue(
            "cockroach-url", target_year=2026, max_seasons=1, pause_seconds=0,
            client_factory=lambda: client, importer=importer, repository_initializer=MagicMock(),
        )
        importer.assert_not_called()
        self.assertEqual(report["seasons_imported"], 0)
        self.assertFalse(report["success"])

    def test_partial_catalogue_import_is_successful_but_not_complete(self):
        client = MagicMock()
        client.__enter__.return_value = client
        client.available_leagues.return_value = [
            {"id": 8, "name": "Premier League", "country": {"name": "England"}},
            {"id": 9, "name": "FA Cup", "country": {"name": "England"}},
        ]
        client.available_seasons.return_value = [
            {"id": 80, "league_id": 8, "name": "2026/27", "starting_at": "2026-08-01"},
            {"id": 90, "league_id": 9, "name": "2026/27", "starting_at": "2026-08-01"},
        ]
        client.teams_by_season.side_effect = [
            [{"id": 1, "name": "Arsenal"}],
            RuntimeError("pagination metadata unavailable"),
        ]
        importer = MagicMock(return_value={
            "upserted": {"teams": 1, "fixtures": 0},
            "provider_links_written": 3,
        })
        report = sync_sportmonks_catalogue(
            "cockroach-url", target_year=2026, max_seasons=2, pause_seconds=0,
            client_factory=lambda: client, importer=importer,
            repository_initializer=MagicMock(),
        )
        self.assertTrue(report["success"])
        self.assertFalse(report["complete"])
        self.assertEqual(report["seasons_imported"], 1)
        self.assertEqual(len(report["errors"]), 1)



class SportmonksCatalogueMainOutputTests(unittest.TestCase):
    def test_main_keeps_progress_logs_off_machine_readable_stdout(self):
        report = {
            "report_name": "sportmonks_canonical_catalogue_sync",
            "seasons_imported": 1,
            "success": True,
        }

        def fake_sync(*_args, **_kwargs):
            print("repository import progress")
            return report

        stdout = StringIO()
        stderr = StringIO()
        with patch.dict(os.environ, {
            "PROVIDER_DATABASE_URL": "provider-db",
            "SPORTMONKS_CATALOGUE_YEAR": "2026",
            "SPORTMONKS_CATALOGUE_MAX_SEASONS": "2",
        }):
            with patch("sportmonks_catalogue_sync.sync_sportmonks_catalogue", side_effect=fake_sync):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    exit_code = main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(stdout.getvalue()), report)
        self.assertIn("repository import progress", stderr.getvalue())




if __name__ == "__main__":
    unittest.main()
