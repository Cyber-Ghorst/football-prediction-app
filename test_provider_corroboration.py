import unittest
from datetime import datetime, timezone

from provider_corroboration import (
    canonicalize_sportmonks_fixture,
    collect_recent_result_corroboration,
)


NOW = datetime(2026, 11, 7, 18, 0, tzinfo=timezone.utc)


def sportmonks_fixture(home_score=2, away_score=1):
    return {
        "id": 700,
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
        self.assertEqual(len(ninjas.calls), 2)
        self.assertEqual(highlightly.calls[0]["leagueName"], "Premier League")

    def test_wrong_country_or_competition_is_not_joined(self):
        highlightly = FakeHighlightly([highlightly_match(country="Spain")])
        report = collect_recent_result_corroboration(
            sportmonks_fixtures=[sportmonks_fixture()],
            competition="Premier League", country="England", season=2026,
            home_team_name="Arsenal", away_team_name="Chelsea",
            highlightly_client=highlightly, now=NOW,
        )
        self.assertEqual(report["fixtures_matched_across_sources"], 0)

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
