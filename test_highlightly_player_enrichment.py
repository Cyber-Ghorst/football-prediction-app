import unittest
from highlightly_player_enrichment import collect_highlightly_player_enrichment


class FakeClient:
    def __init__(self):
        self.player_calls = []
        self.team_calls = []

    def player_statistics(self, player_id):
        self.player_calls.append(str(player_id))
        return [{
            "id": int(player_id), "name": "Player",
            "perCompetition": [
                {"club": "Arsenal", "league": "Premier League", "season": "2026",
                 "gamesPlayed": 10, "minutesPlayed": 800, "goals": 4, "assists": 2},
                {"club": "Arsenal", "league": "Premier League", "season": "2025",
                 "gamesPlayed": 20, "minutesPlayed": 1600, "goals": 8, "assists": 4},
                {"club": "Other Club", "league": "Premier League", "season": "2026",
                 "gamesPlayed": 9, "minutesPlayed": 700, "goals": 3, "assists": 1},
            ],
        }]

    def team_statistics(self, team_id, **params):
        self.team_calls.append((str(team_id), params))
        return [{
            "leagueName": "Premier League", "season": 2026,
            "total": {"games": {"played": 10, "wins": 7, "loses": 2, "draws": 1}},
            "home": {}, "away": {},
        }]


class PlayerEnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.lineups = {
            "home": {"team_id": 11, "team_name": "Arsenal",
                     "starting_players": [{"player_id": 101, "name": "Player"}]},
            "away": {"team_id": 12, "team_name": "Chelsea",
                     "starting_players": [{"player_id": 202, "name": "Player"}]},
        }

    def test_exact_competition_season_and_club_are_required(self):
        client = FakeClient()
        report = collect_highlightly_player_enrichment(
            client=client, lineups=self.lineups, competition="Premier League",
            season=2026, home_team_name="Arsenal", away_team_name="Chelsea",
        )
        self.assertEqual(len(report["players"]), 1)
        self.assertEqual(report["players"][0]["team"], "home")
        self.assertEqual(report["players"][0]["statistics"]["goals"], 4)
        self.assertEqual(report["teams"]["home"]["status"], "matched")
        self.assertEqual(report["team_requests"], 2)
        self.assertEqual(report["player_requests"], 2)

    def test_missing_lineups_do_not_trigger_requests(self):
        client = FakeClient()
        report = collect_highlightly_player_enrichment(
            client=client, lineups=None, competition="Premier League",
            season=2026, home_team_name="Arsenal", away_team_name="Chelsea",
        )
        self.assertEqual(report["availability"], "unknown_no_exact_provider_lineup")
        self.assertEqual(client.player_calls, [])
        self.assertEqual(client.team_calls, [])

    def test_player_without_provider_id_is_not_name_matched(self):
        client = FakeClient()
        lineups = {"home": {"team_id": 11, "team_name": "Arsenal",
                            "starting_players": [{"name": "Unknown Player"}]},
                   "away": {"team_id": 12, "team_name": "Chelsea", "starting_players": []}}
        report = collect_highlightly_player_enrichment(
            client=client, lineups=lineups, competition="Premier League",
            season=2026, home_team_name="Arsenal", away_team_name="Chelsea",
        )
        self.assertEqual(client.player_calls, [])
        self.assertEqual(len(report["unknown_players"]), 1)

    def test_player_request_cap_is_respected(self):
        client = FakeClient()
        lineups = {"home": {"team_id": 11, "team_name": "Arsenal",
                            "starting_players": [{"player_id": i} for i in range(1, 8)]},
                   "away": {"team_id": 12, "team_name": "Chelsea",
                            "starting_players": [{"player_id": i} for i in range(8, 15)]}}
        report = collect_highlightly_player_enrichment(
            client=client, lineups=lineups, competition="Premier League",
            season=2026, home_team_name="Arsenal", away_team_name="Chelsea",
            max_players=5,
        )
        self.assertEqual(report["player_requests"], 5)


if __name__ == "__main__":
    unittest.main()
