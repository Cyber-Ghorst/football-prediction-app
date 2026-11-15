import unittest
from datetime import datetime, timezone

from openligadb_unscoped_scope_probe import (
    build_probe_report,
    select_league_metadata,
    summarize_matches,
)


class OpenLigaDBScopeProbeTests(unittest.TestCase):
    def test_metadata_selection_requires_exact_league_and_season(self):
        available = [
            {"leagueId": 4937, "leagueName": "Bundesliga", "leagueShortcut": "bl1", "leagueSeason": 2026},
            {"leagueId": 4937, "leagueName": "Bundesliga", "leagueShortcut": "bl1", "leagueSeason": 2025},
        ]
        row, status = select_league_metadata(available, 4937, 2026)
        self.assertEqual(status, "metadata_found")
        self.assertEqual(row["league_shortcut"], "bl1")
        missing, missing_status = select_league_metadata(available, 4937, 2024)
        self.assertIsNone(missing)
        self.assertEqual(missing_status, "not_found_in_available_leagues_for_season")

    def test_duplicate_metadata_is_ambiguous(self):
        available = [
            {"leagueId": 4937, "leagueShortcut": "bl1", "leagueSeason": 2026},
            {"leagueId": 4937, "leagueShortcut": "bl1-alt", "leagueSeason": 2026},
        ]
        row, status = select_league_metadata(available, 4937, 2026)
        self.assertIsNone(row)
        self.assertEqual(status, "ambiguous_available_league_metadata")

    def test_match_summary_preserves_team_pair_and_timezone_evidence(self):
        matches = [{
            "matchID": 1,
            "leagueId": 4937,
            "leagueSeason": 2026,
            "matchDateTime": "2026-11-20T20:30:00",
            "matchDateTimeUTC": "2026-11-20T19:30:00Z",
            "timeZoneID": "W. Europe Standard Time",
            "team1": {"teamId": 1, "teamName": "FC Bayern München"},
            "team2": {"teamId": 2, "teamName": "1. FC Köln"},
            "matchIsFinished": False,
            "group": {"groupName": "Matchday 12", "groupOrderID": 12},
        }]
        summary = summarize_matches(matches)
        self.assertEqual(summary["match_count"], 1)
        self.assertEqual(summary["unique_team_count"], 2)
        self.assertEqual(summary["utc_kickoff_count"], 1)
        self.assertEqual(summary["team_names"], ["1. FC Köln", "FC Bayern München"])
        self.assertEqual(summary["sample_fixtures"][0]["kickoff_utc"], "2026-11-20T19:30:00Z")
        self.assertEqual(len(summary["fixture_identity_hashes"]), 1)


    def test_probe_reports_exact_fixture_overlaps_without_promoting_identities(self):
        candidates = {"records": [
            {"league_id": 1, "source_name": "Official league", "season": 2026,
             "scope_class": "domestic_league_candidate", "candidate_country": "X"},
            {"league_id": 2, "source_name": "Alias collection", "season": 2026,
             "scope_class": "possible_alias", "candidate_country": "X"},
        ]}
        fixture = {"matchID": 10, "leagueId": 1, "leagueSeason": 2026,
                   "team1": {"teamName": "FC Example"}, "team2": {"teamName": "United"},
                   "matchDateTimeUTC": "2026-11-20T19:30:00Z"}
        def fake_get(url):
            if url.endswith("/getavailableleagues/2026"):
                return ([
                    {"leagueId": 1, "leagueName": "Official league", "leagueShortcut": "one",
                     "leagueSeason": 2026, "sport": {"sportName": "Football"}},
                    {"leagueId": 2, "leagueName": "Alias collection", "leagueShortcut": "two",
                     "leagueSeason": 2026, "sport": {"sportName": "Football"}},
                ], "available-hash")
            if "/one/" in url:
                return ([fixture], "one-hash")
            alias_fixture = {**fixture, "matchID": 99, "leagueId": 2,
                             "team1": {"teamName": " fc example "}}
            return ([alias_fixture], "two-hash")
        report = build_probe_report(
            candidates, get_json=fake_get, sleep=lambda _: None,
            generated_at=datetime(2026, 11, 15, tzinfo=timezone.utc),
        )
        comparison = report["fixture_identity_comparison"]
        self.assertEqual(comparison["pairs_with_exact_fixture_overlap"], 1)
        self.assertEqual(comparison["overlap_pairs"][0]["exact_fixture_overlap_count"], 1)
        self.assertEqual(report["results"][0]["api_metadata"]["sport"], "Football")
        self.assertFalse(report["safeguards"]["provider_link_writes"])

    def test_probe_is_read_only_and_records_api_hashes(self):
        candidates = {"records": [
            {"league_id": 4937, "source_name": "Bundesliga", "season": 2026,
             "scope_class": "domestic_league_candidate", "candidate_country": "Germany",
             "prior_observation_count": 918}
        ]}
        def fake_get(url):
            if url.endswith("/getavailableleagues/2026"):
                return ([{"leagueId": 4937, "leagueName": "Bundesliga",
                          "leagueShortcut": "bl1", "leagueSeason": 2026}], "available-hash")
            return ([{"matchID": 1, "leagueId": 4937, "leagueSeason": 2026,
                      "team1": {"teamName": "Bayern"}, "team2": {"teamName": "Köln"},
                      "matchDateTimeUTC": "2026-11-20T19:30:00Z"}], "match-hash")
        report = build_probe_report(
            candidates, get_json=fake_get, sleep=lambda _: None,
            generated_at=datetime(2026, 11, 15, tzinfo=timezone.utc),
        )
        self.assertEqual(report["summary"]["matches_found"], 1)
        self.assertEqual(report["results"][0]["matchdata_sha256"], "match-hash")
        self.assertEqual(report["safeguards"]["database_writes"], 0)
        self.assertEqual(report["safeguards"]["provider_link_writes"], 0)


if __name__ == "__main__":
    unittest.main()
