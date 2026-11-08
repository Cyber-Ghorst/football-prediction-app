import unittest
from datetime import datetime, timezone

from provider_corroboration import (
    canonicalize_sportmonks_fixture,
    collect_recent_result_corroboration,
)


NOW = datetime(2026, 11, 7, 18, 0, tzinfo=timezone.utc)


def sportmonks_fixture(home_score=2, away_score=1, season_id=2026):
    return {
        "id": 700,
        "season_id": season_id,
        "starting_at": "2026-11-07T15:00:00Z",
        "state_id": 5,
        "state": {"short_name": "FT", "name": "Finished"},
        "participants": [
            {"id": 1, "name": "Arsenal", "meta": {"location": "home"}},
            {"id": 2, "name": "Chelsea", "meta": {"location": "away"}},
        ],
        "scores": [
            {"participant_id": 1, "description": "CURRENT", "score": {"goals": home_score}},
            {"participant_id": 2, "description": "CURRENT", "score": {"goals": away_score}},
        ],
    }


def highlightly_match(home_score=2, away_score=1, country="England"):
    return {
        "id": 9001,
        "date": "2026-11-07T15:02:00Z",
        "homeTeam": {"id": 11, "name": "Arsenal"},
        "awayTeam": {"id": 12, "name": "Chelsea"},
        "league": {
            "id": 99, "name": "Premier League", "season": 2026,
            "country": {"name": country},
        },
        "state": {
            "description": "Finished",
            "score": {"current": f"{home_score} - {away_score}"},
        },
    }


def ninjas_match(home_score=2, away_score=1):
    return {
        "game_id": "epl-20261107-ars-che",
        "league": "epl",
        "season": 2026,
        "start_time": "2026-11-07T15:01:00Z",
        "updated_at": "2026-11-07T17:10:00Z",
        "status": "final",
        "home_team": {"team_id": "soccer-arsenal", "name": "Arsenal"},
        "away_team": {"team_id": "soccer-chelsea", "name": "Chelsea"},
        "home_score": home_score,
        "away_score": away_score,
    }


class FakeHighlightly:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def matches(self, **params):
        self.calls.append(params)
        return self.rows


class FakeNinjas:
    LEAGUES = [{"id": "epl", "name": "Premier League"}]

    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def team_matches(self, **params):
        self.calls.append(params)
        return self.rows


