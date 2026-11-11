from pathlib import Path
import unittest


SHARED_REPORT_WORKFLOWS = (
    ".github/workflows/api-football-fixture-audit.yml",
    ".github/workflows/crosswalk-after-catalogue-sync.yml",
    ".github/workflows/sportmonks-catalogue-sync.yml",
    ".github/workflows/lab-controller.yml",
)


class ReportWorkflowQueueTests(unittest.TestCase):
    def test_shared_report_writers_use_a_non_cancelling_fifo_queue(self):
        root = Path(__file__).resolve().parent
        for relative_path in SHARED_REPORT_WORKFLOWS:
            with self.subTest(workflow=relative_path):
                source = (root / relative_path).read_text(encoding="utf-8")
                self.assertIn("group: main-report-archive", source)
                self.assertIn("queue: max", source)
                self.assertNotIn("cancel-in-progress: true", source)

    def test_upcoming_fixture_collection_has_an_independent_bounded_queue(self):
        root = Path(__file__).resolve().parent
        source = (root / ".github/workflows/upcoming-fixture-collection.yml").read_text(encoding="utf-8")
        self.assertIn("group: upcoming-fixture-collection", source)
        self.assertNotIn("group: main-report-archive", source)
        self.assertNotIn("queue: max", source)
        self.assertNotIn("cancel-in-progress: true", source)


if __name__ == "__main__":
    unittest.main()
