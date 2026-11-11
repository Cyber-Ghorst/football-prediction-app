import unittest
from datetime import datetime, timezone
from unittest.mock import patch, Mock

from free_fixture_result_sync import (
    sync_free_source_results,
    _crosswalk_matches_record,
    verify_bzzoiro_final_score,
    verify_livescore_final_score,
    verify_openligadb_final_score,
    verify_openmatchday_final_score,
    verify_openfootball_final_score,
    verify_highlightly_final_score,
    verify_api_ninjas_final_score,
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
    def test_saved_prediction_identity_must_match_all_four_provider_crosswalks(self):
        record = {
            "league_id": "sportmonks:10",
            "season_id": "sportmonks:20",
            "home_team_id": "sportmonks:30",
            "away_team_id": "sportmonks:40",
        }
        source = {
            "competition_key": "league-1",
            "season_key": "season-1",
            "home_team_key": "home-1",
            "away_team_key": "away-1",
        }
        links = {
            "league": {"league-1": "sportmonks:10"},
            "season": {"season-1": "sportmonks:20"},
            "team": {"home-1": "sportmonks:30", "away-1": "sportmonks:40"},
        }
        self.assertTrue(_crosswalk_matches_record(record, source, links))
        wrong = {
            **links,
            "team": {"home-1": "sportmonks:30", "away-1": "sportmonks:999"},
        }
        self.assertFalse(_crosswalk_matches_record(record, source, wrong))

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

    def test_openfootball_requires_explicit_kickoff_and_full_time_score(self):
        record = {
            **RECORD,
            "fixture_provider": "openfootball",
            "fixture_id": "openfootball:openfootball:dataset-42",
            "home_team": "Arsenal",
            "away_team": "Coventry",
            "kickoff_at": "2026-11-10T18:00:00Z",
            "season": "2026",
        }
        source = {
            "home_team_name": "Arsenal FC",
            "away_team_name": "Coventry City FC",
            "competition_name": "Premier League",
            "season_name": "2026-27",
        }
        observation = {
            "provider_fixture_id": "openfootball:dataset-42",
            "competition_key": "en.1",
            "competition_name": "Premier League",
            "season_key": "2026-27",
            "season_name": "2026-27",
            "home_team_name": "Arsenal FC",
            "away_team_name": "Coventry City FC",
            "kickoff_utc": "2026-11-10T18:00:00Z",
            "raw_payload": {"score": {"ht": [1, 0], "ft": [2, 1]}},
        }
        self.assertEqual(
            verify_openfootball_final_score(
                record, observation,
                provider_fixture_id="openfootball:dataset-42",
                now=NOW, source_observation=source,
            ),
            (2, 1),
        )
        naive = {**observation, "kickoff_utc": None}
        self.assertIsNone(verify_openfootball_final_score(
            record, naive,
            provider_fixture_id="openfootball:dataset-42",
            now=NOW, source_observation=source,
        ))
        cup = {
            **observation,
            "competition_key": "eng.cup",
            "competition_name": "FA Cup",
        }
        self.assertIsNone(verify_openfootball_final_score(
            record, cup,
            provider_fixture_id="openfootball:dataset-42",
            now=NOW, source_observation={**source, "competition_name": "FA Cup"},
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
    @patch("free_fixture_result_sync.OpenFootballAdapter")
    @patch("free_fixture_result_sync._ensure_promotion_tables")
    def test_openfootball_result_sync_refetches_exact_season_file(
        self, ensure_tables, adapter_cls, source
    ):
        record = {
            **RECORD,
            "fixture_provider": "openfootball",
            "fixture_id": "openfootball:openfootball:dataset-42",
            "home_team": "Arsenal",
            "away_team": "Coventry",
            "kickoff_at": "2026-11-10T18:00:00Z",
            "season": "2026",
        }
        source.return_value = {
            "source_url": "https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/en.1.json",
            "raw_payload": {
                "competition_name": "Premier League",
                "season_name": "2026-27",
                "home_team_name": "Arsenal FC",
                "away_team_name": "Coventry City FC",
            },
            "canonical_fixture_id": record["fixture_id"],
        }
        adapter = adapter_cls.return_value.__enter__.return_value
        adapter.season.return_value = [{
            "provider_fixture_id": "openfootball:dataset-42",
            "competition_key": "en.1",
            "competition_name": "Premier League",
            "season_key": "2026-27",
            "season_name": "2026-27",
            "home_team_name": "Arsenal FC",
            "away_team_name": "Coventry City FC",
            "kickoff_utc": "2026-11-10T18:00:00Z",
            "raw_payload": {"score": {"ht": [1, 0], "ft": [2, 1]}},
        }]
        records = [record]
        report, updated = sync_free_source_results(
            records, provider_database_url="provider-db", now=NOW,
        )
        self.assertEqual(report["records_updated"], 1)
        self.assertEqual(updated[0]["actual_home_goals"], 2)
        adapter.season.assert_called_once_with(
            "2026-27/en.1.json", competition="Premier League"
        )

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
    @patch("free_fixture_result_sync.load_provider_entity_links")
    @patch("free_fixture_result_sync._ensure_promotion_tables")
    def test_result_sync_blocks_when_saved_prediction_crosswalk_has_changed(
        self, ensure_tables, links, source
    ):
        record = {
            **RECORD,
            "fixture_provider": "openligadb",
            "fixture_id": "openligadb:42",
            "league_id": "sportmonks:10",
            "season_id": "sportmonks:20",
            "home_team_id": "sportmonks:30",
            "away_team_id": "sportmonks:40",
        }
        source.return_value = {
            "source_url": "https://api.openligadb.de/getmatchdata/bl1/2026",
            "raw_payload": {
                "competition_key": "bl1", "season_key": "2026",
                "home_team_key": "home-1", "away_team_key": "away-1",
            },
            "canonical_fixture_id": "openligadb:42",
        }
        links.side_effect = [
            {"bl1": "sportmonks:10"},
            {"2026": "sportmonks:20"},
            {"home-1": "sportmonks:30", "away-1": "sportmonks:999"},
        ]
        with patch("free_fixture_result_sync.OpenLigaDBAdapter") as adapter:
            report, updated = sync_free_source_results(
                [record], provider_database_url="provider-db", now=NOW,
            )
        self.assertEqual(updated, [])
        self.assertEqual(report["fixtures_without_verified_score"], 1)
        self.assertEqual(
            report["fixture_results"][0]["reason"],
            "provider_crosswalk_does_not_match_saved_prediction_identity",
        )
        adapter.assert_not_called()

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


class AdditionalProviderResultVerificationTests(unittest.TestCase):
    def setUp(self):
        self.highlightly_source = {
            "competition_key": "564",
            "competition_name": "La Liga",
            "season_key": "2026",
            "season_name": "2026-27",
            "home_team_key": "101",
            "away_team_key": "202",
            "home_team_name": "Home FC",
            "away_team_name": "Away FC",
            "kickoff_utc": "2026-11-10T18:00:00Z",
        }
        self.highlightly_match = {
            "id": 489389,
            "date": "2026-11-10T18:00:00.000Z",
            "league": {"id": 564, "name": "La Liga", "season": 2026},
            "homeTeam": {"id": 101, "name": "Home FC"},
            "awayTeam": {"id": 202, "name": "Away FC"},
            "state": {"description": "Finished", "score": {"current": "2 - 1", "penalties": None}},
        }
        self.api_ninjas_source = {
            "competition_key": "epl",
            "competition_name": "Premier League",
            "season_key": "2026",
            "season_name": "2026-27",
            "home_team_key": "soccer-home",
            "away_team_key": "soccer-away",
            "home_team_name": "Home FC",
            "away_team_name": "Away FC",
            "kickoff_utc": "2026-11-10T18:00:00Z",
        }
        self.api_ninjas_match = {
            "game_id": "epl-20261110-hom-awa",
            "league": "epl",
            "season": 2026,
            "start_time": "2026-11-10T18:00:00Z",
            "status": "final",
            "decided_in": "regulation",
            "home_team": {"team_id": "soccer-home", "name": "Home FC"},
            "away_team": {"team_id": "soccer-away", "name": "Away FC"},
            "home_score": 2,
            "away_score": 1,
        }

    def test_highlightly_accepts_only_exact_regulation_finished_match(self):
        record = {
            **RECORD, "fixture_provider": "highlightly",
            "fixture_id": "highlightly:489389",
            "competition": "La Liga", "season": "2026",
        }
        self.assertEqual(
            verify_highlightly_final_score(
                record, self.highlightly_match, provider_fixture_id="489389",
                now=NOW, source_observation=self.highlightly_source,
            ),
            (2, 1),
        )
        for state in ("Finished after extra time", "Finished after penalties", "Awarded"):
            invalid = {
                **self.highlightly_match,
                "state": {**self.highlightly_match["state"], "description": state},
            }
            self.assertIsNone(verify_highlightly_final_score(
                record, invalid, provider_fixture_id="489389",
                now=NOW, source_observation=self.highlightly_source,
            ))
        self.assertIsNone(verify_highlightly_final_score(
            record, self.highlightly_match, provider_fixture_id="wrong",
            now=NOW, source_observation=self.highlightly_source,
        ))

    def test_api_ninjas_requires_exact_id_and_regulation_result(self):
        record = {
            **RECORD, "fixture_provider": "api_ninjas",
            "fixture_id": "api_ninjas:epl-20261110-hom-awa",
            "competition": "Premier League", "season": "2026",
        }
        self.assertEqual(
            verify_api_ninjas_final_score(
                record, self.api_ninjas_match,
                provider_fixture_id="epl-20261110-hom-awa",
                now=NOW, source_observation=self.api_ninjas_source,
            ),
            (2, 1),
        )
        for decided_in in ("extra_time", "penalties", None):
            invalid = {**self.api_ninjas_match, "decided_in": decided_in}
            self.assertIsNone(verify_api_ninjas_final_score(
                record, invalid, provider_fixture_id="epl-20261110-hom-awa",
                now=NOW, source_observation=self.api_ninjas_source,
            ))
        self.assertIsNone(verify_api_ninjas_final_score(
            record, self.api_ninjas_match, provider_fixture_id="wrong",
            now=NOW, source_observation=self.api_ninjas_source,
        ))

    @patch("free_fixture_result_sync._source_metadata")
    @patch("highlightly.HighlightlyClient")
    @patch("free_fixture_result_sync._ensure_promotion_tables")
    def test_highlightly_sync_updates_only_exact_provider_fixture(
        self, ensure_tables, client_cls, source
    ):
        record = {
            **RECORD, "fixture_provider": "highlightly",
            "fixture_id": "highlightly:489389",
            "competition": "La Liga", "season": "2026",
        }
        source.return_value = {
            "source_url": "https://soccer.highlightly.net/matches/489389",
            "raw_payload": self.highlightly_source,
            "canonical_fixture_id": record["fixture_id"],
        }
        client_cls.return_value.__enter__.return_value.match.return_value = self.highlightly_match
        report, updated = sync_free_source_results(
            [record], provider_database_url="provider-db", now=NOW,
        )
        self.assertEqual(report["records_updated"], 1)
        self.assertEqual(updated[0]["actual_result_provider"], "highlightly")
        self.assertEqual(updated[0]["actual_result_verification"],
            "exact_provider_fixture_team_competition_season_and_90_minute_score")

    @patch("free_fixture_result_sync._source_metadata")
    @patch("api_ninjas.APINinjasClient")
    @patch("free_fixture_result_sync._ensure_promotion_tables")
    def test_api_ninjas_sync_updates_only_exact_regulation_fixture(
        self, ensure_tables, client_cls, source
    ):
        record = {
            **RECORD, "fixture_provider": "api_ninjas",
            "fixture_id": "api_ninjas:epl-20261110-hom-awa",
            "competition": "Premier League", "season": "2026",
        }
        source.return_value = {
            "source_url": "https://api.api-ninjas.com/v1/soccermatches",
            "raw_payload": self.api_ninjas_source,
            "canonical_fixture_id": record["fixture_id"],
        }
        client_cls.return_value.__enter__.return_value.match_details.return_value = self.api_ninjas_match
        report, updated = sync_free_source_results(
            [record], provider_database_url="provider-db", now=NOW,
        )
        self.assertEqual(report["records_updated"], 1)
        self.assertEqual(updated[0]["actual_result_provider"], "api_ninjas")
        self.assertEqual(updated[0]["actual_home_goals"], 2)


if __name__ == "__main__":
    unittest.main()
