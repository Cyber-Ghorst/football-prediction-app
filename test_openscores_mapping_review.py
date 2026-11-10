import unittest

from openscores_mapping_review import exact_name_candidates


class OpenScoresMappingReviewTests(unittest.TestCase):
    def test_unique_exact_name_is_candidate_only(self):
        rows = exact_name_candidates(
            [{"id": "os-1", "name": "Arsenal"}],
            [{"id": "sportmonks:1", "name": "Arsenal"}],
        )
        self.assertEqual(rows[0]["candidate_status"], "no_exact_candidate")
        self.assertEqual(rows[0]["candidates"][0]["canonical_entity_id"], "sportmonks:1")
        self.assertFalse(rows[0]["auto_linked"])

    def test_ambiguous_exact_names_are_not_selected(self):
        rows = exact_name_candidates(
            [{"id": "os-1", "name": "United"}],
            [
                {"id": "sportmonks:1", "name": "United"},
                {"id": "sportmonks:2", "name": "United"},
            ],
        )
        self.assertEqual(rows[0]["candidate_status"], "ambiguous_exact_candidates")
        self.assertEqual(rows[0]["candidate_count"], 2)
        self.assertFalse(rows[0]["auto_linked"])

    def test_case_and_whitespace_are_normalized_but_words_and_punctuation_are_not(self):
        rows = exact_name_candidates(
            [{"id": "os-1", "name": "  ARSENAL   FC "}],
            [
                {"id": "a", "name": "Arsenal FC"},
                {"id": "b", "name": "Arsenal"},
            ],
        )
        self.assertEqual(rows[0]["candidate_count"], 1)
        self.assertEqual(rows[0]["candidates"][0]["canonical_entity_id"], "a")

    def test_country_mismatch_blocks_candidate(self):
        rows = exact_name_candidates(
            [{"id": "os-1", "name": "Premier League", "country": "England"}],
            [{"id": "sportmonks:1", "name": "Premier League", "country": "Scotland"}],
            require_country=True,
        )
        self.assertEqual(rows[0]["candidate_status"], "no_exact_candidate")

    def test_unknown_provider_country_does_not_auto_satisfy_required_country(self):
        rows = exact_name_candidates(
            [{"id": "os-1", "name": "Premier League", "country": ""}],
            [{"id": "sportmonks:1", "name": "Premier League", "country": "England"}],
            require_country=True,
        )
        self.assertEqual(rows[0]["candidate_status"], "unique_exact_candidate")


if __name__ == "__main__":
    unittest.main()
