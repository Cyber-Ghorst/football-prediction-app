import unittest

from deployment_smoke_check import has_eager_crosswalk_review_import


class AppImportSafetyTests(unittest.TestCase):
    def test_crosswalk_review_import_inside_startup_try_is_rejected(self):
        source = """
try:
    from provider_crosswalk_review_report import build_provider_crosswalk_review_report
except Exception:
    pass
"""
        self.assertTrue(has_eager_crosswalk_review_import(source))

    def test_direct_module_level_import_is_rejected(self):
        source = "from provider_crosswalk_review_report import build_provider_crosswalk_review_report"
        self.assertTrue(has_eager_crosswalk_review_import(source))

    def test_conditional_ui_import_is_not_classified_as_startup_import(self):
        source = """
if user_clicked_review:
    from provider_crosswalk_review_report import build_provider_crosswalk_review_report
"""
        self.assertFalse(has_eager_crosswalk_review_import(source))

    def test_function_local_import_is_not_classified_as_startup_import(self):
        source = """
def render_review():
    from provider_crosswalk_review_report import build_provider_crosswalk_review_report
"""
        self.assertFalse(has_eager_crosswalk_review_import(source))


if __name__ == "__main__":
    unittest.main()
