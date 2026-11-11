import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from sportmonks import SportmonksError
from sync_prediction_results import sync_completed_results


NOW = datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)


def ledger_record(fixture_id="123", **overrides):
    record = {
        "record_id": f"record-{fixture_id}",
        "fixture_provider": "sportmonks",
        "fixture_id": str(fixture_id),
        "kickoff_at": "2026-10-01T15:00:00+00:00",
        "predicted_at": "2026-09-30T10:00:00+00:00",
        "competition": "Premier League",
        "season": "2026",
        "home_team": "Home FC",
        "away_team": "Away FC",
        "model_home_win": 50.0,
        "model_draw": 25.0,
        "model_away_win": 25.0,
        "actual_home_goals": "",
        "actual_away_goals": "",
        "actual_result": "",
    }
    record.update(overrides)
    return record


def final_fixture(fixture_id="123", state_id=5):
    return {
        "id": str(fixture_id),
        "state_id": state_id,
        "league": {"name": "Premier League"},
        "season": {"name": "2026/2027"},
        "participants": [
            {"name": "Home FC", "meta": {"location": "home"}},
            {"name": "Away FC", "meta": {"location": "away"}},
        ],
        "scores": [
            {"description": "CURRENT", "score": {"participant": "home", "goals": 2}},
            {"description": "CURRENT", "score": {"participant": "away", "goals": 1}},
        ],
    }


class FakeClient:
    def __init__(self, fixture_payload=None, error=None, api_token=None):
        self.fixture_payload = fixture_payload
        self.error = error
        self.calls = []
        self.last_metadata = {
            "http_status": 200,
            "request_seconds": 0.05,
            "rate_remaining": "1900",
        }

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def fixture(self, fixture_id, **params):
        self.calls.append((str(fixture_id), params))
        if self.error:
            raise self.error
        return self.fixture_payload


