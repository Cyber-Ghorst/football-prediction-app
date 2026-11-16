import unittest

from livescore_standings_evidence_stage import build_standings_observation_rows
from provider_roster_collection import collect_livescore_season_standings


def observation(slug, label, team_prefix):
    teams = [{"id": f"{team_prefix}{i}", "name": f"Club {i}", "raw": {"id": f"{team_prefix}{i}", "name": f"Club {i}"}}
             for i in range(18)]
    return {
        "provider": "livescore_football",
        "league": {"id": slug, "name": "League", "country": "Country"},
        "season": "2026",
        "team_evidence_method": "season_standings",
        "source_endpoint": f"/get/soccer/{slug}/standings",
        "requested_season_parameter": 2026,
        "source_retrieved_at": "2026-11-16T12:00:00+00:00",
        "provider_payload": {
            "season": 2026,
            "children": [{"id": f"{slug}-child", "name": label,
                          "standings": {"season": 2026, "entries": [
                              {"team": {"id": team["id"], "name": team["name"]}}
                              for team in teams
                          ]}}],
        },
        "provider_returned_season": {
            "competition_season": 2026,
            "standings_season": 2026,
            "child_id": f"{slug}-child",
            "child_label": label,
        },
        "teams": teams,
        "team_evidence_complete": True,
        "status": "collected",
    }


class LiveScoreStandingsEvidenceStageTests(unittest.TestCase):
    def test_bundesliga_prefix_child_label_preserves_all_provenance(self):
        item = observation("ger.1", "2026-27 German Bundesliga", "ger-")
        rows = build_standings_observation_rows(item)
        self.assertEqual(len(rows), 18)
        row = rows[0]
        self.assertEqual(row["season_label"], "2026/27")
        self.assertEqual(row["provenance"]["provider_competition_slug"], "ger.1")
        self.assertEqual(row["provenance"]["requested_season_parameter"], "2026")
        self.assertEqual(row["provenance"]["unique_child_id"], "ger.1-child")
        self.assertEqual(row["provenance"]["nested_standings_season"], 2026)
        self.assertEqual(row["raw_response"], item["provider_payload"])
        self.assertEqual(row["source_endpoint"], "/get/soccer/ger.1/standings")

    def test_ligue1_suffix_child_label_is_supported(self):
        item = observation("fra.1", "Ligue 1 2026/27", "fra-")
        rows = build_standings_observation_rows(item)
        self.assertEqual(len(rows), 18)
        self.assertEqual(rows[0]["provenance"]["unique_child_label"], "Ligue 1 2026/27")

    def test_season_mismatch_is_rejected(self):
        item = observation("ger.1", "2026-27 German Bundesliga", "ger-")
        item["provider_returned_season"]["standings_season"] = 2025
        with self.assertRaises(ValueError):
            build_standings_observation_rows(item)

    def test_duplicate_team_ids_are_rejected(self):
        item = observation("fra.1", "Ligue 1 2026/27", "fra-")
        item["teams"][1]["id"] = item["teams"][0]["id"]
        with self.assertRaises(ValueError):
            build_standings_observation_rows(item)

    def test_incomplete_participant_evidence_is_not_staged(self):
        item = observation("ger.1", "2026-27 German Bundesliga", "ger-")
        item["team_evidence_method"] = "season_window_fixture_participants"
        self.assertEqual(build_standings_observation_rows(item), [])




    def test_raw_response_team_mismatch_is_rejected(self):
        item = observation("ger.1", "2026-27 German Bundesliga", "ger-")
        item["provider_payload"]["children"][0]["standings"]["entries"][0]["team"]["id"] = "other-id"
        with self.assertRaises(ValueError):
            build_standings_observation_rows(item)

    def test_staging_rejects_wrong_requested_season(self):
        item = observation("ger.1", "2026-27 German Bundesliga", "ger-")
        item["requested_season_parameter"] = 2025
        with self.assertRaises(ValueError):
            build_standings_observation_rows(item)

    def test_staging_rejects_unrecognized_child_label(self):
        item = observation("fra.1", "Ligue 1 2025/26", "fra-")
        with self.assertRaises(ValueError):
            build_standings_observation_rows(item)

    def test_collector_holds_ambiguous_matching_children(self):
        class FakeClient:
            def standings(self, slug, season):
                child = {
                    "id": "season-child",
                    "name": "Ligue 1 2026/27",
                    "standings": {
                        "season": 2026,
                        "entries": [{
                            "team": {"id": f"team-{i}", "name": f"Club {i}"}
                        } for i in range(18)],
                    },
                }
                return {"season": 2026, "children": [child, {**child, "id": "duplicate-child"}]}

        result = collect_livescore_season_standings(
            FakeClient(),
            league={"id": "fra.1", "name": "Ligue 1", "country": "France"},
            season_year=2026,
            retrieved_at="2026-11-16T12:00:00+00:00",
        )
        self.assertEqual(result["status"], "held_ambiguous_returned_season")
        self.assertFalse(result["team_evidence_complete"])
        self.assertEqual(result["teams"], [])
        self.assertEqual(result["provider_returned_season"]["matching_child_count"], 2)

if __name__ == "__main__":
    unittest.main()
