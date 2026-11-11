"""Catch missing names in the Streamlit application's startup import contract."""
import unittest


class StreamlitStartupImportContractTests(unittest.TestCase):
    def test_deployment_build_marker_is_present_for_live_revision_verification(self):
        from pathlib import Path

        source = Path(__file__).with_name("app.py").read_text(encoding="utf-8")
        self.assertIn("Deployment build: startup-import compatibility 2026-11-11", source)

    def test_optional_fixture_promotion_writer_is_imported_lazily(self):
        from pathlib import Path

        source = Path(__file__).with_name("app.py").read_text(encoding="utf-8")
        self.assertIn(
            "from temporary_fixture_store import search_temporary_upcoming_fixtures",
            source,
        )
        self.assertNotIn(
            "from temporary_fixture_store import (\\n        add_temporary_upcoming_fixtures",
            source,
        )
        self.assertIn(
            "from temporary_fixture_store import add_temporary_upcoming_fixtures",
            source,
        )

    def test_optional_crosswalk_review_module_is_imported_only_on_demand(self):
        from pathlib import Path

        source = Path(__file__).with_name("app.py").read_text(encoding="utf-8")
        self.assertNotIn(
            "\\n    from provider_crosswalk_review_report import build_provider_crosswalk_review_report",
            source,
        )
        self.assertIn(
            "                from provider_crosswalk_review_report import build_provider_crosswalk_review_report",
            source,
        )

    def test_new_provider_and_fixture_workflow_imports_resolve(self):
        from temporary_fixture_store import (
            add_temporary_upcoming_fixtures,
            search_temporary_upcoming_fixtures,
        )
        from free_fixture_adapters import BzzoiroAdapter
        from free_fixture_observation_pipeline import (
            collect_openligadb_observations,
            collect_openfootball_observations,
            collect_openmatchday_observations,
            collect_livescore_observations,
            collect_bzzoiro_observations,
        )
        from provider_entity_crosswalk import save_explicit_provider_entity_links
        from provider_crosswalk_review_report import build_provider_crosswalk_review_report
        from free_fixture_result_sync import sync_free_source_results
        from free_fixture_canonical_promotion import review_and_promote_free_fixture_observations
        from livescore_football import LiveScoreFootballClient, LiveScoreFootballError

        imported = (
            add_temporary_upcoming_fixtures,
            search_temporary_upcoming_fixtures,
            BzzoiroAdapter,
            collect_openligadb_observations,
            collect_openfootball_observations,
            collect_openmatchday_observations,
            collect_livescore_observations,
            collect_bzzoiro_observations,
            save_explicit_provider_entity_links,
            build_provider_crosswalk_review_report,
            sync_free_source_results,
            review_and_promote_free_fixture_observations,
            LiveScoreFootballClient,
            LiveScoreFootballError,
        )
        self.assertTrue(all(item is not None for item in imported))


if __name__ == "__main__":
    unittest.main()
