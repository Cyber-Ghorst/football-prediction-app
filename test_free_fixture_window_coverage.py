from datetime import datetime, timedelta, timezone
import unittest

from free_fixture_window_coverage import build_window_coverage_report


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
        )
        self.assertEqual(report["fresh_provider_fixture_records_in_window"], 3)
        self.assertEqual(report["unique_fixtures_in_window"], 2)
        self.assertEqual(report["exact_identity_duplicates_removed"], 1)
        self.assertEqual(report["daily_unique_fixture_counts_utc"]["2026-11-12"], 2)
        self.assertEqual(report["daily_counts_by_provider_utc"]["highlightly"]["2026-11-12"], 1)
        self.assertEqual(report["daily_counts_by_provider_utc"]["api_ninjas"]["2026-11-12"], 1)
        self.assertEqual(report["target_shortfall_total"], 14)
        self.assertFalse(report["target_met"])
        self.assertEqual(report["max_highlights"], 50)
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
        report = build_window_coverage_report(snapshots, now=NOW)
        self.assertEqual(report["stale_snapshots_skipped"], 1)
        self.assertEqual(
            report["rejected_observation_counts"]["missing_timezone_aware_timestamp"],
            1,
        )
        self.assertEqual(report["unique_fixtures_in_window"], 0)

    def test_future_dated_snapshot_is_rejected(self):
        snapshots = {
            "highlightly": [snapshot(
                "highlightly",
                [observation("highlightly", "hl:future")],
                retrieved="2026-11-11T00:10:00Z",
            )],
        }
        report = build_window_coverage_report(snapshots, now=NOW)
        self.assertEqual(report["stale_snapshots_skipped"], 1)
        self.assertEqual(report["unique_fixtures_in_window"], 0)

    def test_out_of_window_fixtures_are_not_counted(self):
        snapshots = {
            "api_ninjas": [snapshot("api_ninjas", [
                observation("api_ninjas", "ninjas:past", kickoff="2026-11-10T15:00:00Z"),
                observation("api_ninjas", "ninjas:late", kickoff="2026-11-20T15:00:00Z"),
            ])],
        }
        report = build_window_coverage_report(snapshots, now=NOW)
        self.assertEqual(report["source_observations_loaded"], 2)
        self.assertEqual(report["unique_fixtures_in_window"], 0)

    def test_requires_timezone_aware_now(self):
        with self.assertRaises(ValueError):
            build_window_coverage_report({}, now=datetime(2026, 11, 11))


if __name__ == "__main__":
    unittest.main()
