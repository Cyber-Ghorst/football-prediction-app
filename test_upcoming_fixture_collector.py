import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from upcoming_fixture_collector import (
    DAILY_FIXTURE_TARGET,
    FIXTURE_INCLUDE,
    collect_upcoming_fixtures,
    normalize_upcoming_fixtures,
    select_highlighted_fixtures,
)


NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def fixture(fid, kickoff, *, state="NS", league_id=8, season_id=2026,
            home_id=None, away_id=None):
    home_id = home_id if home_id is not None else fid * 2
    away_id = away_id if away_id is not None else fid * 2 + 1
    return {
        "id": fid,
        "league_id": league_id,
        "season_id": season_id,
        "starting_at_timestamp": int(kickoff.timestamp()),
        "state": {"short_name": state, "name": state},
        "league": {"id": league_id, "name": "Premier League",
                   "country": {"name": "England"}},
        "season": {"id": season_id, "name": "2026/2027"},
        "participants": [
            {"id": home_id, "name": f"Home {home_id}",
             "meta": {"location": "home"}},
            {"id": away_id, "name": f"Away {away_id}",
             "meta": {"location": "away"}},
        ],
    }


class FakeClient:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def fixtures_between_all_pages(self, start_date, end_date, **params):
        self.calls.append((start_date, end_date, params))
        return self.rows