class ProviderCorroborationTests(unittest.TestCase):
    def test_sportmonks_fixture_canonicalization_keeps_namespaced_ids(self):
        row = canonicalize_sportmonks_fixture(
            sportmonks_fixture(), competition="Premier League",
            country="England", season=2026,
        )
        self.assertEqual(row["source_ids"]["sportmonks"], "700")
        self.assertEqual(row["home_score"], 2)
        self.assertEqual(row["status"], "finished")

    def test_team_history_uses_sportmonks_season_id_not_calendar_year(self):
        report = collect_recent_result_corroboration(
            sportmonks_fixtures=[sportmonks_fixture(season_id=25678)],
            competition="Premier League", country="England", season=2026,
            sportmonks_season_id=25678,
            home_team_name="Arsenal", away_team_name="Chelsea",
            highlightly_client=FakeHighlightly([]), now=NOW,
        )
        arsenal = report["team_history_coverage"]["Arsenal"]
        self.assertEqual(arsenal["sportmonks_completed_score_valid"], 1)

    def test_three_provider_agreement_and_conflict_are_exposed(self):
        highlightly = FakeHighlightly([highlightly_match(home_score=3)])
        ninjas = FakeNinjas([ninjas_match(), ninjas_match()])
        report = collect_recent_result_corroboration(
            sportmonks_fixtures=[sportmonks_fixture()],
            competition="Premier League", country="England", season=2026,
            home_team_name="Arsenal", away_team_name="Chelsea",
            highlightly_client=highlightly, api_ninjas_client=ninjas, now=NOW,
        )
        self.assertEqual(report["fixtures_matched_across_sources"], 1)
        self.assertEqual(report["fixtures_with_conflicts"], 1)
        match = report["matches"][0]
        self.assertEqual(match["home_score"], 2)
        self.assertEqual(match["reconciliation"]["home_score"]["provider"], "sportmonks")
        self.assertEqual(match["reconciliation"]["home_score"]["status"], "conflict")
        self.assertEqual(match["reconciliation"]["home_score"]["corroborating_providers"], ["api_ninjas"])
        self.assertEqual(match["reconciliation"]["home_score"]["conflicting_providers"], ["highlightly"])
        observed = {row["provider"]: row["value"] for row in match["reconciliation"]["home_score"]["observations"]}
        self.assertEqual(observed, {"sportmonks": 2, "highlightly": 3, "api_ninjas": 2})
        self.assertTrue(all(row.get("fetched_at") for row in match["reconciliation"]["home_score"]["observations"]))
        self.assertEqual(set(match["source_ids"]), {"sportmonks", "highlightly", "api_ninjas"})
        self.assertEqual(match["agreement_fields"], ["status", "away_score"])
        self.assertEqual(match["conflict_fields"], ["home_score", "kickoff_utc"])
        self.assertEqual(match["diagnostic_status"], "agreement_and_conflict")
        home_score_rows = [row for row in match["field_observations"] if row["field"] == "home_score"]
        self.assertEqual(
            {row["provider"]: row["value"] for row in home_score_rows},
            {"sportmonks": 2, "highlightly": 3, "api_ninjas": 2},
        )
        self.assertTrue(all(row["fetched_at"] for row in home_score_rows))
        self.assertEqual(
            report["field_level_summary"]["home_score"]["fixtures_with_conflict"], 1
        )
        self.assertEqual(
            report["field_level_summary"]["away_score"]["fixtures_with_agreement"], 1
        )
        self.assertEqual(report["fixtures_with_both_agreement_and_conflict"], 1)
        self.assertIn("counted independently", report["interpretation"])
        self.assertEqual(len(ninjas.calls), 2)
        self.assertEqual(highlightly.calls[0]["leagueName"], "Premier League")

    def test_team_history_check_flags_unmatched_highlightly_results_without_adding_them(self):
        extra = highlightly_match()
        extra.update({
            "id": 9002,
            "date": "2026-11-05T15:00:00Z",
            "homeTeam": {"id": 11, "name": "Arsenal"},
            "awayTeam": {"id": 13, "name": "Everton"},
            "state": {"description": "Finished", "score": {"current": "1 - 0"}},
        })
        report = collect_recent_result_corroboration(
            sportmonks_fixtures=[sportmonks_fixture()],
            competition="Premier League", country="England", season=2026,
            home_team_name="Arsenal", away_team_name="Chelsea",
            highlightly_client=FakeHighlightly([highlightly_match(), extra]), now=NOW,
        )
        arsenal = report["team_history_coverage"]["Arsenal"]
        self.assertEqual(arsenal["highlightly_completed_score_valid"], 2)
        self.assertEqual(arsenal["sportmonks_completed_score_valid"], 1)
        self.assertEqual(arsenal["exact_matches_across_sources"], 1)
        self.assertEqual(arsenal["highlightly_results_not_found_in_sportmonks"], 1)
        self.assertEqual(arsenal["unmatched_completed_candidates"][0]["highlightly_match_id"], "9002")
        self.assertEqual(
            arsenal["unmatched_completed_candidates"][0]["review_status"],
            "candidate_only_not_added_to_prediction_history",
        )
        self.assertEqual(len(report["matches"]), 1)

    def test_api_ninjas_team_history_coverage_is_reported_per_team(self):
        extra = ninjas_match()
        extra.update({
            "game_id": "epl-20261105-ars-eve",
            "start_time": "2026-11-05T15:00:00Z",
            "away_team": {"team_id": "soccer-everton", "name": "Everton"},
            "home_score": 1,
            "away_score": 0,
        })
        report = collect_recent_result_corroboration(
            sportmonks_fixtures=[sportmonks_fixture()],
            competition="Premier League", country="England", season=2026,
            home_team_name="Arsenal", away_team_name="Chelsea",
            api_ninjas_client=FakeNinjas([ninjas_match(), extra]), now=NOW,
        )
        arsenal = report["team_history_coverage"]["Arsenal"]
        chelsea = report["team_history_coverage"]["Chelsea"]
        self.assertEqual(arsenal["api_ninjas_completed_score_valid"], 2)
        self.assertEqual(arsenal["api_ninjas_exact_matches"], 1)
        self.assertEqual(arsenal["api_ninjas_unmatched_count"], 1)
        self.assertEqual(
            arsenal["api_ninjas_unmatched_candidates"][0]["api_ninjas_match_id"],
            "epl-20261105-ars-eve",
        )
        self.assertEqual(chelsea["api_ninjas_completed_score_valid"], 1)
        self.assertEqual(chelsea["api_ninjas_exact_matches"], 1)
        self.assertEqual(len(report["matches"]), 1)

    def test_highlightly_team_diagnostics_explain_status_and_score_exclusions(self):
        finished = highlightly_match()
        finished["homeTeam"] = {"id": 78, "name": "Brighton & Hove Albion"}
        finished["awayTeam"] = {"id": 11, "name": "Arsenal"}
        unknown_state = highlightly_match()
        unknown_state.update({
            "id": 9002,
            "date": "2026-11-06T15:00:00Z",
            "homeTeam": {"id": 78, "name": "Brighton & Hove Albion"},
            "awayTeam": {"id": 12, "name": "Chelsea"},
            "state": {
                "description": "Match Finished",
                "score": {"current": "2 - 0"},
            },
        })
        report = collect_recent_result_corroboration(
            sportmonks_fixtures=[],
            competition="Premier League", country="England", season=2026,
            home_team_name="Brighton & Hove Albion", away_team_name="Fulham",
            highlightly_client=FakeHighlightly([finished, unknown_state]), now=NOW,
        )
        diagnostics = report["highlightly_diagnostics"]["team_record_diagnostics"]["Brighton & Hove Albion"]
        self.assertEqual(diagnostics["records_seen_after_competition_season_filters"], 2)
        self.assertEqual(diagnostics["normalized_status_counts"], {"finished": 1, "unknown": 1})
        self.assertEqual(diagnostics["finished_and_score_valid_records"], 1)
        self.assertEqual(diagnostics["sample_records"][1]["state_description"], "Match Finished")
        self.assertEqual(diagnostics["sample_records"][1]["normalized_status"], "unknown")
        self.assertEqual(diagnostics["sample_records"][1]["score_current"], "2 - 0")

    def test_documented_top_level_country_object_is_accepted(self):
        row = highlightly_match()
        row["country"] = {"code": "GB", "name": "England", "logo": ""}
        del row["league"]["country"]
        report = collect_recent_result_corroboration(
            sportmonks_fixtures=[sportmonks_fixture()],
            competition="Premier League", country="England", season=2026,
            home_team_name="Arsenal", away_team_name="Chelsea",
            highlightly_client=FakeHighlightly([row]), now=NOW,
        )
        self.assertEqual(report["provider_records_returned"]["highlightly"], 1)
        self.assertEqual(report["highlightly_diagnostics"]["rejected_country_missing"], 0)
        self.assertEqual(report["highlightly_diagnostics"]["rejected_country_mismatch"], 0)
        self.assertEqual(report["highlightly_diagnostics"]["completed_score_valid_records"], 1)

    def test_documented_top_level_country_mismatch_is_rejected(self):
        row = highlightly_match()
        row["country"] = {"code": "ES", "name": "Spain", "logo": ""}
        del row["league"]["country"]
        report = collect_recent_result_corroboration(
            sportmonks_fixtures=[sportmonks_fixture()],
            competition="Premier League", country="England", season=2026,
            home_team_name="Arsenal", away_team_name="Chelsea",
            highlightly_client=FakeHighlightly([row]), now=NOW,
        )
        self.assertEqual(report["provider_records_returned"]["highlightly"], 0)
        self.assertEqual(report["highlightly_diagnostics"]["rejected_country_mismatch"], 1)
        self.assertEqual(report["highlightly_diagnostics"]["rejected_country_missing"], 0)

    def test_wrong_country_or_competition_is_not_joined(self):
        highlightly = FakeHighlightly([highlightly_match(country="Spain")])
        report = collect_recent_result_corroboration(
            sportmonks_fixtures=[sportmonks_fixture()],
            competition="Premier League", country="England", season=2026,
            home_team_name="Arsenal", away_team_name="Chelsea",
            highlightly_client=highlightly, now=NOW,
        )
        self.assertEqual(report["fixtures_matched_across_sources"], 0)

    def test_wrong_reported_season_is_excluded_from_history_check(self):
        wrong = highlightly_match()
        wrong["league"]["season"] = 2025
        report = collect_recent_result_corroboration(
            sportmonks_fixtures=[sportmonks_fixture()],
            competition="Premier League", country="England", season=2026,
            home_team_name="Arsenal", away_team_name="Chelsea",
            highlightly_client=FakeHighlightly([wrong]), now=NOW,
        )
        self.assertEqual(report["provider_records_returned"]["highlightly"], 0)
        self.assertEqual(report["team_history_coverage"]["Arsenal"]["highlightly_completed_score_valid"], 0)

    def test_missing_source_client_does_not_invent_corroboration(self):
        report = collect_recent_result_corroboration(
            sportmonks_fixtures=[sportmonks_fixture()],
            competition="Premier League", country="England", season=2026,
            home_team_name="Arsenal", away_team_name="Chelsea",
            now=NOW,
        )
        self.assertEqual(report["fixtures_matched_across_sources"], 0)
        self.assertEqual(report["provider_records_returned"], {})

    def test_unmatched_team_and_kickoff_do_not_merge(self):
        row = highlightly_match()
        row["homeTeam"]["name"] = "Different Club"
        report = collect_recent_result_corroboration(
            sportmonks_fixtures=[sportmonks_fixture()],
            competition="Premier League", country="England", season=2026,
            home_team_name="Arsenal", away_team_name="Chelsea",
            highlightly_client=FakeHighlightly([row]), now=NOW,
        )
        self.assertEqual(report["fixtures_matched_across_sources"], 0)


if __name__ == "__main__":
    unittest.main()