class ScheduledPredictionResultSyncTests(unittest.TestCase):
    @patch("sync_prediction_results.sync_free_source_results")
    def test_free_provider_results_persist_even_without_sportmonks_candidates(
        self, free_sync
    ):
        record = ledger_record(
            fixture_id="openligadb:42",
            fixture_provider="openligadb",
            kickoff_at="2026-11-09T18:00:00+00:00",
        )
        record["actual_home_goals"] = ""
        record["actual_away_goals"] = ""
        record["actual_result"] = ""
        saved = []
        free_sync.return_value = (
            {"status": "updated", "candidate_fixtures": 1, "records_updated": 1, "errors": []},
            [record],
        )
        with patch.dict("os.environ", {
            "SPORTMONKS_API_TOKEN": "", "SPORTMONKS_API_KEY": "",
        }):
            report, exit_code = sync_completed_results(
                database_url="postgresql://example",
                provider_database_url="provider-db",
                now=NOW,
                ledger_loader=lambda _url: [record],
                ledger_saver=lambda _url, rows: saved.extend(rows) or len(rows),
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["status"], "updated")
        self.assertEqual(report["records_updated"], 1)
        self.assertEqual(len(saved), 1)
        free_sync.assert_called_once()
        self.assertEqual(
            free_sync.call_args.kwargs["provider_database_url"], "provider-db"
        )

    def test_verified_final_score_updates_and_persists_ledger(self):
        records = [ledger_record()]
        saved = []
        client = FakeClient(final_fixture())

        report, exit_code = sync_completed_results(
            database_url="postgresql://example",
            api_token="test-token",
            now=NOW,
            ledger_loader=lambda _url: records,
            ledger_saver=lambda _url, rows: saved.extend(rows) or len(rows),
            client_factory=lambda **_kwargs: client,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["status"], "updated")
        self.assertEqual(report["fixtures_checked"], 1)
        self.assertEqual(report["records_updated"], 1)
        self.assertEqual(records[0]["actual_home_goals"], 2)
        self.assertEqual(records[0]["actual_away_goals"], 1)
        self.assertEqual(records[0]["actual_result"], "home")
        self.assertEqual(records[0]["actual_result_provider"], "sportmonks")
        self.assertEqual(
            records[0]["actual_result_verification"],
            "exact_fixture_team_competition_season_and_score",
        )
        self.assertEqual(len(saved), 1)
        self.assertEqual(report["evaluation"]["completed_pre_match_predictions"], 1)
        self.assertEqual(
            client.calls[0][1]["include"],
            "participants;scores;state;league;season",
        )

    def test_non_completed_fixture_is_not_scored_or_persisted(self):
        records = [ledger_record()]
        saved = []
        client = FakeClient(final_fixture(state_id=3))

        report, exit_code = sync_completed_results(
            database_url="postgresql://example",
            api_token="test-token",
            now=NOW,
            ledger_loader=lambda _url: records,
            ledger_saver=lambda _url, rows: saved.extend(rows) or len(rows),
            client_factory=lambda **_kwargs: client,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["status"], "no_verified_results")
        self.assertEqual(report["records_updated"], 0)
        self.assertEqual(saved, [])
        self.assertEqual(records[0]["actual_home_goals"], "")

    def test_manual_score_is_never_overwritten(self):
        records = [ledger_record(actual_home_goals=1, actual_away_goals=0)]
        saved = []
        client = FakeClient(final_fixture())

        report, exit_code = sync_completed_results(
            database_url="postgresql://example",
            api_token="test-token",
            now=NOW,
            ledger_loader=lambda _url: records,
            ledger_saver=lambda _url, rows: saved.extend(rows) or len(rows),
            client_factory=lambda **_kwargs: client,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["status"], "no_eligible_fixtures")
        self.assertEqual(client.calls, [])
        self.assertEqual(saved, [])
        self.assertEqual(records[0]["actual_home_goals"], 1)
        self.assertEqual(records[0]["actual_away_goals"], 0)

    def test_missing_database_skips_without_loading_ledger(self):
        called = []
        report, exit_code = sync_completed_results(
            database_url=None,
            now=NOW,
            ledger_loader=lambda _url: called.append(_url) or [],
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["status"], "skipped_database_not_configured")
        self.assertEqual(called, [])

    def test_missing_provider_token_does_not_make_network_requests(self):
        records = [ledger_record()]
        called = []
        report, exit_code = sync_completed_results(
            database_url="postgresql://example",
            api_token="",
            now=NOW,
            ledger_loader=lambda _url: records,
            client_factory=lambda **_kwargs: called.append(True),
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["status"], "blocked_missing_sportmonks_credential")
        self.assertEqual(called, [])

    def test_provider_error_is_reported_without_saving_a_result(self):
        records = [ledger_record()]
        saved = []
        client = FakeClient(error=SportmonksError("Sportmonks rate limit reached (HTTP 429)."))
        report, exit_code = sync_completed_results(
            database_url="postgresql://example",
            api_token="test-token",
            now=NOW,
            ledger_loader=lambda _url: records,
            ledger_saver=lambda _url, rows: saved.extend(rows) or len(rows),
            client_factory=lambda **_kwargs: client,
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["status"], "attention_required")
        self.assertEqual(len(report["errors"]), 1)
        self.assertEqual(report["records_updated"], 0)
        self.assertEqual(saved, [])

    def test_fixture_limit_defers_remaining_unique_fixtures(self):
        records = [ledger_record("123"), ledger_record("456")]
        client = FakeClient(final_fixture("123"))
        report, exit_code = sync_completed_results(
            database_url="postgresql://example",
            api_token="test-token",
            limit=1,
            now=NOW,
            ledger_loader=lambda _url: records,
            ledger_saver=lambda _url, rows: len(rows),
            client_factory=lambda **_kwargs: client,
        )
        self.assertEqual(exit_code, 0)
        self.assertTrue(report["limit_reached"])
        self.assertEqual(report["fixtures_deferred"], 1)
        self.assertEqual(report["fixtures_checked"], 1)


if __name__ == "__main__":
    unittest.main()
