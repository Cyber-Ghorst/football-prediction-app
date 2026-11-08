import unittest
from unittest.mock import patch
from datetime import datetime, timezone

from sportmonks import SportmonksClient


def scheduled_fixture(fid, home_id, away_id, kickoff, season_id=2026):
    return {
        "id": fid,
        "season_id": season_id,
        "starting_at": "2026-12-26 15:00:00",
        "starting_at_timestamp": kickoff,
        "participants": [
            {"id": home_id, "meta": {"location": "home"}},
            {"id": away_id, "meta": {"location": "away"}},
        ],
    }


class FakeSportmonksClient(SportmonksClient):
    def __init__(self, schedule, details):
        # Avoid credentials/network setup; _get is fully stubbed.
        self.schedule = schedule
        self.details = details
        self.calls = []

    def _get(self, path, params=None):
        self.calls.append((path, params or {}))
        if path.startswith("schedules/seasons/"):
            return {"data": self.schedule}
        if path.startswith("fixtures/multi/"):
            return {"data": self.details}
        raise AssertionError(f"Unexpected endpoint: {path}")


class UpcomingFixtureEnrichmentTests(unittest.TestCase):
    def test_upcoming_exact_pair_is_enriched_even_without_match_statistics(self):
        kickoff = int(datetime(2026, 12, 26, 15, tzinfo=timezone.utc).timestamp())
        schedule_fixture = scheduled_fixture(7001, 11, 22, kickoff)
        detail_fixture = {
            "id": 7001,
            "season_id": 2026,
            "participants": [
                {"id": 11, "name": "Fulham", "meta": {"location": "home"}},
                {"id": 22, "name": "Brighton & Hove Albion", "meta": {"location": "away"}},
            ],
            "state": {"id": 1, "short_name": "NS", "name": "Not Started"},
        }
        client = FakeSportmonksClient(
            [{"id": 1, "rounds": [{"id": 2, "fixtures": [schedule_fixture]}]}],
            [detail_fixture],
        )
        now = int(datetime(2026, 11, 7, tzinfo=timezone.utc).timestamp())
        with patch("time.time", return_value=now):
            fixtures = client.fixtures_by_season(
                2026, include_statistics=False, team_ids=[11, 22]
            )

        self.assertEqual(fixtures[0]["id"], 7001)
        self.assertEqual(fixtures[0]["state"]["short_name"], "NS")
        self.assertEqual(fixtures[0]["participants"][0]["name"], "Fulham")
        fetched_at = datetime.fromisoformat(
            fixtures[0]["fixture_details_fetched_at"].replace("Z", "+00:00")
        )
        self.assertIsNotNone(fetched_at.tzinfo)
        self.assertIsNone(fixtures[0].get("updated_at"))
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(client.calls[1][0], "fixtures/multi/7001")
        self.assertEqual(client.calls[1][1]["include"], "participants;state;league;season")

    def test_exact_live_or_past_pair_is_hydrated_for_prediction_ledger_identity(self):
        now = int(datetime(2026, 11, 8, 16, tzinfo=timezone.utc).timestamp())
        schedule_fixture = scheduled_fixture(7002, 11, 22, now - 1800)
        detail_fixture = {
            "id": 7002,
            "season_id": 2026,
            "starting_at": "2026-11-08 15:30:00",
            "participants": [
                {"id": 11, "name": "Brighton", "meta": {"location": "home"}},
                {"id": 22, "name": "Brentford", "meta": {"location": "away"}},
            ],
            "state": {"id": 2, "short_name": "LIVE", "name": "In Play"},
            "league": {"name": "Premier League"},
            "season": {"name": "2026/2027"},
        }
        client = FakeSportmonksClient(
            [{"id": 1, "rounds": [{"id": 2, "fixtures": [schedule_fixture]}]}],
            [detail_fixture],
        )
        with patch("time.time", return_value=now):
            fixtures = client.fixtures_by_season(2026, include_statistics=False, team_ids=[11, 22])
        self.assertEqual(fixtures[0]["id"], 7002)
        self.assertEqual(fixtures[0]["state"]["short_name"], "LIVE")
        self.assertEqual(fixtures[0]["league"]["name"], "Premier League")
        self.assertEqual(fixtures[0]["season"]["name"], "2026/2027")
        self.assertEqual(client.calls[1][0], "fixtures/multi/7002")
        self.assertEqual(client.calls[1][1]["include"], "participants;state;league;season")

    def test_completed_fixture_details_are_fetched_in_batches_of_at_most_10(self):
        now = int(datetime(2026, 11, 7, tzinfo=timezone.utc).timestamp())
        schedule_rows = []
        detail_rows = []
        fixture_id = 8000
        for home_id, away_id in [(11, 12), (13, 14), (15, 16)]:
            for index in range(10):
                fixture_id += 1
                row = scheduled_fixture(
                    fixture_id, home_id, away_id, now - (index + 1) * 86400
                )
                row["state_id"] = 5
                schedule_rows.append(row)
                detail_rows.append({
                    "id": fixture_id,
                    "season_id": 2026,
                    "participants": row["participants"],
                    "scores": [],
                    "state": {"id": 5, "short_name": "FT"},
                })

        client = FakeSportmonksClient(
            [{"id": 1, "rounds": [{"id": 2, "fixtures": schedule_rows}]}],
            detail_rows,
        )
        fixtures = client.fixtures_by_season(
            2026, include_statistics=True, team_ids=[11, 12, 13, 14, 15, 16]
        )

        multi_calls = [
            path for path, _ in client.calls if path.startswith("fixtures/multi/")
        ]
        self.assertEqual(len(multi_calls), 3)
        requested_ids = []
        for path in multi_calls:
            ids = path.rsplit("/", 1)[1].split(",")
            self.assertLessEqual(len(ids), 10)
            requested_ids.extend(ids)
        self.assertEqual(len(requested_ids), 30)
        self.assertTrue(all(fixture.get("state") for fixture in fixtures))

    def test_unrelated_wrong_season_and_wrong_pair_are_not_hydrated(self):
        now_dt = datetime(2026, 11, 7, tzinfo=timezone.utc)
        now = int(now_dt.timestamp())
        schedule_rows = [
            scheduled_fixture(1, 11, 22, now + 3600, season_id=2025),
            scheduled_fixture(2, 11, 33, now + 3600),
            scheduled_fixture(3, 11, 33, now - 3600),
        ]
        client = FakeSportmonksClient(
            [{"id": 1, "rounds": [{"id": 2, "fixtures": schedule_rows}]}],
            [],
        )
        with patch("time.time", return_value=now):
            client.fixtures_by_season(2026, include_statistics=False, team_ids=[11, 22])

        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0][0], "schedules/seasons/2026")


if __name__ == "__main__":
    unittest.main()
