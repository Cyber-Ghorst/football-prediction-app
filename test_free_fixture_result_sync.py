import unittest
from datetime import datetime, timezone
from unittest.mock import patch, Mock

from free_fixture_result_sync import (
    sync_free_source_results,
    verify_bzzoiro_final_score,
    verify_livescore_final_score,
    verify_openligadb_final_score,
    verify_openmatchday_final_score,
)


NOW = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
RECORD = {
    "fixture_provider": "openligadb",
    "fixture_id": "openligadb:42",
    "kickoff_at": "2026-11-10T18:00:00Z",
    "competition": "Premier League",
    "season": "2026",
    "home_team": "Home FC",
    "away_team": "Away FC",
    "actual_home_goals": "",
    "actual_away_goals": "",
}


class FreeFixtureResultVerificationTests(unittest.TestCase):
    def test_openligadb_requires_exact_finished_match_and_full_time_score(self):
        match = {
            "matchID": 42,
            "matchIsFinished": True,
            "matchDateTimeUTC": "2026-11-10T18:00:00Z",
            "leagueName": "Premier League",
            "leagueSeason": 2026,
            "team1": {"teamName": "Home FC"},
            "team2": {"teamName": "Away FC"},
            "matchResults": [
                {"resultTypeID": 1, "pointsTeam1": 1, "pointsTeam2": 0},
                {"resultTypeID": 2, "resultName": "Endergebnis", "pointsTeam1": 2, "pointsTeam2": 1},
            ],
        }
        self.assertEqual(
            verify_openligadb_final_score(
                RECORD, match, provider_fixture_id="42", now=NOW,
            ),
            (2, 1),
        )

    def test_openligadb_rejects_unfinished_wrong_identity_and_ambiguous_results(self):
        match = {
            "matchID": 42, "matchIsFinished": False,
            "matchDateTimeUTC": "2026-11-10T18:00:00Z",
            "leagueName": "Premier League", "leagueSeason": 2026,
            "team1": {"teamName": "Home FC"}, "team2": {"teamName": "Away FC"},
            "matchResults": [{"resultTypeID": 2, "pointsTeam1": 2, "pointsTeam2": 1}],
        }
        self.assertIsNone(verify_openligadb_final_score(RECORD, match, provider_fixture_id="42", now=NOW))
        finished = {**match, "matchIsFinished": True}
        self.assertIsNone(verify_openligadb_final_score(
            {**RECORD, "home_team": "Other FC"}, finished, provider_fixture_id="42", now=NOW
        ))
        ambiguous = {
            **finished,
            "matchResults": [
                {"resultTypeID": 2, "pointsTeam1": 2, "pointsTeam2": 1},
                {"resultTypeID": 2, "pointsTeam1": 3, "pointsTeam2": 1},
            ],
        }
        self.assertIsNone(verify_openligadb_final_score(RECORD, ambiguous, provider_fixture_id="42", now=NOW))

    def test_livescore_requires_explicit_full_time_and_exact_event_identity(self):
        record = {**RECORD, "fixture_provider": "livescore_football", "fixture_id": "livescore_football:event-1"}
        event = {
            "id": "event-1",
            "date": "2026-11-10T18:00:00Z",
            "season": {"year": 2026},
            "status": {"type": {
                "name": "STATUS_FINAL", "completed": True, "detail": "Full Time"
            }},
            "competitions": [{
                "name": "Premier League",
                "competitors": [
                    {"homeAway": "home", "score": "2", "team": {"displayName": "Home FC"}},
                    {"homeAway": "away", "score": "1", "team": {"displayName": "Away FC"}},
                ],
            }],
        }
        self.assertEqual(
            verify_livescore_final_score(record, event, provider_fixture_id="event-1", now=NOW),
            (2, 1),
        )
        aet = {
            **event,
            "status": {"type": {
                "name": "STATUS_FINAL", "completed": True, "detail": "After Extra Time"
            }},
        }
        self.assertIsNone(verify_livescore_final_score(
            record, aet, provider_fixture_id="event-1", now=NOW
        ))

    def test_openmatchday_uses_results_csv_and_exact_deterministic_fixture_identity(self):
        record = {
            **RECORD,
            "fixture_provider": "open_matchday",
            "fixture_id": "open_matchday:dataset-42",
            "kickoff_at": "2026-11-21T12:30:00+00:00",
            "season": "2026",
        }
        observation = {
            "provider_fixture_id": "open_matchday:dataset-42",
            "competition_key": "ENG_1_premier-league",
            "competition_name": "Premier League",
            "season_key": "2627",
            "season_name": "2627",
            "home_team_name": "Home FC",
            "away_team_name": "Away FC",
            "kickoff_utc": "2026-11-21T12:30:00Z",
            "raw_payload": {"ft_home": "2", "ft_away": "1", "ft_result": "H"},
        }
        self.assertEqual(
            verify_openmatchday_final_score(
                record, observation,
                provider_fixture_id="open_matchday:dataset-42",
                now=datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc),
            ),
            (2, 1),
        )
        cup = {
            **observation,
            "competition_key": "ENG_CUP_efl-cup",
            "competition_name": "EFL Cup",
        }
        self.assertIsNone(verify_openmatchday_final_score(
            record, cup, provider_fixture_id="open_matchday:dataset-42",
            now=datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)
        ))

    @patch("free_fixture_result_sync._source_metadata")
    @patch("free_fixture_result_sync.OpenMatchdayAdapter")
    @patch("free_fixture_result_sync._ensure_promotion_tables")
    def test_openmatchday_result_sync_reads_results_csv(
        self, ensure_tables, adapter_cls, source
    ):
        record = {
            **RECORD,
            "fixture_provider": "open_matchday",
            "fixture_id": "open_matchday:open_matchday:dataset-42",
            "kickoff_at": "2026-11-21T12:30:00+00:00",
            "season": "2026",
        }
        source.return_value = {
            "source_url": "https://raw.githubusercontent.com/oladeeayo/open-matchday/master/data/ENG_1_premier-league/fixtures_2627.csv",
            "raw_payload": {
                "competition_name": "Premier League", "season_name": "2627",
            },
            "canonical_fixture_id": "open_matchday:dataset-42",
        }
        result_row = {
            "provider_fixture_id": "open_matchday:dataset-42",
            "competition_key": "ENG_1_premier-league",
            "competition_name": "Premier League",
            "season_key": "2627",
            "season_name": "2627",
            "home_team_name": "Home FC",
            "away_team_name": "Away FC",
            "kickoff_utc": "2026-11-21T12:30:00Z",
            "raw_payload": {"ft_home": 2, "ft_away": 1, "ft_result": "H"},
        }
        adapter = adapter_cls.return_value.__enter__.return_value
        adapter.season_csv.return_value = [result_row]
        records = [record]
        report, updated = sync_free_source_results(
            records, provider_database_url="provider-db",
            now=datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(report["records_updated"], 1)
        self.assertEqual(updated[0]["actual_home_goals"], 2)
        self.assertEqual(updated[0]["actual_result_provider"], "open_matchday")
        self.assertTrue(adapter.season_csv.call_args.args[0].endswith("results_2627.csv"))

    def test_bzzoiro_requires_finished_event_and_explicit_full_time_score(self):
        record = {**RECORD, "fixture_provider": "bzzoiro", "fixture_id": "bzzoiro:42"}
        event = {
            "id": 42, "status": "finished",
            "date": "2026-11-10T18:00:00Z",
            "season": {"name": "2026/27"},
            "league": {"name": "Premier League"},
            "home_team": {"name": "Home FC"},
            "away_team": {"name": "Away FC"},
            "scores": {"ft": {"home": 2, "away": 1}},
        }
        self.assertEqual(
            verify_bzzoiro_final_score(record, event, provider_fixture_id="42", now=NOW),
            (2, 1),
        )
        self.assertIsNone(verify_bzzoiro_final_score(
            record, {**event, "scores": {"ht": {"home": 1, "away": 0}}},
            provider_fixture_id="42", now=NOW,
        ))

    @patch("free_fixture_result_sync._source_metadata")
    @patch("free_fixture_result_sync.OpenLigaDBAdapter")
    @patch("free_fixture_result_sync._ensure_promotion_tables")
    def test_openligadb_result_sync_updates_only_blank_ledger_rows(
        self, ensure_tables, adapter_cls, source
    ):
        record = {**RECORD, "fixture_provider": "openligadb"}
        duplicate = {**record, "record_id": "second"}
        source.return_value = {
            "source_url": "https://api.openligadb.de/getmatchdata/bl1/2026",
            "raw_payload": {"fetched_at": "2026-11-11T00:00:00Z"},
            "canonical_fixture_id": "openligadb:42",
        }
        match = {
            "provider_fixture_id": "42",
            "raw_payload": {
                "matchID": 42, "matchIsFinished": True,
                "matchDateTimeUTC": "2026-11-10T18:00:00Z",
                "leagueName": "Premier League", "leagueSeason": 2026,
                "team1": {"teamName": "Home FC"}, "team2": {"teamName": "Away FC"},
                "matchResults": [{"resultTypeID": 2, "pointsTeam1": 2, "pointsTeam2": 1}],
            },
        }
        client = adapter_cls.return_value.__enter__.return_value
        client.matches.return_value = [match]
        records = [record, duplicate]
        report, updated = sync_free_source_results(
            records, provider_database_url="provider-db", now=NOW,
        )
        self.assertEqual(report["records_updated"], 2)
        self.assertEqual(len(updated), 2)
        self.assertEqual(record["actual_result"], "home")
        self.assertEqual(duplicate["actual_home_goals"], 2)
        self.assertEqual(record["actual_result_provider"], "openligadb")
        client.matches.assert_called_once_with("bl1", 2026)


if __name__ == "__main__":
    unittest.main()
