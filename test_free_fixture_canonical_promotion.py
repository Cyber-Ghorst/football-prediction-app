import unittest
from datetime import datetime, timedelta, timezone

from free_fixture_canonical_promotion import (
    SUPPORTED_PROVIDERS,
    assess_free_fixture_observation,
)


NOW = datetime(2026, 11, 11, 2, 0, tzinfo=timezone.utc)
OBSERVATION = {
    "provider_fixture_id": "42",
    "eligible_for_review": True,
    "exclusion_reason": None,
    "competition_key": "league-1",
    "season_key": "season-1",
    "home_team_key": "home-1",
    "away_team_key": "away-1",
    "home_team_name": "Home FC",
    "away_team_name": "Away FC",
    "kickoff_utc": "2026-11-13T18:00:00Z",
    "status": "scheduled",
    "fetched_at": "2026-11-11T01:55:00Z",
}


def canonical_entities():
    return {
        "leagues": {
            "sportmonks:10": {
                "league_id": "sportmonks:10", "name": "Premier League", "country": "England"
            }
        },
        "seasons": {
            "sportmonks:20": {
                "season_id": "sportmonks:20", "league_id": "sportmonks:10", "name": "2026/27"
            }
        },
        "teams": {
            "sportmonks:30": {"team_id": "sportmonks:30", "name": "Home FC"},
            "sportmonks:40": {"team_id": "sportmonks:40", "name": "Away FC"},
        },
    }


