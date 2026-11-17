import unittest
from datetime import datetime, timezone

from competition_readiness_live_audit import build_live_readiness_records

NOW = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)


class LiveReadinessEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.leagues = [{
            "league_id": "sportmonks:8", "name": "Premier League",
            "country": "England", "competition_type": "league",
            "source_provider": "sportmonks",
        }]
        self.seasons = [{
            "season_id": "sportmonks:28083", "league_id": "sportmonks:8",
            "name": "2026/2027", "is_current": True,
            "source_provider": "sportmonks",
        }]
        self.fixtures = [{
            "fixture_id": "sportmonks:1001", "season_id": "sportmonks:28083",
            "league_id": "sportmonks:8", "home_team_id": "sportmonks:10",
            "away_team_id": "sportmonks:11",
            "starting_at": datetime(2026, 11, 20, 18, tzinfo=timezone.utc),
            "status": "NS", "home_goals": None, "away_goals": None,
            "source_provider": "sportmonks",
            "provider_updated_at": datetime(2026, 11, 17, 10, tzinfo=timezone.utc),
        }]

    def test_unapproved_native_provider_rows_are_not_verified(self):
        records = build_live_readiness_records(
            self.leagues, self.seasons, self.fixtures, [], now=NOW,
        )
        record = records[0]
        self.assertFalse(record["competition"]["identity_verified"])
        self.assertFalse(record["season"]["identity_verified"])
        self.assertEqual(record["teams"]["approved_mapping_count"], 0)
        self.assertFalse(record["fixture"]["upcoming_valid"])
        self.assertEqual(record["fixture"]["source_freshness"], "fresh")

    def test_only_exact_approved_links_can_verify_entities_and_fixture(self):
        links = [
            {"provider": "sportmonks", "entity_type": "league",
             "provider_entity_id": "8", "canonical_entity_id": "sportmonks:8",
             "target_parent_id": None},
            {"provider": "sportmonks", "entity_type": "season",
             "provider_entity_id": "28083", "canonical_entity_id": "sportmonks:28083",
             "target_parent_id": "sportmonks:8"},
            {"provider": "sportmonks", "entity_type": "team",
             "provider_entity_id": "10", "canonical_entity_id": "sportmonks:10"},
            {"provider": "sportmonks", "entity_type": "team",
             "provider_entity_id": "11", "canonical_entity_id": "sportmonks:11"},
            {"provider": "sportmonks", "entity_type": "fixture",
             "provider_entity_id": "1001", "canonical_entity_id": "sportmonks:1001",
             "target_parent_id": None},
        ]
        records = build_live_readiness_records(
            self.leagues, self.seasons, self.fixtures, links, now=NOW,
        )
        record = records[0]
        self.assertTrue(record["competition"]["identity_verified"])
        self.assertTrue(record["season"]["identity_verified"])
        self.assertEqual(record["teams"]["approved_mapping_count"], 2)
        self.assertTrue(record["fixture"]["upcoming_valid"])
        # A valid fixture alone cannot make a competition prediction-ready.
        self.assertEqual(record["teams"]["statistics_complete_by_team"],
                         {"sportmonks:10": False, "sportmonks:11": False})
        self.assertEqual(record["teams"]["tactical_components_by_team"], {})

    def test_season_mapping_to_different_competition_is_rejected(self):
        links = [
            {"provider": "sportmonks", "entity_type": "league",
             "provider_entity_id": "8", "canonical_entity_id": "sportmonks:8"},
            {"provider": "sportmonks", "entity_type": "season",
             "provider_entity_id": "28083", "canonical_entity_id": "sportmonks:28083",
             "target_parent_id": "sportmonks:999"},
        ]
        record = build_live_readiness_records(
            self.leagues, self.seasons, self.fixtures, links, now=NOW,
        )[0]
        self.assertFalse(record["season"]["identity_verified"])
        self.assertFalse(record["fixture"]["upcoming_valid"])

    def test_future_provider_timestamp_is_not_fresh(self):
        self.fixtures[0]["provider_updated_at"] = datetime(2026, 11, 18, 10, tzinfo=timezone.utc)
        record = build_live_readiness_records(
            self.leagues, self.seasons, self.fixtures, [], now=NOW,
        )[0]
        self.assertEqual(record["fixture"]["source_freshness"], "stale")

    def test_missing_fixture_freshness_fails_closed(self):
        self.fixtures[0]["provider_updated_at"] = None
        self.fixtures[0]["collected_at"] = None
        record = build_live_readiness_records(
            self.leagues, self.seasons, self.fixtures, [], now=NOW,
        )[0]
        self.assertEqual(record["fixture"]["source_freshness"], "unknown")

    def test_statistics_and_tactical_evidence_use_layer2_profile_builder(self):
        teams = [
            {"team_id": "sportmonks:10", "name": "Home FC"},
            {"team_id": "sportmonks:11", "name": "Away FC"},
        ]
        fixtures = []
        statistics = []
        metrics = {
            "Ball Possession": 55, "Passes %": 85, "Total Shots": 12,
            "Shots on Target": 5, "Tackles": 16, "Interceptions": 8,
            "Blocked Shots": 3, "Corner Kicks": 6,
        }
        for index in range(10):
            fixture_id = f"sportmonks:{2000 + index}"
            fixtures.append({
                "fixture_id": fixture_id, "season_id": "sportmonks:28083",
                "league_id": "sportmonks:8", "home_team_id": "sportmonks:10",
                "away_team_id": "sportmonks:11",
                "starting_at": datetime(2026, 10, 1 + index, 18, tzinfo=timezone.utc),
                "status": "FT", "home_goals": 2, "away_goals": 1,
                "source_provider": "sportmonks",
                "provider_updated_at": datetime(2026, 11, 17, 10, tzinfo=timezone.utc),
            })
            for team_id in ("sportmonks:10", "sportmonks:11"):
                for metric, value in metrics.items():
                    statistics.append({
                        "fixture_id": fixture_id, "team_id": team_id,
                        "statistic_type": metric, "statistic_value": value,
                        "source_provider": "sportmonks",
                    })
        records = build_live_readiness_records(
            self.leagues, self.seasons, fixtures, [], now=NOW,
            team_rows=teams, statistics=statistics,
        )
        record = records[0]
        self.assertEqual(record["teams"]["history_by_team"]["sportmonks:10"], 10)
        self.assertTrue(record["teams"]["statistics_complete_by_team"]["sportmonks:10"])
        self.assertTrue(record["teams"]["statistics_complete_by_team"]["sportmonks:11"])
        self.assertTrue(all(
            record["teams"]["tactical_components_by_team"]["sportmonks:10"][key] is not None
            for key in ("playing_style", "defensive_structure", "attacking_approach")
        ))

    def test_completed_history_requires_terminal_status_and_both_scores(self):
        self.fixtures.append({
            **self.fixtures[0], "fixture_id": "sportmonks:1002",
            "starting_at": datetime(2026, 10, 1, 18, tzinfo=timezone.utc),
            "status": "FT", "home_goals": 2, "away_goals": 1,
        })
        record = build_live_readiness_records(
            self.leagues, self.seasons, self.fixtures, [], now=NOW,
        )[0]
        self.assertEqual(record["teams"]["history_by_team"],
                         {"sportmonks:10": 1, "sportmonks:11": 1})


if __name__ == "__main__":
    unittest.main()
