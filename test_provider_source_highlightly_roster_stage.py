import unittest

from provider_source_highlightly_roster_stage import (
    build_source_entities,
    _select_competition,
    TARGETS,
)


class HighlightlySourceRosterStageTests(unittest.TestCase):
    def test_targets_cover_five_domestic_top_flights_only(self):
        self.assertEqual(
            {(row["name"], row["country"]) for row in TARGETS},
            {
                ("Premier League", "England"),
                ("La Liga", "Spain"),
                ("Serie A", "Italy"),
                ("Bundesliga", "Germany"),
                ("Ligue 1", "France"),
            },
        )
    def test_builds_competition_scoped_season_ids_and_keeps_team_country_explicit(self):
        rows = build_source_entities([
            {
                "league": {
                    "id": 67162, "name": "Bundesliga",
                    "country": {"name": "Germany"}, "type": None,
                },
                "season": {"id": 2026, "name": "2026", "start_date": "2026-08-01"},
                "teams": [{
                    "id": 1, "name": "Bayern Munich", "country": None, "type": "domestic", "gender": "male",
                    "raw": {"id": 1, "name": "Bayern Munich"},
                }],
                "team_evidence_method": "league_season_standings",
                "team_evidence_complete": True,
            },
            {
                "league": {
                    "id": 52695, "name": "Ligue 1",
                    "country": {"name": "France"}, "type": None,
                },
                "season": {"id": 2026, "name": "2026"},
                "teams": [{
                    "id": 1, "name": "Bayern Munich", "country": None, "type": "domestic", "gender": "male",
                    "raw": {"id": 1, "name": "Bayern Munich"},
                }],
                "team_evidence_method": "league_season_standings",
                "team_evidence_complete": True,
            },
        ], retrieved_at="2026-11-16T13:00:00+00:00")
        seasons = [row for row in rows if row["entity_type"] == "season"]
        self.assertEqual(
            {row["provider_entity_id"] for row in seasons},
            {"67162:2026", "52695:2026"},
        )
        self.assertEqual(seasons[0]["raw_payload"]["provider_entity_id_kind"],
                         "competition_scoped_composite")
        teams = [row for row in rows if row["entity_type"] == "team"]
        self.assertEqual(len(teams), 1)
        self.assertIsNone(teams[0]["country"])
        self.assertEqual(teams[0]["team_type"], "domestic")
        self.assertEqual(teams[0]["gender_scope"], "male")
        self.assertFalse(teams[0]["raw_payload"]["team_evidence_complete"])
        self.assertEqual(teams[0]["raw_payload"]["season_label"], "2026")
        self.assertEqual(teams[0]["raw_payload"]["source_endpoint"], "standings")
        self.assertEqual(teams[0]["raw_payload"]["source_retrieved_at"], "2026-11-16T13:00:00+00:00")
        self.assertEqual(
            teams[0]["raw_payload"]["competition_provider_ids"],
            ["52695", "67162"],
        )

    def test_exact_competition_selection_rejects_country_mismatch_and_ambiguity(self):
        rows = [
            {"id": 1, "name": "Bundesliga", "country": {"name": "Germany"}},
            {"id": 2, "name": "Bundesliga", "country": {"name": "Austria"}},
        ]
        selected, status = _select_competition(
            rows, {"name": "Bundesliga", "country": "Germany"},
        )
        self.assertEqual(status, "unique_exact_name_country")
        self.assertEqual(selected["id"], 1)
        selected, status = _select_competition(
            rows + [{"id": 3, "name": "Bundesliga", "country": {"name": "Germany"}}],
            {"name": "Bundesliga", "country": "Germany"},
        )
        self.assertIsNone(selected)
        self.assertEqual(status, "ambiguous_exact_name_country")


if __name__ == "__main__":
    unittest.main()