class FreeFixtureCanonicalPromotionAssessmentTests(unittest.TestCase):
    def assess(self, observation=None, **kwargs):
        retrieved_at = kwargs.pop("snapshot_retrieved_at", "2026-11-11T01:56:00Z")
        return assess_free_fixture_observation(
            "openligadb",
            observation or OBSERVATION,
            snapshot_id="snapshot-1",
            snapshot_retrieved_at=retrieved_at,
            league_links={"league-1": "sportmonks:10"},
            season_links={"league-1::season-1": "sportmonks:20"},
            team_links={"home-1": "sportmonks:30", "away-1": "sportmonks:40"},
            canonical_entities=canonical_entities(),
            now=NOW,
            licence_acknowledged=True,
            **kwargs,
        )

    def test_exact_explicit_crosswalks_make_future_fixture_ready(self):
        result = self.assess()
        self.assertEqual(result["decision"], "ready_for_promotion")
        self.assertEqual(result["fixture_id"], "openligadb:42")
        self.assertEqual(result["canonical"]["league_id"], "sportmonks:10")
        self.assertEqual(result["canonical"]["home_team"], "Home FC")

    def test_highlightly_and_api_ninjas_can_promote_only_with_explicit_sportmonks_links(self):
        for provider in ("highlightly", "api_ninjas"):
            self.assertIn(provider, SUPPORTED_PROVIDERS)
            observation = {
                **OBSERVATION,
                "status": "Not started" if provider == "highlightly" else "scheduled",
            }
            result = assess_free_fixture_observation(
                provider, observation,
                snapshot_id="snapshot-1",
                snapshot_retrieved_at="2026-11-11T01:56:00Z",
                league_links={"league-1": "sportmonks:10"},
                season_links={"league-1::season-1": "sportmonks:20"},
                team_links={"home-1": "sportmonks:30", "away-1": "sportmonks:40"},
                canonical_entities=canonical_entities(),
                now=NOW,
                licence_acknowledged=True,
                api_ninjas_noncommercial_confirmed=(provider == "api_ninjas"),
            )
            self.assertEqual(result["decision"], "ready_for_promotion")
            self.assertTrue(all(
                str(value).startswith("sportmonks:")
                for key, value in result["canonical"].items()
                if key.endswith("_id")
            ))

    def test_api_ninjas_free_plan_requires_noncommercial_acknowledgement(self):
        result = assess_free_fixture_observation(
            "api_ninjas", OBSERVATION, snapshot_id="snapshot-1",
            snapshot_retrieved_at="2026-11-11T01:56:00Z",
            league_links={"league-1": "sportmonks:10"},
            season_links={"league-1::season-1": "sportmonks:20"},
            team_links={"home-1": "sportmonks:30", "away-1": "sportmonks:40"},
            canonical_entities=canonical_entities(), now=NOW,
            licence_acknowledged=True,
        )
        self.assertEqual(result["decision"], "blocked")
        self.assertEqual(
            result["reason"],
            "api_ninjas_free_plan_noncommercial_use_not_confirmed",
        )

    def test_missing_any_entity_link_blocks_promotion(self):
        result = assess_free_fixture_observation(
            "openligadb", OBSERVATION, snapshot_id="snapshot-1",
            snapshot_retrieved_at="2026-11-11T01:56:00Z",
            league_links={"league-1": "sportmonks:10"},
            season_links={"league-1::season-1": "sportmonks:20"},
            team_links={"home-1": "sportmonks:30"},
            canonical_entities=canonical_entities(), now=NOW,
            licence_acknowledged=True,
        )
        self.assertEqual(result["decision"], "blocked")
        self.assertIn("missing_explicit_crosswalk", result["reason"])

    def test_stale_snapshot_is_blocked(self):
        result = self.assess(snapshot_retrieved_at="2026-11-09T00:00:00Z")
        self.assertEqual(result["reason"], "stale_observation_snapshot")

    def test_timezone_less_kickoff_is_blocked_even_if_marked_eligible(self):
        observation = {**OBSERVATION, "kickoff_utc": "2026-11-13T18:00:00"}
        result = self.assess(observation)
        self.assertEqual(result["reason"], "kickoff_missing_timezone_or_precision")

    def test_outside_seven_day_window_is_blocked(self):
        observation = {
            **OBSERVATION,
            "kickoff_utc": (NOW + timedelta(days=8)).isoformat(),
        }
        result = self.assess(observation)
        self.assertEqual(result["reason"], "kickoff_outside_active_future_window")

    def test_wrong_season_parent_is_blocked(self):
        entities = canonical_entities()
        entities["seasons"]["sportmonks:20"]["league_id"] = "sportmonks:999"
        result = assess_free_fixture_observation(
            "openligadb", OBSERVATION, snapshot_id="snapshot-1",
            snapshot_retrieved_at="2026-11-11T01:56:00Z",
            league_links={"league-1": "sportmonks:10"},
            season_links={"league-1::season-1": "sportmonks:20"},
            team_links={"home-1": "sportmonks:30", "away-1": "sportmonks:40"},
            canonical_entities=entities, now=NOW,
            licence_acknowledged=True,
        )
        self.assertEqual(result["reason"], "canonical_season_belongs_to_a_different_competition")

    def test_livescore_requires_upstream_competition_sync_timestamp(self):
        observation = {**OBSERVATION, "source_sync_at": None}
        result = assess_free_fixture_observation(
            "livescore_football", observation, snapshot_id="snapshot-1",
            snapshot_retrieved_at="2026-11-11T01:56:00Z",
            league_links={"league-1": "sportmonks:10"},
            season_links={"league-1::season-1": "sportmonks:20"},
            team_links={"home-1": "sportmonks:30", "away-1": "sportmonks:40"},
            canonical_entities=canonical_entities(), now=NOW,
            licence_acknowledged=True,
        )
        self.assertEqual(result["reason"], "missing_upstream_competition_sync_timestamp")

    def test_stale_livescore_upstream_competition_data_is_blocked(self):
        observation = {**OBSERVATION, "source_sync_at": "2026-11-09T00:00:00Z"}
        result = assess_free_fixture_observation(
            "livescore_football", observation, snapshot_id="snapshot-1",
            snapshot_retrieved_at="2026-11-11T01:56:00Z",
            league_links={"league-1": "sportmonks:10"},
            season_links={"league-1::season-1": "sportmonks:20"},
            team_links={"home-1": "sportmonks:30", "away-1": "sportmonks:40"},
            canonical_entities=canonical_entities(), now=NOW,
            licence_acknowledged=True,
        )
        self.assertEqual(result["reason"], "stale_upstream_competition_data")

    def test_fresh_livescore_upstream_competition_data_can_pass_freshness_gate(self):
        observation = {**OBSERVATION, "source_sync_at": "2026-11-11T01:45:00Z"}
        result = assess_free_fixture_observation(
            "livescore_football", observation, snapshot_id="snapshot-1",
            snapshot_retrieved_at="2026-11-11T01:56:00Z",
            league_links={"league-1": "sportmonks:10"},
            season_links={"league-1::season-1": "sportmonks:20"},
            team_links={"home-1": "sportmonks:30", "away-1": "sportmonks:40"},
            canonical_entities=canonical_entities(), now=NOW,
            licence_acknowledged=True,
        )
        self.assertEqual(result["decision"], "ready_for_promotion")

    def test_non_sportmonks_canonical_targets_are_blocked(self):
        result = assess_free_fixture_observation(
            "openligadb", OBSERVATION, snapshot_id="snapshot-1",
            snapshot_retrieved_at="2026-11-11T01:56:00Z",
            league_links={"league-1": "other:10"},
            season_links={"league-1::season-1": "sportmonks:20"},
            team_links={"home-1": "sportmonks:30", "away-1": "sportmonks:40"},
            canonical_entities=canonical_entities(), now=NOW,
            licence_acknowledged=True,
        )
        self.assertEqual(result["reason"], "canonical_target_is_not_a_sportmonks_entity")


if __name__ == "__main__":
    unittest.main()
