import unittest

from provider_source_api_ninjas_season_standings_stage import (
    build_source_entities,
    validate_standings_rows,
)


def standing(*, league="epl", season=2026, label="2026-27",
             team_id="soccer-arsenal", name="Arsenal"):
    return {
        "league": league,
        "sport": "soccer",
        "season": season,
        "season_label": label,
        "team": {
            "team_id": team_id,
            "name": name,
            "abbreviation": "ARS",
        },
        "games_played": 10,
        "points": 20,
    }


class APINinjasSeasonStandingsEvidenceTests(unittest.TestCase):
    def test_exact_provider_season_label_is_accepted(self):
        teams, held = validate_standings_rows(
            [standing()], requested_league="epl",
            retrieved_at="2026-11-16T12:00:00+00:00",
        )
        self.assertEqual(len(teams), 1)
        self.assertEqual(held, [])
        self.assertEqual(
            teams[0]["raw_payload"]["provider_returned_season_label"],
            "2026-27",
        )
        self.assertFalse(teams[0]["raw_payload"]["promotion_allowed"])

    def test_slash_season_label_is_accepted(self):
        teams, held = validate_standings_rows(
            [standing(label="2026/27")], requested_league="epl",
            retrieved_at="2026-11-16T12:00:00+00:00",
        )
        self.assertEqual(len(teams), 1)
        self.assertEqual(held, [])

    def test_missing_or_mismatched_season_fields_are_held(self):
        rows = [
            standing(season=None),
            standing(label="2025-26", team_id="soccer-chelsea", name="Chelsea"),
            standing(season=2025, team_id="soccer-liverpool", name="Liverpool"),
        ]
        teams, held = validate_standings_rows(
            rows, requested_league="epl",
            retrieved_at="2026-11-16T12:00:00+00:00",
        )
        self.assertEqual(teams, [])
        self.assertEqual(len(held), 3)

    def test_wrong_competition_is_held(self):
        teams, held = validate_standings_rows(
            [standing(league="laliga")], requested_league="epl",
            retrieved_at="2026-11-16T12:00:00+00:00",
        )
        self.assertEqual(teams, [])
        self.assertIn(
            "provider_league_missing_or_mismatched",
            held[0]["reasons"],
        )

    def test_missing_team_identity_is_held(self):
        row = standing()
        row["team"] = {"name": "Arsenal"}
        teams, held = validate_standings_rows(
            [row], requested_league="epl",
            retrieved_at="2026-11-16T12:00:00+00:00",
        )
        self.assertEqual(teams, [])
        self.assertIn("provider_team_id_missing", held[0]["reasons"])

    def test_conflicting_duplicate_team_id_is_held(self):
        rows = [
            standing(),
            standing(name="Arsenal FC"),
        ]
        teams, held = validate_standings_rows(
            rows, requested_league="epl",
            retrieved_at="2026-11-16T12:00:00+00:00",
        )
        self.assertEqual(teams, [])
        self.assertEqual(
            held[0]["reason"],
            "conflicting_duplicate_team_id_within_competition",
        )

    def test_same_team_id_isolated_between_competitions(self):
        entities, held = build_source_entities(
            [
                ("epl", [standing(league="epl")]),
                ("laliga", [standing(
                    league="laliga", team_id="soccer-arsenal",
                    name="Arsenal",
                )]),
            ],
            retrieved_at="2026-11-16T12:00:00+00:00",
        )
        self.assertEqual(held, [])
        team_rows = [row for row in entities if row["entity_type"] == "team"]
        self.assertEqual(len(team_rows), 2)
        self.assertEqual(
            {row["raw_payload"]["competition_provider_id"] for row in team_rows},
            {"epl", "laliga"},
        )
        self.assertEqual(
            {row["provider_entity_id"] for row in team_rows},
            {"epl:soccer-arsenal", "laliga:soccer-arsenal"},
        )
        self.assertEqual(
            {row["raw_payload"]["provider_team_id"] for row in team_rows},
            {"soccer-arsenal"},
        )

    def test_unverified_season_does_not_create_season_entity(self):
        entities, held = build_source_entities(
            [("epl", [standing(label="2025-26")])],
            retrieved_at="2026-11-16T12:00:00+00:00",
        )
        self.assertEqual(held[0]["reasons"], [
            "provider_season_label_missing_or_mismatched"
        ])
        self.assertFalse(any(row["entity_type"] == "season" for row in entities))

    def test_empty_response_does_not_create_season_entity(self):
        entities, held = build_source_entities(
            [("epl", [])],
            retrieved_at="2026-11-16T12:00:00+00:00",
        )
        self.assertEqual(entities, [])
        self.assertEqual(held, [])


if __name__ == "__main__":
    unittest.main()
