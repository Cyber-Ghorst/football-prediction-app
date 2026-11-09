import unittest

from statistics_coverage import build_statistics_coverage


class StatisticsCoverageTests(unittest.TestCase):
    def test_reports_partial_and_complete_core_metric_coverage(self):
        matches = [
            {
                "fixture_id": 101,
                "statistics": {
                    "Ball Possession": 61,
                    "Passes %": 84,
                    "Total Shots": 14,
                    "Shots on Target": 5,
                    "Tackles": 13,
                    "Interceptions": 8,
                    "Blocked Shots": 3,
                    "Corner Kicks": 6,
                    "Big Chances Created": 4,
                },
                "opponent_statistics": {"Big Chances Created": 2},
                "statistics_raw_diagnostics": [
                    {"statistic_name_raw": "Shots Accuracy", "mapping_status": "unmapped"},
                    {"statistic_name_raw": "Ball Possession %", "canonical_name": "Ball Possession", "mapping_status": "mapped"},
                ],
            },
            {
                "fixture_id": 102,
                "statistics": {
                    "Ball Possession": 54,
                    "Total Shots": 9,
                    "Shots on Goal": 3,
                    "Tackles": 16,
                    "Interceptions": 6,
                    "Corner Kicks": 4,
                },
                "statistics_raw_diagnostics": [
                    {"statistic_name_raw": "Shots Accuracy", "mapping_status": "unmapped"},
                ],
            },
        ]
        report = build_statistics_coverage(matches)
        by_name = {row["statistic"]: row for row in report["metrics"]}

        self.assertEqual(report["fixtures_checked"], 2)
        self.assertEqual(report["core_metrics_with_any_data"], 8)
        self.assertEqual(report["core_metrics_complete"], 6)
        self.assertEqual(by_name["Ball Possession"]["coverage_pct"], 100.0)
        self.assertEqual(by_name["Passes %"]["coverage_pct"], 50.0)
        self.assertEqual(by_name["Shots on Target / Goal"]["fixtures_available"], 2)
        self.assertEqual(by_name["Blocked Shots"]["status"], "partial")
        self.assertEqual(report["unmapped_observations"], 2)
        self.assertEqual(report["unmapped_statistics"][0]["provider_statistic"], "Shots Accuracy")
        self.assertEqual(report["unmapped_statistics"][0]["fixtures_seen"], 2)
        self.assertEqual(report["mapping_visibility"], "available")
        big_chance_coverage = next(row for row in report["tactical_evidence_metrics"] if row["statistic"] == "Big Chances Created")
        self.assertEqual(big_chance_coverage["team_output_fixtures"], 1)
        self.assertEqual(big_chance_coverage["opponent_output_fixtures"], 1)

    def test_missing_statistics_remain_missing_and_do_not_become_zero(self):
        report = build_statistics_coverage([{"fixture_id": 1, "statistics": {}}])
        self.assertEqual(report["core_metrics_with_any_data"], 0)
        self.assertEqual(report["core_metrics_complete"], 0)
        self.assertTrue(all(row["status"] == "missing" for row in report["metrics"]))
        self.assertTrue(all(row["coverage_pct"] == 0.0 for row in report["metrics"]))
        self.assertEqual(report["mapping_visibility"], "not supplied by this data path")

    def test_only_ten_most_recent_matches_are_counted(self):
        matches = [
            {"fixture_id": i, "statistics": {"Ball Possession": 50}}
            for i in range(12)
        ]
        report = build_statistics_coverage(matches)
        self.assertEqual(report["fixtures_checked"], 10)
        self.assertEqual(
            next(row for row in report["metrics"] if row["statistic"] == "Ball Possession")["fixtures_available"],
            10,
        )


if __name__ == "__main__":
    unittest.main()
