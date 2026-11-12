from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from free_fixture_window_coverage import (
    PROVIDERS,
    build_free_fixture_window_coverage,
    build_window_coverage_report,
)


NOW = datetime(2026, 11, 11, 0, 0, tzinfo=timezone.utc)


def observation(provider, fixture_id, *, kickoff="2026-11-12T15:00:00Z",
                fetched="2026-11-11T00:00:00Z", country="England",
                competition="Premier League", season="2026/27",
                home="Arsenal", away="Chelsea", status="scheduled"):
    raw = {"league": {"country": country}}
    if country is not None:
        raw["country"] = country
    return {
        "provider": provider,
        "provider_fixture_id": fixture_id,
        "eligible_for_review": True,
        "status": status,
        "kickoff_utc": kickoff,
        "fetched_at": fetched,
        "competition_name": competition,
        "season_name": season,
        "home_team_name": home,
        "away_team_name": away,
        "raw_payload": raw,
    }


def snapshot(provider, rows, retrieved="2026-11-11T00:00:00Z"):
    return {
        "provider": provider,
        "retrieved_at": retrieved,
        "payload": {"observations": rows},
    }


class FreeFixtureWindowCoverageTests(unittest.TestCase):
    def test_exact_country_competition_season_teams_and_kickoff_deduplicate(self):
        snapshots = {
            "highlightly": [snapshot("highlightly", [
                observation("highlightly", "hl:1"),
            ])],
            "api_ninjas": [snapshot("api_ninjas", [
                observation("api_ninjas", "ninjas:1"),
            ])],
            "openligadb": [snapshot("openligadb", [
                observation("openligadb", "ol:1", country=None),
            ])],
        }
        report = build_window_coverage_report(
            snapshots, now=NOW, daily_target=2,
            highlightly_use_allowed=True, api_ninjas_noncommercial_confirmed=True,
        )
        self.assertEqual(report["fresh_provider_fixture_records_in_window"], 3)
        self.assertEqual(report["unique_fixtures_in_window"], 2)
        self.assertEqual(report["exact_identity_duplicates_removed"], 1)
        self.assertEqual(report["daily_unique_fixture_counts_utc"]["2026-11-12"], 2)
        self.assertEqual(report["daily_counts_by_provider_utc"]["highlightly"]["2026-11-12"], 1)
        self.assertEqual(report["daily_counts_by_provider_utc"]["api_ninjas"]["2026-11-12"], 1)
        self.assertEqual(report["target_shortfall_total"], 12)
        self.assertEqual(report["minimum_target_shortfall_total"], 68)
        self.assertEqual(report["stretch_target_shortfall_total"], 208)
        self.assertFalse(report["minimum_target_met"])
        self.assertFalse(report["target_met"])
        self.assertFalse(report["stretch_target_met"])
        self.assertEqual(report["max_highlights"], 15)
        self.assertEqual(report["calendar_days_in_window"], 9)
        self.assertEqual(report["target_days_in_window"], 7)
        self.assertIn("2026-11-15", report["daily_target_shortfalls_utc"])
        self.assertNotIn("2026-11-11", report["daily_target_shortfalls_utc"])
        self.assertNotIn("2026-11-20", report["daily_target_shortfalls_utc"])
        self.assertEqual(report["partial_boundary_days_utc"], {
            "2026-11-11": 0, "2026-11-20": 0,
        })
        self.assertEqual(report["canonical_fixture_writes"], 0)
        self.assertEqual(report["temporary_fixture_staging_writes"], 0)
        self.assertEqual(report["prediction_ledger_writes"], 0)

    def test_stale_snapshots_and_timezone_naive_kickoffs_are_excluded(self):
        snapshots = {
            "livescore_football": [snapshot(
                "livescore_football",
                [observation("livescore_football", "ls:1")],
                retrieved="2026-11-09T22:00:00Z",
            )],
            "bzzoiro": [snapshot("bzzoiro", [
                observation("bzzoiro", "bz:1", kickoff="2026-11-12T15:00:00"),
            ])],
        }
        report = build_window_coverage_report(
            snapshots, now=NOW, highlightly_use_allowed=True,
        )
        self.assertEqual(report["stale_snapshots_skipped"], 1)
        self.assertEqual(
            report["rejected_observation_counts"]["missing_timezone_aware_timestamp"],
            1,
        )
        self.assertEqual(report["unique_fixtures_in_window"], 0)

    def test_rejection_counts_are_attributed_to_each_provider(self):
        snapshots = {
            "api_ninjas": [snapshot("api_ninjas", [
                observation("api_ninjas", "ninjas:naive", kickoff="2026-11-12T15:00:00"),
            ])],
            "highlightly": [snapshot("highlightly", [
                observation("highlightly", "hl:bad-status", status="in_play"),
            ])],
        }
        report = build_window_coverage_report(
            snapshots, now=NOW, highlightly_use_allowed=True,
            api_ninjas_noncommercial_confirmed=True,
        )
        self.assertEqual(
            report["rejected_observation_counts_by_provider"]["api_ninjas"]["missing_timezone_aware_timestamp"],
            1,
        )
        self.assertEqual(
            report["rejected_observation_counts_by_provider"]["highlightly"]["not_scheduled"],
            1,
        )

    def test_bzzoiro_notstarted_status_is_counted_in_coverage(self):
        snapshots = {
            "bzzoiro": [snapshot("bzzoiro", [
                observation("bzzoiro", "bz:notstarted", status="notstarted"),
            ])],
        }
        report = build_window_coverage_report(snapshots, now=NOW)
        self.assertEqual(report["fresh_provider_fixture_records_in_window"], 1)
        self.assertEqual(report["unique_fixtures_in_window"], 1)
        self.assertEqual(report["daily_counts_by_provider_utc"]["bzzoiro"]["2026-11-12"], 1)
        self.assertNotIn(
            "not_scheduled",
            report["rejected_observation_counts_by_provider"].get("bzzoiro", {}),
        )

    def test_future_dated_snapshot_is_rejected(self):
        snapshots = {
            "highlightly": [snapshot(
                "highlightly",
                [observation("highlightly", "hl:future")],
                retrieved="2026-11-11T00:10:00Z",
            )],
        }
        report = build_window_coverage_report(
            snapshots, now=NOW, highlightly_use_allowed=True,
        )
        self.assertEqual(report["stale_snapshots_skipped"], 1)
        self.assertEqual(report["unique_fixtures_in_window"], 0)

    def test_out_of_window_fixtures_are_not_counted(self):
        snapshots = {
            "api_ninjas": [snapshot("api_ninjas", [
                observation("api_ninjas", "ninjas:past", kickoff="2026-11-10T15:00:00Z"),
                observation("api_ninjas", "ninjas:late", kickoff="2026-11-20T15:00:00Z"),
            ])],
        }
        report = build_window_coverage_report(
            snapshots, now=NOW, api_ninjas_noncommercial_confirmed=True,
        )
        self.assertEqual(report["source_observations_loaded"], 2)
        self.assertEqual(report["unique_fixtures_in_window"], 0)

    @patch("free_fixture_window_coverage.load_provider_observation_snapshots", return_value=[])
    def test_loads_recent_snapshots_for_every_approved_provider(self, load):
        report = build_free_fixture_window_coverage(
            "provider-db", now=NOW, highlightly_use_allowed=True,
            api_ninjas_noncommercial_confirmed=True,
            open_matchday_noncommercial_confirmed=True,
        )
        self.assertEqual(load.call_count, len(PROVIDERS))
        self.assertEqual(
            {call.kwargs["provider"] for call in load.call_args_list},
            set(PROVIDERS),
        )
        self.assertTrue(all(call.kwargs["limit"] == 5 for call in load.call_args_list))
        self.assertEqual(report["unique_fixtures_in_window"], 0)

    @patch("free_fixture_window_coverage.load_provider_observation_snapshots", return_value=[])
    def test_restricted_providers_are_not_loaded_without_use_acknowledgements(self, load):
        report = build_free_fixture_window_coverage("provider-db", now=NOW)
        loaded = {call.kwargs["provider"] for call in load.call_args_list}
        self.assertNotIn("highlightly", loaded)
        self.assertNotIn("api_ninjas", loaded)
        self.assertEqual(
            set(report["providers_excluded_by_terms"]),
            {"highlightly", "api_ninjas", "open_matchday"},
        )

    def test_loader_defaults_match_seven_day_target_and_highlight_cap(self):
        with patch("free_fixture_window_coverage.load_provider_observation_snapshots", return_value=[]):
            report = build_free_fixture_window_coverage("provider-db", now=NOW)
        self.assertEqual(report["window_days"], 7)
        self.assertEqual(report["daily_target"], 20)
        self.assertEqual(report["minimum_daily_target"], 10)
        self.assertEqual(report["stretch_daily_target"], 30)
        self.assertEqual(report["max_highlights"], 15)

    def test_requires_timezone_aware_now(self):
        with self.assertRaises(ValueError):
            build_window_coverage_report({}, now=datetime(2026, 11, 11))


if __name__ == "__main__":
    unittest.main()
