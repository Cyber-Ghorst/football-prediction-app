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

    def test_season_alignment_is_evidence_only_and_not_an_identity_approval(self):
        report = build_provider_independent_competition_catalogue(
            {
                "openfootball": [{"id": "en.1", "name": "Premier League", "country": "England"}],
                "openligadb": [{"id": "5996", "name": "Premier League", "country": "England"}],
            },
            {
                "openfootball": [{
                    "id": "en.1::2026-27", "name": "2026-27",
                    "provider_competition_id": "en.1",
                }],
                "openligadb": [{
                    "id": "5996::2026", "name": "2026",
                    "provider_competition_id": "5996",
                }],
            },
        )
        candidate = report["canonical_seed_review_candidates"][0]
        self.assertEqual(candidate["season_evidence"]["status"], "cross_provider_start_year_overlap")
        self.assertEqual(candidate["season_evidence"]["shared_start_years"], [2026])
        self.assertFalse(candidate["automatic_approval"])
        self.assertEqual(candidate["canonical_record_created"], False)

    def test_numeric_provider_season_id_is_not_mistaken_for_a_calendar_year(self):
        report = build_provider_independent_competition_catalogue(
            {
                "bzzoiro": [{"id": "98", "name": "Girabola", "country": "Angola"}],
            },
            {
                "bzzoiro": [{
                    "id": "98::2037", "name": "Girabola 26/27",
                    "provider_competition_id": "98",
                }],
            },
        )
        season = report["competitions"][0]["sources"][0]["seasons"][0]
        self.assertEqual(season["provider_season_id"], "98::2037")
        self.assertEqual(season["season_name"], "Girabola 26/27")
        self.assertEqual(season["start_years"], [])
        self.assertEqual(
            report["competitions"][0]["season_evidence"]["status"],
            "insufficient_provider_season_evidence",
        )

    def test_calendar_year_in_season_label_is_still_extracted(self):
        report = build_provider_independent_competition_catalogue(
            {
                "provider_a": [{"id": "1", "name": "Premier League", "country": "England"}],
            },
            {
                "provider_a": [{
                    "id": "1::opaque", "name": "2026-27",
                    "provider_competition_id": "1",
                }],
            },
        )
        season = report["competitions"][0]["sources"][0]["seasons"][0]
        self.assertEqual(season["start_years"], [2026])

    def test_competition_type_conflict_is_exposed_and_missing_type_stays_unknown(self):
        conflict = build_provider_independent_competition_catalogue({
            "provider_a": [{
                "id": "1", "name": "Premier League", "country": "England",
                "competition_type": "LEAGUE",
            }],
            "provider_b": [{
                "id": "2", "name": "Premier League", "country": "England",
                "competition_type": "CUP",
            }],
        })["competitions"][0]["competition_type_evidence"]
        unknown = build_provider_independent_competition_catalogue({
            "provider_a": [{"id": "1", "name": "Premier League", "country": "England"}],
            "provider_b": [{"id": "2", "name": "Premier League", "country": "England"}],
        })["competitions"][0]["competition_type_evidence"]
        self.assertEqual(conflict["status"], "provider_type_conflict")
        self.assertEqual(unknown["status"], "unknown_not_supplied")


if __name__ == "__main__":
    unittest.main()