class UpcomingFixtureCollectorTests(unittest.TestCase):
    def test_collects_only_scheduled_fixtures_inside_seven_day_rolling_window(self):
        valid = fixture(1, NOW + timedelta(hours=1))
        past = fixture(2, NOW - timedelta(seconds=1))
        too_late = fixture(3, NOW + timedelta(days=7, seconds=1))
        live = fixture(4, NOW + timedelta(hours=2), state="LIVE")
        result = normalize_upcoming_fixtures(
            [valid, past, too_late, live], now=NOW, window_days=7
        )
        self.assertEqual([row["id"] for row in result["fixtures"]], ["1"])
        self.assertEqual(result["window_days"], 7)
        self.assertEqual(result["excluded"]["outside_window"], 2)
        self.assertEqual(result["excluded"]["not_scheduled"], 1)

    def test_rejects_fixtures_with_missing_identity_or_kickoff(self):
        missing_team = fixture(1, NOW + timedelta(hours=1))
        missing_team["participants"] = missing_team["participants"][:1]
        missing_competition = fixture(2, NOW + timedelta(hours=2))
        missing_competition.pop("league_id")
        missing_competition["league"] = {}
        missing_kickoff = fixture(3, NOW + timedelta(hours=3))
        missing_kickoff.pop("starting_at_timestamp")
        missing_kickoff.pop("starting_at", None)
        result = normalize_upcoming_fixtures(
            [missing_team, missing_competition, missing_kickoff],
            now=NOW,
        )
        self.assertEqual(result["fixtures"], [])
        self.assertEqual(result["excluded"]["missing_home_or_away"], 1)
        self.assertEqual(result["excluded"]["missing_competition_or_season"], 1)
        self.assertEqual(result["excluded"]["missing_or_invalid_kickoff"], 1)

    def test_deduplicates_provider_fixture_ids_and_orders_by_kickoff(self):
        later = fixture(2, NOW + timedelta(hours=3))
        earlier = fixture(1, NOW + timedelta(hours=1))
        duplicate = fixture(1, NOW + timedelta(hours=2))
        result = normalize_upcoming_fixtures(
            [later, earlier, duplicate], now=NOW
        )
        self.assertEqual([row["id"] for row in result["fixtures"]], ["1", "2"])
        self.assertEqual(result["excluded"]["duplicate_fixture_id"], 1)

    def test_reports_90_fixture_target_per_calendar_day_without_fabricating_rows(self):
        rows = []
        fixture_id = 1
        for day_offset in range(8):
            kickoff_day = (NOW + timedelta(days=day_offset)).replace(
                hour=12, minute=0, second=0, microsecond=0
            )
            for index in range(DAILY_FIXTURE_TARGET):
                rows.append(fixture(
                    fixture_id, kickoff_day + timedelta(minutes=index),
                    league_id=8 + index % 3,
                ))
                fixture_id += 1
        result = normalize_upcoming_fixtures(rows, now=NOW)
        self.assertEqual(result["fixtures_found"], DAILY_FIXTURE_TARGET * 8)
        self.assertTrue(result["target_met"])
        self.assertEqual(result["target_shortfall"], 0)
        self.assertEqual(result["days_meeting_target"], 8)
        self.assertEqual(result["competitions_found"], 3)
        self.assertTrue(all(
            count == DAILY_FIXTURE_TARGET
            for count in result["daily_fixture_counts_utc"].values()
        ))

        short = normalize_upcoming_fixtures(rows[:12], now=NOW)
        self.assertFalse(short["target_met"])
        self.assertEqual(short["target_shortfall"], 708)
        self.assertEqual(short["fixtures_found"], 12)

    def test_highlights_major_leagues_before_earlier_lower_tier_fixtures(self):
        major_earlier = fixture(1, NOW + timedelta(hours=2), league_id=8)
        major_earlier["league"]["name"] = "Premier League"
        lower_tier_earlier = fixture(2, NOW + timedelta(hours=1), league_id=99)
        lower_tier_earlier["league"]["name"] = "Kenyan Premier League"
        result = normalize_upcoming_fixtures(
            [lower_tier_earlier, major_earlier], now=NOW
        )
        self.assertEqual(result["highlighted_fixtures"][0]["id"], "1")
        self.assertEqual(result["highlighted_fixtures"][0]["highlight_priority"], 1)
        self.assertEqual(result["fixtures_found"], 2)
        self.assertEqual(result["highlighted_count"], 2)

    def test_highlight_selection_is_capped_at_50_and_keeps_major_tier_order(self):
        rows = []
        for index in range(60):
            row = fixture(index + 1, NOW + timedelta(minutes=index + 1))
            row["league"]["name"] = (
                "UEFA Champions League" if index < 8 else "Unknown Competition"
            )
            rows.append(row)
        result = normalize_upcoming_fixtures(rows, now=NOW)
        self.assertEqual(result["fixtures_found"], 60)
        self.assertEqual(result["highlighted_count"], 50)
        self.assertEqual(len(result["highlighted_fixtures"]), 50)
        self.assertTrue(all(
            row["highlight_priority"] == 1
            for row in result["highlighted_fixtures"][:8]
        ))
        self.assertEqual(
            sum(1 for row in result["fixtures"] if row["is_highlighted"]), 50
        )

    def test_select_highlighted_fixtures_rejects_invalid_limit(self):
        with self.assertRaises(ValueError):
            select_highlighted_fixtures([], limit=0)

    def test_postponed_fixture_with_new_kickoff_is_retained_in_window(self):
        postponed = fixture(77, NOW + timedelta(days=2), state="Postponed")
        result = normalize_upcoming_fixtures([postponed], now=NOW, window_days=7)
        self.assertEqual(result["fixtures_found"], 1)
        self.assertEqual(result["fixtures"][0]["id"], "77")
        self.assertEqual(result["fixtures"][0]["state"]["short_name"], "Postponed")

    def test_rejects_window_longer_than_one_week(self):
        with self.assertRaises(ValueError):
            normalize_upcoming_fixtures([], now=NOW, window_days=8)

    def test_collector_requests_provider_date_range_and_persists_valid_rows(self):
        rows = [fixture(10, NOW + timedelta(hours=2))]
        client = FakeClient(rows)
        with patch(
            "football_repository.upsert_discovered_fixtures",
            return_value={
                "fixtures_upserted": 1,
                "competitions_upserted": 1,
                "teams_upserted": 2,
            },
        ) as save:
            result = collect_upcoming_fixtures(
                client=client, now=NOW, database_url="postgresql://example"
            )
        self.assertEqual(
            client.calls,
            [("2026-11-10", "2026-11-17", {"include": FIXTURE_INCLUDE})],
        )
        save.assert_called_once_with("postgresql://example", result["fixtures"])
        self.assertTrue(result["persisted"])
        self.assertEqual(result["fixtures_upserted"], 1)
        self.assertEqual(result["future_fixture_sources"], ["sportmonks"])

    def test_unimplemented_future_fixture_provider_fails_closed(self):
        client = FakeClient([])
        with patch(
            "upcoming_fixture_collector.default_provider_registry"
        ) as registry_factory:
            registry_factory.return_value.primary_sources.return_value = [
                "sportmonks", "openligadb"
            ]
            with self.assertRaisesRegex(RuntimeError, "unimplemented provider"):
                collect_upcoming_fixtures(client=client, now=NOW)
        self.assertEqual(client.calls, [])

    def test_invalid_window_is_rejected_before_provider_call(self):
        client = FakeClient([])
        with self.assertRaises(ValueError):
            collect_upcoming_fixtures(client=client, now=NOW, window_days=8)
        self.assertEqual(client.calls, [])


if __name__ == "__main__":
    unittest.main()
