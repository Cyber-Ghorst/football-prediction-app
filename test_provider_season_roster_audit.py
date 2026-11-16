import unittest
from unittest.mock import Mock, patch

from provider_season_roster_audit import _select_highlightly, audit_livescore_rosters


class ProviderSeasonRosterAuditTests(unittest.TestCase):
    def test_exact_name_and_country_selects_single_highlightly_competition(self):
        rows = [
            {"id": 1, "name": "Bundesliga",
             "country": {"name": "Germany"}},
            {"id": 2, "name": "Bundesliga",
             "country": {"name": "Austria"}},
        ]
        selected, status = _select_highlightly(
            rows, {"name": "Bundesliga", "country": "Germany"},
        )
        self.assertEqual(status, "unique_exact_name_country")
        self.assertEqual(selected["id"], 1)

    def test_ambiguous_world_cup_candidates_are_held(self):
        rows = [
            {"id": 1, "name": "World Cup", "country": {"name": "World"}},
            {"id": 2, "name": "World Cup", "country": {"name": "World"}},
        ]
        selected, status = _select_highlightly(
            rows, {"name": "World Cup", "country": None},
        )
        self.assertIsNone(selected)
        self.assertEqual(status, "ambiguous_competition")

    def test_missing_exact_competition_is_not_guessed(self):
        selected, status = _select_highlightly(
            [{"id": 1, "name": "Bundesliga", "country": {"name": "Germany"}}],
            {"name": "Ligue 1", "country": "France"},
        )
        self.assertIsNone(selected)
        self.assertEqual(status, "not_found")

    @patch("provider_season_roster_audit.collect_livescore_season_participants")
    @patch("provider_season_roster_audit.collect_livescore_season_standings")
    @patch("provider_season_roster_audit.LiveScoreFootballClient")
    def test_livescore_audit_uses_full_catalogue_then_applies_active_data_gates(
        self, client_class, collect_standings, collect_participants,
    ):
        client = Mock()
        client_class.return_value = client
        client.leagues.return_value = [
            {"slug": "ger.1", "name": "German Bundesliga", "country": "Germany",
             "active": True, "coverage": {"hasData": True}},
            {"slug": "fra.1", "name": "French Ligue 1", "country": "France",
             "active": True, "coverage": {"hasData": True}},
        ]
        collect_standings.side_effect = lambda _client, *, league, **kwargs: {
            "teams": [{"id": "1", "name": "Example"}],
            "league": {"id": league["slug"]},
            "team_evidence_method": "season_standings",
            "team_evidence_complete": True,
            "status": "collected",
        }
        collect_participants.side_effect = lambda _client, *, league, **kwargs: {
            "teams": [{"id": "1", "name": "Example"}],
            "fixtures_examined": 10,
            "league": {"id": league["slug"]},
            "team_evidence_method": "season_window_fixture_participants",
        }
        result = audit_livescore_rosters()
        client.leagues.assert_called_once_with(kind="all", available=False)
        self.assertEqual(
            [row["team_evidence_method"] for row in result["competitions"]],
            ["season_standings", "season_window_fixture_participants"] * 2,
        )
        self.assertEqual(
            [row["team_evidence_complete"] for row in result["competitions"]],
            [True, False, True, False],
        )
        self.assertEqual(
            [row["team_count"] for row in result["competitions"] if "team_count" in row],
            [1, 1, 1, 1],
        )


if __name__ == "__main__":
    unittest.main()
