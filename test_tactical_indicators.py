import unittest

from tactical_indicators import analyze_tactics


def match(possession=None, **statistics):
    stats = dict(statistics)
    if possession is not None:
        stats["Ball Possession"] = possession
    return {"statistics": stats}


class TacticalRecencyWeightingTests(unittest.TestCase):
    def test_latest_five_have_sixty_percent_and_previous_five_forty_percent(self):
        matches = [match(70) for _ in range(5)] + [match(30) for _ in range(5)]
        result = analyze_tactics(matches)
        self.assertEqual(result["available_metrics"]["average_possession"], 54.0)
        self.assertEqual(result["recency_weighting"]["recent_weight"], 0.60)
        self.assertEqual(result["recency_weighting"]["previous_weight"], 0.40)

    def test_only_available_window_is_renormalized_when_other_window_is_missing(self):
        matches = [match(70) for _ in range(5)] + [match() for _ in range(5)]
        result = analyze_tactics(matches)
        self.assertEqual(result["available_metrics"]["average_possession"], 70.0)

    def test_missing_metric_remains_unknown(self):
        result = analyze_tactics([match() for _ in range(10)])
        self.assertIsNone(result["available_metrics"]["average_possession"])
        self.assertIsNone(result["playing_style"])
        self.assertEqual(result["coverage_metrics"], 0)

    def test_only_latest_ten_matches_are_used(self):
        matches = [match(70) for _ in range(5)] + [match(30) for _ in range(5)] + [match(0) for _ in range(3)]
        result = analyze_tactics(matches)
        self.assertEqual(result["recency_weighting"]["matches_used"], 10)
        self.assertEqual(result["available_metrics"]["average_possession"], 54.0)


if __name__ == "__main__":
    unittest.main()
