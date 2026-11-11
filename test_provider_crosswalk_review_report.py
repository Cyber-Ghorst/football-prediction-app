import unittest
from unittest.mock import patch

from provider_crosswalk_review_report import build_provider_crosswalk_review_report


class ProviderCrosswalkReviewReportTests(unittest.TestCase):
    @patch("provider_crosswalk_review_report.load_provider_entity_links_by_type")
    @patch("provider_crosswalk_review_report.get_repository_teams")
    @patch("provider_crosswalk_review_report.get_repository_seasons")
    @patch("provider_crosswalk_review_report.get_repository_leagues")
    @patch("provider_crosswalk_review_report.load_provider_observation_snapshots")
    def test_builds_candidates_from_archived_observations(
        self, snapshots, leagues, seasons, teams, links
    ):
        snapshots.return_value = [{
            "snapshot_id": "snap-1",
            "payload": {
                "provider": "openligadb",
                "observations": [{
                    "competition_key": "bl1",
                    "competition_name": "Bundesliga",
                    "season_key": "2026",
                    "season_name": "2026",
                    "home_team_key": "home-1",
                    "home_team_name": "Home FC",
                    "away_team_key": "away-1",
                    "away_team_name": "Away FC",
                    "raw_payload": {
                        "leagueCountry": "Germany",
                        "team1": {"teamCountry": "Germany"},
                        "team2": {"teamCountry": "Germany"},
                    },
                }],
            },
        }]
        leagues.return_value = [{
            "league_id": "sportmonks:bl1",
            "name": "Bundesliga",
            "country": "Germany",
        }]
        seasons.return_value = [{
            "season_id": "sportmonks:2026",
            "name": "2026",
            "league_id": "sportmonks:bl1",
        }]
        teams.return_value = [
            {"team_id": "sportmonks:home", "name": "Home FC", "country": "Germany"},
            {"team_id": "sportmonks:away", "name": "Away FC", "country": "Germany"},
        ]
        links.return_value = {
            "league": {"bl1": "sportmonks:bl1"},
            "season": {},
            "team": {},
        }
        report = build_provider_crosswalk_review_report(
            "provider-db", provider="openligadb", snapshot_limit=50,
        )
        self.assertEqual(report["snapshot_count"], 1)
        self.assertEqual(report["observation_count"], 1)
        self.assertEqual(report["source_entity_counts"]["teams"], 2)
        self.assertEqual(report["candidates"]["leagues"][0]["status"], "already_linked")
        self.assertEqual(report["candidates"]["seasons"][0]["status"],
                         "candidate_requires_manual_approval")
        self.assertEqual(len(report["candidates"]["teams"]), 2)
        self.assertEqual(links.call_count, 1)

    @patch("provider_crosswalk_review_report.get_repository_teams")
    @patch("provider_crosswalk_review_report.get_repository_seasons")
    @patch("provider_crosswalk_review_report.get_repository_leagues")
    def test_reuses_supplied_canonical_catalogue_without_requerying(
        self, leagues, seasons, teams
    ):
        catalogue = {
            "leagues": [{"league_id": "sportmonks:8", "name": "Premier League", "country": "England"}],
            "seasons": [{"season_id": "sportmonks:2026", "name": "2026/27"}],
            "teams": [{"team_id": "sportmonks:1", "name": "Arsenal", "country": "England"}],
        }
        with patch("provider_crosswalk_review_report.load_provider_observation_snapshots", return_value=[]), \
             patch("provider_crosswalk_review_report.load_provider_entity_links_by_type", return_value={}):
            report = build_provider_crosswalk_review_report(
                "provider-db", provider="highlightly",
                canonical_catalogue=catalogue,
            )
        self.assertEqual(report["canonical_options"]["leagues"], ["sportmonks:8"])
        leagues.assert_not_called()
        seasons.assert_not_called()
        teams.assert_not_called()

    @patch("provider_crosswalk_review_report.load_provider_observation_snapshots", return_value=[])
    @patch("provider_crosswalk_review_report.get_repository_teams", return_value=[])
    @patch("provider_crosswalk_review_report.get_repository_seasons", return_value=[])
    @patch("provider_crosswalk_review_report.get_repository_leagues", return_value=[])
    @patch("provider_crosswalk_review_report.load_provider_entity_links_by_type", return_value={"league": {}, "season": {}, "team": {}})
    def test_empty_archive_returns_empty_review_report(
        self, links, leagues, seasons, teams, snapshots
    ):
        report = build_provider_crosswalk_review_report("provider-db", provider="bzzoiro")
        self.assertEqual(report["snapshot_count"], 0)
        self.assertEqual(report["observation_count"], 0)
        self.assertEqual(report["source_entity_counts"], {
            "leagues": 0, "seasons": 0, "teams": 0,
        })
        self.assertEqual(report["candidates"]["teams"], [])


if __name__ == "__main__":
    unittest.main()
