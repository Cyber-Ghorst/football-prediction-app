import unittest

from provider_independent_competition_catalogue import (
    build_provider_independent_competition_catalogue,
)


class ProviderIndependentCompetitionCatalogueTests(unittest.TestCase):
    def test_exact_name_and_country_consensus_is_reported_without_mapping(self):
        report = build_provider_independent_competition_catalogue({
            "bzzoiro": [{
                "id": "14", "name": "Premier League", "country": "England",
                "observation_count": 22,
            }],
            "livescore_football": [{
                "id": "eng-premier", "name": "Premier League", "country": "England",
                "observation_count": 8,
            }],
        })
        self.assertEqual(report["competition_count"], 1)
        self.assertEqual(report["corroborated_competition_count"], 1)
        item = report["competitions"][0]
        self.assertEqual(item["status"], "corroborated_multi_provider")
        self.assertEqual(item["providers"], ["bzzoiro", "livescore_football"])
        self.assertFalse(item["canonical_mapping_created"])
        self.assertEqual(report["canonical_rows_created"], 0)
        self.assertEqual(report["provider_links_created"], 0)
        self.assertEqual(report["automatic_mapping_approvals"], 0)

    def test_country_aliases_are_normalized_for_corroboration(self):
        report = build_provider_independent_competition_catalogue({
            "openligadb": [{"id": "bl1", "name": "Bundesliga", "country": "Deutschland"}],
            "bzzoiro": [{"id": "5", "name": "Bundesliga", "country": "Germany"}],
        })
        self.assertEqual(report["corroborated_competition_count"], 1)
        self.assertEqual(report["competitions"][0]["normalized_country"], "germany")

    def test_different_country_never_corroborates_same_competition_name(self):
        report = build_provider_independent_competition_catalogue({
            "provider_a": [{"id": "1", "name": "Premier League", "country": "England"}],
            "provider_b": [{"id": "2", "name": "Premier League", "country": "Kenya"}],
        })
        self.assertEqual(report["competition_count"], 2)
        self.assertEqual(report["corroborated_competition_count"], 0)
        self.assertEqual(report["single_provider_competition_count"], 2)

    def test_missing_country_is_retained_but_never_corroborated(self):
        report = build_provider_independent_competition_catalogue({
            "openligadb": [{"id": "1", "name": "Eredivisie"}],
            "bzzoiro": [{"id": "2", "name": "Eredivisie"}],
        })
        self.assertEqual(report["competition_count"], 0)
        self.assertEqual(report["country_unscoped_source_count"], 2)
        self.assertEqual(len(report["country_unscoped_sources"]), 2)

    def test_only_multi_provider_exact_consensus_enters_manual_seed_review(self):
        report = build_provider_independent_competition_catalogue({
            "openfootball": [
                {"id": "en.1", "name": "Premier League", "country": "England"},
                {"id": "de.1", "name": "Bundesliga", "country": "Germany"},
            ],
            "openligadb": [
                {"id": "5996", "name": "Premier League", "country": "England"},
                {"id": "4937", "name": "Bundesliga", "country": "Germany"},
            ],
            "bzzoiro": [
                {"id": "91", "name": "National League", "country": "England"},
            ],
        })
        candidates = report["canonical_seed_review_candidates"]
        self.assertEqual(report["canonical_seed_review_candidate_count"], 2)
        self.assertEqual(
            {row["competition_name"] for row in candidates},
            {"Premier League", "Bundesliga"},
        )
        for candidate in candidates:
            self.assertEqual(candidate["status"], "eligible_for_manual_canonical_seed_review")
            self.assertFalse(candidate["canonical_record_created"])
            self.assertFalse(candidate["provider_links_created"])
            self.assertFalse(candidate["automatic_approval"])
            self.assertEqual(candidate["provider_count"], 2)

    def test_duplicate_entities_from_one_provider_do_not_fake_consensus(self):
        report = build_provider_independent_competition_catalogue({
            "bzzoiro": [
                {"id": "14", "name": "Premier League", "country": "England"},
                {"id": "14", "name": "Premier League", "country": "England"},
            ],
        })
        self.assertEqual(report["competition_count"], 1)
        self.assertEqual(report["competitions"][0]["provider_count"], 1)
        self.assertEqual(report["competitions"][0]["status"], "single_provider_only")
        self.assertEqual(len(report["competitions"][0]["sources"]), 2)


if __name__ == "__main__":
    unittest.main()
