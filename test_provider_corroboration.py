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



class FakePagedHighlightly:
    def __init__(self, rows, requested_offsets=None):
        self.rows = rows
        self.requested_offsets = requested_offsets if requested_offsets is not None else []
        self.last_metadata = {}

    def matches(self, **params):
        offset = int(params.get("offset", 0))
        limit = int(params.get("limit", 100))
        self.requested_offsets.append(offset)
        self.last_metadata = {
            "pagination": {
                "total_count": len(self.rows),
                "offset": offset,
                "limit": limit,
            }
        }
        return self.rows[offset:offset + limit]

    def close(self):
        return None


class ProviderCorroborationTests(unittest.TestCase):
    def test_sportmonks_fixture_canonicalization_keeps_namespaced_ids(self):
        row = canonicalize_sportmonks_fixture(
            sportmonks_fixture(), competition="Premier League",
            country="England", season=2026,
        )
        self.assertEqual(row["source_ids"]["sportmonks"], "700")
        self.assertEqual(row["home_score"], 2)
        self.assertEqual(row["status"], "finished")

    def test_sportmonks_score_parser_rejects_boolean_fractional_and_negative_values(self):
        for invalid in (True, 1.5, -1, "1.5", "unknown"):
            row = canonicalize_sportmonks_fixture(
                sportmonks_fixture(home_score=invalid, away_score=2),
                competition="Premier League", country="England", season=2026,
            )
            self.assertIsNone(row["home_score"], msg=f"accepted invalid score {invalid!r}")
            self.assertEqual(row["away_score"], 2)

    def test_sportmonks_period_scores_are_not_used_when_current_score_is_missing(self):
        fixture = sportmonks_fixture()
        fixture["scores"] = [
            {"participant_id": 1, "description": "1ST_HALF", "score": {"goals": 1}},
            {"participant_id": 1, "description": "2ND_HALF", "score": {"goals": 2}},
            {"participant_id": 2, "description": "1ST_HALF", "score": {"goals": 0}},
            {"participant_id": 2, "description": "2ND_HALF", "score": {"goals": 1}},
        ]
        row = canonicalize_sportmonks_fixture(
            fixture, competition="Premier League", country="England", season=2026,
        )
        self.assertIsNone(row["home_score"])
        self.assertIsNone(row["away_score"])

    def test_sportmonks_current_score_takes_precedence_over_period_scores(self):
        fixture = sportmonks_fixture()
        fixture["scores"].extend([
            {"participant_id": 1, "description": "1ST_HALF", "score": {"goals": 1}},
            {"participant_id": 2, "description": "1ST_HALF", "score": {"goals": 0}},
        ])
        row = canonicalize_sportmonks_fixture(
            fixture, competition="Premier League", country="England", season=2026,
        )
        self.assertEqual(row["home_score"], 2)
        self.assertEqual(row["away_score"], 1)

    def test_sportmonks_score_parser_accepts_digit_strings_and_whole_numbers(self):
        row = canonicalize_sportmonks_fixture(
            sportmonks_fixture(home_score=" 3 ", away_score=0),
            competition="Premier League", country="England", season=2026,
        )
        self.assertEqual(row["home_score"], 3)
        self.assertEqual(row["away_score"], 0)

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

    def test_highlightly_selected_team_breakdown_exposes_status_and_raw_state(self):
        brighton_finished = highlightly_match()
        brighton_finished.update({
            "id": 9101,
            "homeTeam": {"id": 78, "name": "Brighton & Hove Albion"},
            "awayTeam": {"id": 11, "name": "Arsenal"},
            "state": {"description": "Finished", "score": {"current": "2 - 1"}},
        })
        brighton_scheduled = highlightly_match()
        brighton_scheduled.update({
            "id": 9102,
            "date": "2026-11-09T15:00:00Z",
            "homeTeam": {"id": 78, "name": "Brighton & Hove Albion"},
            "awayTeam": {"id": 12, "name": "Chelsea"},
            "state": {"description": "Not started", "score": {"current": None}},
        })
        report = collect_recent_result_corroboration(
            sportmonks_fixtures=[sportmonks_fixture()],
            competition="Premier League", country="England", season=2026,
            home_team_name="Brighton & Hove Albion", away_team_name="Fulham",
            highlightly_client=FakeHighlightly([brighton_finished, brighton_scheduled]),
            now=NOW,
        )
        breakdown = report["highlightly_diagnostics"]["selected_team_breakdown"]
        brighton = breakdown["Brighton & Hove Albion"]
        self.assertEqual(brighton["normalized_team_records"], 2)
        self.assertEqual(brighton["status_counts"], {"finished": 1, "scheduled": 1})
        self.assertEqual(brighton["completed_score_valid"], 1)
        self.assertEqual(brighton["raw_state_descriptions"]["Finished"], 1)
        self.assertEqual(brighton["sample_records"][0]["home_team_id"], 78)
        self.assertEqual(brighton["sample_records"][0]["raw_state"]["description"], "Finished")

    def test_highlightly_brighton_alias_requires_exact_reviewed_team_id(self):
        primary = sportmonks_fixture()
        primary.update({
            "id": 7001,
            "starting_at": "2026-11-07T15:00:00Z",
            "participants": [
                {"id": 78, "name": "Brighton & Hove Albion", "meta": {"location": "home"}},
                {"id": 79, "name": "Fulham", "meta": {"location": "away"}},
            ],
            "scores": [
                {"participant_id": 78, "description": "CURRENT", "score": {"goals": 2}},
                {"participant_id": 79, "description": "CURRENT", "score": {"goals": 1}},
            ],
        })
        correct = highlightly_match()
        correct.update({
            "id": 9201,
            "date": "2026-11-07T15:02:00Z",
            "homeTeam": {"id": 44185, "name": "Brighton"},
            "awayTeam": {"id": 31420, "name": "Fulham"},
        })
        wrong_id = highlightly_match()
        wrong_id.update({
            "id": 9202,
            "date": "2026-11-07T15:02:00Z",
            "homeTeam": {"id": 99999, "name": "Brighton"},
            "awayTeam": {"id": 31420, "name": "Fulham"},
        })
        report = collect_recent_result_corroboration(
            sportmonks_fixtures=[primary],
            competition="Premier League", country="England", season=2026,
            home_team_name="Brighton & Hove Albion", away_team_name="Fulham",
            highlightly_client=FakeHighlightly([correct, wrong_id]), now=NOW,
        )
        coverage = report["team_history_coverage"]["Brighton & Hove Albion"]
        self.assertEqual(coverage["highlightly_completed_score_valid"], 1)
        self.assertEqual(coverage["highlightly_exact_matches"], 1)
        self.assertEqual(coverage["highlightly_unmatched_count"], 0)
        self.assertEqual(
            report["highlightly_diagnostics"]["selected_team_breakdown"]["Brighton & Hove Albion"]["completed_score_valid"],
            1,
        )

    def test_highlightly_team_name_catalog_exposes_all_normalized_names_and_ids(self):
        brighton = highlightly_match()
        brighton.update({
            "id": 9191,
            "homeTeam": {"id": 78, "name": "Brighton"},
            "awayTeam": {"id": 11, "name": "Arsenal"},
        })
        report = collect_recent_result_corroboration(
            sportmonks_fixtures=[sportmonks_fixture()],
            competition="Premier League", country="England", season=2026,
            home_team_name="Brighton & Hove Albion", away_team_name="Fulham",
            highlightly_client=FakeHighlightly([brighton]), now=NOW,
        )
        catalog = report["highlightly_diagnostics"]["team_name_catalog"]
        self.assertEqual(catalog["Brighton"]["normalized_name"], "brighton")
        self.assertEqual(catalog["Brighton"]["appearances"], 1)
        self.assertEqual(catalog["Brighton"]["source_team_ids"], ["78"])
        # A short provider label remains diagnostic-only and is not treated as
        # an exact selected-team identity.
        self.assertEqual(
            report["highlightly_diagnostics"]["selected_team_breakdown"]["Brighton & Hove Albion"]["normalized_team_records"],
            0,
        )

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


    def test_highlightly_pages_use_factory_and_preserve_offset_order(self):
        rows = []
        for index in range(101):
            row = highlightly_match()
            row["id"] = 10000 + index
            row["date"] = f"2026-11-{(index % 27) + 1:02d}T15:00:00Z"
            row["homeTeam"] = {"id": 1000 + index, "name": f"Home Club {index}"}
            row["awayTeam"] = {"id": 2000 + index, "name": f"Away Club {index}"}
            rows.append(row)

        requested_offsets = []
        first_client = FakePagedHighlightly(rows, requested_offsets)

        def client_factory():
            return FakePagedHighlightly(rows, requested_offsets)

        report = collect_recent_result_corroboration(
            sportmonks_fixtures=[sportmonks_fixture()],
            competition="Premier League", country="England", season=2026,
            home_team_name="Arsenal", away_team_name="Chelsea",
            highlightly_client=first_client,
            highlightly_client_factory=client_factory,
            now=NOW,
        )

        diagnostics = report["highlightly_diagnostics"]
        self.assertEqual(requested_offsets, [0, 100])
        self.assertEqual(diagnostics["pages_requested"], 2)
        self.assertEqual(diagnostics["raw_rows_received"], 101)
        self.assertEqual(
            [page["offset"] for page in diagnostics["page_metadata"]],
            [0, 100],
        )
        self.assertEqual(
            [page["rows_returned"] for page in diagnostics["page_metadata"]],
            [100, 1],
        )


    def test_highlightly_additional_pages_are_fetched_concurrently_with_cap_two(self):
        import threading
        import time

        rows = []
        for index in range(201):
            row = highlightly_match()
            row["id"] = 30000 + index
            row["homeTeam"] = {"id": 5000 + index, "name": f"Home Club {index}"}
            row["awayTeam"] = {"id": 6000 + index, "name": f"Away Club {index}"}
            rows.append(row)

        state = {"active": 0, "maximum": 0}
        lock = threading.Lock()

        class TrackingClient(FakePagedHighlightly):
            def matches(self, **params):
                offset = int(params.get("offset", 0))
                if offset:
                    with lock:
                        state["active"] += 1
                        state["maximum"] = max(state["maximum"], state["active"])
                    try:
                        time.sleep(0.03)
                        return super().matches(**params)
                    finally:
                        with lock:
                            state["active"] -= 1
                return super().matches(**params)

        report = collect_recent_result_corroboration(
            sportmonks_fixtures=[sportmonks_fixture()],
            competition="Premier League", country="England", season=2026,
            home_team_name="Arsenal", away_team_name="Chelsea",
            highlightly_client=TrackingClient(rows),
            highlightly_client_factory=lambda: TrackingClient(rows),
            now=NOW,
        )

        self.assertEqual(report["highlightly_diagnostics"]["pages_requested"], 3)
        self.assertEqual(report["highlightly_diagnostics"]["raw_rows_received"], 201)
        self.assertEqual(state["maximum"], 2)

    def test_highlightly_rejects_pages_returned_for_the_wrong_offset(self):
        rows = []
        for index in range(101):
            row = highlightly_match()
            row["id"] = 20000 + index
            row["homeTeam"] = {"id": 3000 + index, "name": f"Home Club {index}"}
            row["awayTeam"] = {"id": 4000 + index, "name": f"Away Club {index}"}
            rows.append(row)

        class WrongOffsetClient(FakePagedHighlightly):
            def matches(self, **params):
                page = super().matches(**params)
                if int(params.get("offset", 0)) == 100:
                    self.last_metadata["pagination"]["offset"] = 0
                return page

        report = collect_recent_result_corroboration(
            sportmonks_fixtures=[sportmonks_fixture()],
            competition="Premier League", country="England", season=2026,
            home_team_name="Arsenal", away_team_name="Chelsea",
            highlightly_client=FakePagedHighlightly(rows),
            highlightly_client_factory=lambda: WrongOffsetClient(rows),
            now=NOW,
        )

        self.assertIn("offset 0 for requested offset 100", report["errors"]["highlightly"])
        self.assertNotIn("highlightly", report["provider_records_returned"])



    def test_api_ninjas_team_histories_use_two_independent_sessions_concurrently(self):
        import threading
        import time

        state = {"active": 0, "maximum": 0, "teams": []}
        lock = threading.Lock()

        class TrackingNinjas(FakeNinjas):
            def team_matches(self, **params):
                with lock:
                    state["active"] += 1
                    state["maximum"] = max(state["maximum"], state["active"])
                    state["teams"].append(params["team"])
                try:
                    time.sleep(0.03)
                    return [ninjas_match()]
                finally:
                    with lock:
                        state["active"] -= 1

        first_client = TrackingNinjas([ninjas_match()])
        report = collect_recent_result_corroboration(
            sportmonks_fixtures=[sportmonks_fixture()],
            competition="Premier League", country="England", season=2026,
            home_team_name="Arsenal", away_team_name="Chelsea",
            api_ninjas_client=first_client,
            api_ninjas_client_factory=lambda: TrackingNinjas([ninjas_match()]),
            now=NOW,
        )

        self.assertEqual(state["maximum"], 2)
        self.assertCountEqual(state["teams"], ["Arsenal", "Chelsea"])
        self.assertEqual(report["api_ninjas_diagnostics"]["team_requests"], 2)
        self.assertEqual(report["api_ninjas_diagnostics"]["raw_rows_received"], 2)
        self.assertEqual(report["provider_records_returned"]["api_ninjas"], 1)
        self.assertNotIn("api_ninjas", report["errors"])


if __name__ == "__main__":
    unittest.main()
