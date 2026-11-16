import unittest

from provider_season_roster_audit import build_roster_identity_candidates


def roster(name, provider_id, method="league_season_standings"):
    return {
        "target": {"name": name, "country": "Germany" if "Bundesliga" in name else "France"},
        "status": "collected",
        "league_id": 67162 if name == "Bundesliga" else 52695 if name == "Ligue 1" else "ger.1",
        "season": 2026,
        "team_evidence_method": method,
        "team_evidence_complete": method == "season_standings",
        "teams": [{"id": provider_id, "name": "Bayern Munchen"}],
    }


class ProviderRosterIdentityCandidateTests(unittest.TestCase):
    def test_exact_normalized_name_is_candidate_not_verified_link(self):
        highlightly = {"competitions": [roster("Bundesliga", "134391")]}
        livescore = {"competitions": [roster("German Bundesliga", "132", "season_standings")]}
        result = build_roster_identity_candidates(highlightly, livescore)
        candidate = result["comparisons"][0]["candidates"][0]
        self.assertEqual(candidate["highlightly"]["team_id"], "134391")
        self.assertEqual(candidate["livescore_football"]["team_id"], "132")
        self.assertFalse(candidate["verified"])
        self.assertFalse(candidate["link_written"])
        self.assertEqual(result["verified_links_created"], 0)

    def test_duplicate_normalized_names_are_held_as_ambiguous(self):
        h = roster("Bundesliga", "134391")
        h["teams"].append({"id": "999", "name": "Bayern Munchen"})
        l = roster("German Bundesliga", "132", "season_standings")
        result = build_roster_identity_candidates(
            {"competitions": [h]}, {"competitions": [l]},
        )
        self.assertEqual(result["comparisons"][0]["candidate_count"], 0)
        self.assertEqual(result["comparisons"][0]["ambiguous_count"], 1)

    def test_missing_provider_roster_is_held(self):
        result = build_roster_identity_candidates(
            {"competitions": []}, {"competitions": []},
        )
        self.assertEqual(result["comparisons"][0]["status"], "held_missing_or_ambiguous_roster")
        self.assertEqual(result["candidates_total"], 0)


if __name__ == "__main__":
    unittest.main()
