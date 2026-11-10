import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from openscores_fixture_observation_sync import run_sync


class FakeClient:
    def __init__(self, fixtures=None, total_pages=1):
        self.calls = []
        self.total_pages = total_pages
        self.fixtures = fixtures if fixtures is not None else [{
            "id": 77, "league_id": 1, "season_id": 2026,
            "scheduled_kickoff_at": "2026-11-12T19:00:00Z",
            "home_team": {"id": 10, "name": "Home"},
            "away_team": {"id": 20, "name": "Away"},
            "status": "scheduled",
        }]

    def __enter__(self): return self
    def __exit__(self, *args): return False

    def list_leagues(self):
        return {"data": [{"id": 1, "name": "Test League"}]}

    def list_seasons(self, league_id):
        return {"data": {"seasons": [{"id": 2026, "league_id": 1}]}}

    @staticmethod
    def _league_collection(data):
        return data, "$"

    def list_fixtures(self, **filters):
        self.calls.append(("fixtures", filters))
        return {
            "retrieved_at_utc": "2026-11-10T17:00:00Z",
            "data": {
                "items": self.fixtures,
                "pagination": {
                    "page": filters["page"],
                    "total_pages": self.total_pages,
                },
            },
        }


class OpenScoresObservationSyncTests(unittest.TestCase):
    def _run(self, client):
        with patch(
            "openscores_fixture_observation_sync.upsert_openscores_observations",
            side_effect=lambda _db, rows: {
                "observations_upserted": len(rows), "canonical_fixtures_written": 0
            },
        ) as save, patch(
            "openscores_fixture_observation_sync.mark_outside_upcoming_window_observations",
            return_value=300,
        ) as retire, patch(
            "openscores_fixture_observation_sync.reconcile_openscores_observations",
            return_value={"observations_checked": 1, "matched": 0, "pending_entity_mapping": 1},
        ) as reconcile:
            report = run_sync(
                client_factory=lambda: client,
                database_url="postgresql://db",
                now=datetime(2026, 11, 10, 18, 0, tzinfo=timezone.utc),
            )
        return report, save, retire, reconcile

    def test_live_flow_uses_global_scheduled_status_and_exact_seven_day_filters(self):
        client = FakeClient()
        report, save, retire, reconcile = self._run(client)
        filters = next(call[1] for call in client.calls if call[0] == "fixtures")
        self.assertEqual(filters, {
            "season_id": "2026",
            "status": "scheduled",
            "date_from": "2026-11-10T18:00:00Z",
            "date_to": "2026-11-17T18:00:00Z",
            "page": 1,
            "page_size": 200,
        })
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(report["fixtures_accepted_for_window"], 1)
        self.assertEqual(report["observations_upserted"], 1)
        self.assertEqual(report["historical_observations_marked_out_of_window"], 300)
        self.assertEqual(report["canonical_fixtures_written"], 0)
        self.assertTrue(report["read_only_for_canonical_fixtures"])
        self.assertFalse(report["prediction_ledger_touched"])
        save.assert_called_once()
        retire.assert_called_once()
        reconcile.assert_called_once_with("postgresql://db")

    def test_outside_window_fixture_is_never_staged(self):
        client = FakeClient(fixtures=[{
            "id": 78, "league_id": 1, "season_id": 2026,
            "scheduled_kickoff_at": "2026-11-20T19:00:00Z",
            "home_team": {"id": 10, "name": "Home"},
            "away_team": {"id": 20, "name": "Away"},
            "status": "scheduled",
        }])
        report, save, _, _ = self._run(client)
        self.assertEqual(report["fixtures_outside_window"], 1)
        self.assertEqual(report["fixtures_accepted_for_window"], 0)
        save.assert_called_once_with("postgresql://db", [])

    def test_non_scheduled_fixture_is_never_staged(self):
        client = FakeClient(fixtures=[{
            "id": 79, "league_id": 1, "season_id": 2026,
            "scheduled_kickoff_at": "2026-11-12T19:00:00Z",
            "home_team": {"id": 10, "name": "Home"},
            "away_team": {"id": 20, "name": "Away"},
            "status": "finished",
        }])
        report, save, _, _ = self._run(client)
        self.assertEqual(report["fixtures_non_scheduled"], 1)
        self.assertEqual(report["fixtures_accepted_for_window"], 0)
        save.assert_called_once_with("postgresql://db", [])

    def test_reports_truncated_provider_pagination_after_safe_page_cap(self):
        client = FakeClient(total_pages=12)
        report, _, _, _ = self._run(client)
        self.assertEqual(len(client.calls), 10)
        self.assertTrue(report["pagination_truncated"])
        self.assertEqual(report["status"], "partial")

    def test_requires_database_before_provider_calls(self):
        client = FakeClient()
        with self.assertRaises(ValueError):
            run_sync(client_factory=lambda: client, database_url="")
        self.assertEqual(client.calls, [])


if __name__ == "__main__":
    unittest.main()
