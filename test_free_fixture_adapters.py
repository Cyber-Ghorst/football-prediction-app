import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from free_fixture_adapters import (
    BzzoiroAdapter,
    OpenFootballAdapter,
    OpenLigaDBAdapter,
    OpenMatchdayAdapter,
    eligible_observations,
    normalize_livescore_football_events,
    normalize_highlightly_matches,
    normalize_api_ninjas_matches,
)


NOW = datetime.now(timezone.utc)


class Response:
    def __init__(self, payload=None, text=None):
        self._payload = payload
        self.text = text or ""
    def raise_for_status(self):
        return None
    def json(self):
        return self._payload


class FreeFixtureAdapterTests(unittest.TestCase):
    def test_openligadb_discovers_current_league_season_scopes(self):
        client = OpenLigaDBAdapter()
        client._get_json = Mock(side_effect=[
            [
                {"leagueId": 1, "leagueName": "Bundesliga", "leagueShortcut": "bl1", "leagueSeason": "2026",
                 "sport": {"sportName": "Fußball"}},
                {"leagueId": 2, "leagueName": "2. Bundesliga", "leagueShortcut": "bl2", "leagueSeason": "2026",
                 "sport": {"sportName": "Football"}},
                {"leagueId": 9, "leagueName": "Handball", "leagueShortcut": "hand1", "leagueSeason": "2026",
                 "sport": {"sportName": "Handball"}},
            ],
            [
                {"leagueId": 1, "leagueName": "Bundesliga", "leagueShortcut": "bl1", "leagueSeason": "2027",
                 "sport": {"sportName": "Fußball"}},
            ],
        ])
        scopes = client.discover_scopes([2026, 2027])
        self.assertEqual(len(scopes), 3)
        self.assertEqual(scopes[0]["league_shortcut"], "bl1")
        self.assertEqual(scopes[0]["season"], 2026)
        self.assertEqual(scopes[2]["season"], 2027)
        client.close()

    def test_openfootball_discovers_json_files_for_season(self):
        client = OpenFootballAdapter()
        client._get_json = Mock(return_value=[
            {"type": "file", "name": "en.1.json"},
            {"type": "file", "name": "de.1.json"},
            {"type": "file", "name": "README.md"},
            {"type": "dir", "name": "archive"},
        ])
        datasets = client.discover_season_files("2026-27")
        self.assertEqual(
            datasets,
            [
                {"season_file": "2026-27/de.1.json", "competition": "Bundesliga"},
                {"season_file": "2026-27/en.1.json", "competition": "Premier League"},
            ],
        )
        client.close()

    def test_openfootball_rejects_invalid_season_directory(self):
        client = OpenFootballAdapter()
        with self.assertRaisesRegex(ValueError, "YYYY-YY"):
            client.discover_season_files("../master")
        client.close()

    def test_openligadb_maps_documented_utc_match_fields(self):
        row = {
            "matchID": 42,
            "matchDateTimeUTC": (NOW + timedelta(days=1)).replace(tzinfo=None).isoformat(),
            "leagueName": "Bundesliga",
            "leagueSeason": 2026,
            "matchStatus": "scheduled",
            "team1": {"teamId": 1, "teamName": "Home FC"},
            "team2": {"teamId": 2, "teamName": "Away FC"},
        }
        client = OpenLigaDBAdapter()
        client._get_json = Mock(return_value=[row])
        result = client.matches("bl1", 2026)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["eligible_for_review"])
        self.assertEqual(result[0]["provider_fixture_id"], "42")
        self.assertEqual(result[0]["home_team_key"], "1")
        self.assertEqual(result[0]["competition_key"], "bl1")
        self.assertEqual(result[0]["competition_name"], "Bundesliga")
        self.assertEqual(result[0]["season_key"], "2026")
        self.assertTrue(result[0]["kickoff_utc"].endswith("Z"))
        self.assertIn("/getmatchdata/bl1/2026", client._get_json.call_args.args[0])
        client.close()

    def test_openfootball_accepts_explicit_timezone_and_rejects_naive_time(self):
        good = {
            "date": (NOW + timedelta(days=2)).date().isoformat(),
            "time": "18:30:00+00:00",
            "team1": "Home FC", "team2": "Away FC",
        }
        bad = {
            "date": (NOW + timedelta(days=2)).date().isoformat(),
            "time": "18:30:00",
            "team1": "Other Home", "team2": "Other Away",
        }
        explicit_offset = {
            "date": (NOW + timedelta(days=2)).date().isoformat(),
            "time": "18:30:00",
            "utc_offset": "+01:00",
            "team1": "Offset Home", "team2": "Offset Away",
        }
        client = OpenFootballAdapter()
        client._get_json = Mock(return_value={"matches": [good, bad, explicit_offset]})
        rows = client.season("2026-27/eng.1.json", "Premier League")
        self.assertTrue(rows[0]["eligible_for_review"])
        self.assertEqual(rows[1]["exclusion_reason"], "kickoff_missing_timezone_or_precision")
        self.assertTrue(rows[2]["eligible_for_review"])
        self.assertTrue(rows[2]["kickoff_utc"].endswith("Z"))
        self.assertEqual(
            rows[2]["kickoff_utc"],
            f"{(NOW + timedelta(days=2)).date().isoformat()}T17:30:00Z",
        )
        self.assertTrue(rows[0]["provider_fixture_id"].startswith("openfootball:dataset:"))
        self.assertEqual(rows[0]["competition_key"], "eng.1")
        self.assertEqual(rows[0]["competition_name"], "Premier League")
        self.assertEqual(rows[0]["raw_payload"]["country"], "England")
        self.assertEqual(rows[0]["season_key"], "2026-27")
        client.close()

    def test_openfootball_date_only_is_never_prediction_ready(self):
        client = OpenFootballAdapter()
        client._get_json = Mock(return_value={"matches": [{
            "date": (NOW + timedelta(days=2)).date().isoformat(),
            "team1": "Home FC", "team2": "Away FC",
        }]})
        row = client.season("2026-27/eng.1.json", "Premier League")[0]
        self.assertFalse(row["eligible_for_review"])
        self.assertIsNone(row["kickoff_utc"])
        client.close()

    def test_openligadb_normalizes_season_suffix_in_competition_name(self):
        row = {
            "matchID": 43,
            "matchDateTimeUTC": (NOW + timedelta(days=1)).replace(tzinfo=None).isoformat(),
            "leagueName": "1. Fußball-Bundesliga 2026/2027",
            "leagueSeason": 2026,
            "leagueCountry": "Deutschland",
            "matchStatus": "scheduled",
            "team1": {"teamId": 1, "teamName": "Home FC"},
            "team2": {"teamId": 2, "teamName": "Away FC"},
        }
        client = OpenLigaDBAdapter()
        client._get_json = Mock(return_value=[row])
        result = client.matches("bl1", 2026)[0]
        self.assertEqual(result["competition_name"], "Bundesliga")
        self.assertEqual(result["raw_payload"]["leagueCountry"], "Deutschland")
        client.close()

    def test_openligadb_normalizes_herren_suffix(self):
        row = {
            "matchID": 44,
            "matchDateTimeUTC": (NOW + timedelta(days=1)).replace(tzinfo=None).isoformat(),
            "leagueName": "2. Bundesliga 2026/27 (Herren)",
            "leagueSeason": 2026,
            "leagueCountry": "Deutschland",
            "matchStatus": "scheduled",
            "team1": {"teamId": 1, "teamName": "Home FC"},
            "team2": {"teamId": 2, "teamName": "Away FC"},
        }
        client = OpenLigaDBAdapter()
        client._get_json = Mock(return_value=[row])
        self.assertEqual(client.matches("bl2", 2026)[0]["competition_name"], "2. Bundesliga")
        client.close()

    def test_livescore_uses_league_catalogue_name_and_country(self):
        event = {
            "id": "event-10",
            "date": (NOW + timedelta(days=2)).isoformat(),
            "status": {"type": {"name": "STATUS_SCHEDULED"}},
            "season": {"id": "season-26"},
            "competitions": [{
                "id": "event-competition-id",
                "competitors": [
                    {"homeAway": "home", "team": {"id": "1", "displayName": "Home FC"}},
                    {"homeAway": "away", "team": {"id": "2", "displayName": "Away FC"}},
                ],
            }],
        }
        row = normalize_livescore_football_events(
            [event],
            league_key="eng.1",
            source_url="https://worldcup26.ir/get/soccer/eng.1/fixtures",
            league_metadata={
                "id": "catalogue-competition-id",
                "slug": "eng.1",
                "name": "Premier League",
                "country": "England",
            },
        )[0]
        self.assertEqual(row["competition_key"], "catalogue-competition-id")
        self.assertEqual(row["competition_name"], "Premier League")
        self.assertEqual(row["raw_payload"]["country"], "England")
        self.assertEqual(row["raw_payload"]["league"]["country"], "England")

    def test_openmatchday_fixed_cet_minus_one_time_is_converted_to_utc(self):
        client = OpenMatchdayAdapter()
        match_date = (NOW + timedelta(days=2)).date()
        fixtures_url = "https://raw.githubusercontent.com/oladeeayo/open-matchday/master/data/ENG_1_premier-league/fixtures_2627.csv"
        results_url = fixtures_url.replace("fixtures_", "results_")
        client._get_text = Mock(side_effect=[
            "gw,date,time,home,away\n"
            f"11,{match_date.isoformat()},19:00,Home FC,Away FC\n",
            "gw,date,time,home,away,ft_home,ft_away,ft_result\n"
            f"11,{match_date.isoformat()},19:00,Home FC,Away FC,2,1,H\n",
        ])
        row = client.season_csv(
            fixtures_url, competition="League", season="2627",
        )[0]
        result_row = client.season_csv(
            results_url, competition="League", season="2627",
        )[0]
        expected = datetime.combine(
            match_date, datetime.min.time().replace(hour=19),
            tzinfo=timezone(timedelta(hours=1)),
        ).astimezone(timezone.utc)
        self.assertTrue(row["eligible_for_review"])
        self.assertEqual(row["kickoff_utc"], expected.isoformat().replace("+00:00", "Z"))
        self.assertEqual(row["competition_key"], "ENG_1_premier-league")
        self.assertEqual(row["season_key"], "2627")
        self.assertEqual(row["provider_fixture_id"], result_row["provider_fixture_id"])
        self.assertEqual(result_row["raw_payload"]["ft_home"], "2")
        self.assertIn("non-commercial-only", row["licence"])
        client.close()

    def test_bzzoiro_requires_token_and_explicit_endpoint(self):
        with self.assertRaisesRegex(Exception, "BZZOIRO_API_TOKEN"):
            BzzoiroAdapter(token=None, endpoint="https://example.test/fixtures")
        with self.assertRaisesRegex(Exception, "documented BSD API host"):
            BzzoiroAdapter(token="test-token", endpoint="https://example.test/events/")

    def test_bzzoiro_parses_utc_upcoming_payload_without_exposing_token(self):
        client = BzzoiroAdapter(token="secret")
        client._get_json = Mock(return_value={"results": [{
            "id": 99,
            "league_id": 10,
            "season_id": 2026,
            "home_team": {"id": 1, "name": "Home FC"},
            "away_team": {"id": 2, "name": "Away FC"},
            "event_date": (NOW + timedelta(days=1)).isoformat(),
            "status": "upcoming",
        }]})
        row = client.upcoming()[0]
        self.assertTrue(row["eligible_for_review"])
        self.assertEqual(row["provider_fixture_id"], "99")
        self.assertEqual(row["competition_key"], "10")
        self.assertEqual(row["season_key"], "2026")
        self.assertNotIn("secret", str(row))
        self.assertEqual(client._get_json.call_args.kwargs["headers"]["Authorization"], "Token secret")
        self.assertEqual(client._get_json.call_args.args[0], BzzoiroAdapter.BASE_URL)
        self.assertEqual(client._get_json.call_args.kwargs["params"]["status"], "upcoming")
        client.close()


    def test_bzzoiro_event_detail_uses_exact_event_id_and_token(self):
        client = BzzoiroAdapter(token="secret")
        client._get_json = Mock(return_value={"data": {
            "id": 99, "status": "finished",
        }})
        event = client.event("99")
        self.assertEqual(event["id"], 99)
        self.assertEqual(
            client._get_json.call_args.args[0],
            f"{BzzoiroAdapter.BASE_URL}99/",
        )
        self.assertEqual(
            client._get_json.call_args.kwargs["headers"]["Authorization"],
            "Token secret",
        )
        client.close()

    def test_livescore_event_requires_timezone_and_home_away_competitors(self):
        event = {
            "id": "event-1",
            "date": (NOW + timedelta(days=1)).isoformat(),
            "status": {"type": {"name": "STATUS_SCHEDULED"}},
            "season": {"id": "season-26"},
            "competitions": [{
                "id": "league-1",
                "competitors": [
                    {"homeAway": "home", "team": {"id": "team-1", "displayName": "Home FC"}},
                    {"homeAway": "away", "team": {"id": "team-2", "displayName": "Away FC"}},
                ],
            }],
        }
        rows = normalize_livescore_football_events(
            [event], league_key="league-1",
            source_url="https://worldcup26.ir/get/soccer/league-1/fixtures",
            fetched_at=NOW,
        )
        self.assertTrue(rows[0]["eligible_for_review"])
        self.assertEqual(rows[0]["provider_fixture_id"], "event-1")
        self.assertEqual(rows[0]["home_team_key"], "team-1")
        self.assertEqual(rows[0]["season_key"], "season-26")

    def test_livescore_naive_event_date_is_excluded(self):
        event = {
            "id": "event-2", "date": "2026-11-15T19:00:00",
            "status": {"type": {"name": "STATUS_SCHEDULED"}},
            "season": {"id": "season-26"},
            "competitions": [{"id": "league-1", "competitors": [
                {"homeAway": "home", "team": {"id": "1", "displayName": "Home FC"}},
                {"homeAway": "away", "team": {"id": "2", "displayName": "Away FC"}},
            ]}],
        }
        row = normalize_livescore_football_events(
            [event], league_key="league-1", source_url="https://example.test",
            fetched_at=NOW,
        )[0]
        self.assertFalse(row["eligible_for_review"])
        self.assertEqual(row["exclusion_reason"], "kickoff_missing_timezone_or_precision")

    def test_bzzoiro_does_not_fabricate_missing_competition_identity(self):
        client = BzzoiroAdapter(token="secret")
        client._get_json = Mock(return_value={"results": [{
            "id": 100, "season_id": 2026,
            "home_team": {"id": 1, "name": "Home FC"},
            "away_team": {"id": 2, "name": "Away FC"},
            "event_date": (NOW + timedelta(days=1)).isoformat(),
            "status": "upcoming",
        }]})
        row = client.upcoming()[0]
        self.assertFalse(row["eligible_for_review"])
        self.assertIsNone(row["competition_key"])
        self.assertEqual(row["exclusion_reason"], "missing_competition_or_season_identity")
        client.close()

    def test_only_explicitly_eligible_observations_are_selected(self):
        rows = [
            {"eligible_for_review": True, "provider_fixture_id": "a"},
            {"eligible_for_review": False, "provider_fixture_id": "b"},
        ]
        self.assertEqual(eligible_observations(rows), [rows[0]])


    def test_highlightly_scheduled_match_requires_stable_ids_and_timezone(self):
        kickoff = (NOW + timedelta(days=1)).isoformat().replace("+00:00", "Z")
        row = {
            "id": 12345,
            "date": kickoff,
            "country": {"code": "GB", "name": "England"},
            "homeTeam": {"id": 10, "name": "Arsenal", "type": "club"},
            "awayTeam": {"id": 20, "name": "Chelsea", "type": "club"},
            "league": {"id": 8, "season": 2026, "name": "Premier League"},
            "state": {"description": "Not started"},
        }
        result = normalize_highlightly_matches([row], fetched_at=NOW)[0]
        self.assertEqual(result["provider"], "highlightly")
        self.assertEqual(result["provider_fixture_id"], "12345")
        self.assertEqual(result["home_team_key"], "10")
        self.assertEqual(result["away_team_key"], "20")
        self.assertEqual(result["competition_name"], "Premier League")
        self.assertEqual(result["season_key"], "2026")
        self.assertTrue(result["eligible_for_review"])
        self.assertEqual(result["raw_payload"]["country"]["name"], "England")

    def test_highlightly_rejects_missing_stable_team_ids(self):
        kickoff = (NOW + timedelta(days=1)).isoformat().replace("+00:00", "Z")
        row = {
            "id": 12345, "date": kickoff,
            "homeTeam": {"name": "Arsenal"}, "awayTeam": {"name": "Chelsea"},
            "league": {"id": 8, "season": 2026, "name": "Premier League"},
            "state": {"description": "Not started"},
        }
        result = normalize_highlightly_matches([row], fetched_at=NOW)[0]
        self.assertFalse(result["eligible_for_review"])
        self.assertEqual(result["exclusion_reason"], "missing_stable_team_ids")

    def test_api_ninjas_scheduled_match_uses_stable_game_and_team_ids(self):
        kickoff = (NOW + timedelta(days=1)).isoformat().replace("+00:00", "Z")
        row = {
            "game_id": "epl-20261112-ars-che",
            "league": "epl",
            "season": 2026,
            "season_label": "2026-27",
            "start_time": kickoff,
            "status": "scheduled",
            "home_team": {"team_id": "soccer-arsenal", "name": "Arsenal"},
            "away_team": {"team_id": "soccer-chelsea", "name": "Chelsea"},
        }
        result = normalize_api_ninjas_matches(
            [row], league="epl", season=2026, fetched_at=NOW
        )[0]
        self.assertEqual(result["provider"], "api_ninjas")
        self.assertEqual(result["provider_fixture_id"], "epl-20261112-ars-che")
        self.assertEqual(result["home_team_key"], "soccer-arsenal")
        self.assertEqual(result["away_team_key"], "soccer-chelsea")
        self.assertEqual(result["competition_name"], "Premier League")
        self.assertEqual(result["season_name"], "2026-27")
        self.assertTrue(result["eligible_for_review"])
        self.assertEqual(result["raw_payload"]["country"], "England")

    def test_api_ninjas_rejects_missing_provider_fixture_id(self):
        kickoff = (NOW + timedelta(days=1)).isoformat().replace("+00:00", "Z")
        row = {
            "league": "epl", "season": 2026, "start_time": kickoff,
            "status": "scheduled",
            "home_team": {"team_id": "soccer-arsenal", "name": "Arsenal"},
            "away_team": {"team_id": "soccer-chelsea", "name": "Chelsea"},
        }
        result = normalize_api_ninjas_matches(
            [row], league="epl", season=2026, fetched_at=NOW
        )[0]
        self.assertFalse(result["eligible_for_review"])
        self.assertEqual(result["exclusion_reason"], "missing_stable_fixture_id")


if __name__ == "__main__":
    unittest.main()
