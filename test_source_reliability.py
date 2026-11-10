import unittest

from source_reliability import build_source_reliability_report


def _record(home_primary=2, away_primary=1, home_secondary=2, away_secondary=1,
            status_primary="finished", status_secondary="finished",
            kickoff_primary="2026-11-01T15:00:00Z",
            kickoff_secondary="2026-11-01T15:02:00Z"):
    def observations(primary, secondary):
        return [
            {"provider": "sportmonks", "value": primary},
            {"provider": "highlightly", "value": secondary},
        ]
    return {
        "reconciliation": {
            "home_score": {"observations": observations(home_primary, home_secondary)},
            "away_score": {"observations": observations(away_primary, away_secondary)},
            "status": {"observations": observations(status_primary, status_secondary)},
            "kickoff_utc": {"observations": observations(kickoff_primary, kickoff_secondary)},
        }
    }


class SourceReliabilityTests(unittest.TestCase):
    def test_exact_score_pair_agreement_and_separate_status_kickoff_metrics(self):
        report = build_source_reliability_report(
            {"matches": [_record()]}, minimum_score_samples=1
        )
        row = report["providers"]["highlightly"]
        self.assertEqual(row["score_pairs"], {"compared": 1, "agreed": 1, "disagreed": 0})
        self.assertEqual(row["score_pair_agreement_pct"], 100.0)
        self.assertEqual(row["status"]["agreed"], 1)
        self.assertEqual(row["kickoff_within_5_minutes"]["agreed"], 1)
        self.assertEqual(row["score_reliability_status"], "sample_sufficient_descriptive_only")

    def test_score_mismatch_is_counted_as_one_fixture_pair_not_two_fields(self):
        report = build_source_reliability_report(
            {"matches": [_record(home_secondary=3)]}, minimum_score_samples=1
        )
        row = report["providers"]["highlightly"]
        self.assertEqual(row["score_pairs"], {"compared": 1, "agreed": 0, "disagreed": 1})
        self.assertEqual(row["score_pair_agreement_pct"], 0.0)

    def test_incomplete_or_invalid_scores_do_not_enter_score_sample(self):
        report = build_source_reliability_report(
            {"matches": [_record(home_secondary=True), _record(away_secondary=None)]},
            minimum_score_samples=1,
        )
        row = report["providers"]["highlightly"]
        self.assertEqual(row["score_pairs"]["compared"], 0)
        self.assertIsNone(row["score_pair_agreement_pct"])
        self.assertEqual(row["score_reliability_status"], "insufficient_sample")

    def test_small_samples_are_never_reported_as_reliable(self):
        report = build_source_reliability_report(
            {"matches": [_record() for _ in range(29)]}, minimum_score_samples=30
        )
        row = report["providers"]["highlightly"]
        self.assertEqual(row["score_pairs"]["compared"], 29)
        self.assertEqual(row["score_reliability_status"], "insufficient_sample")
        self.assertFalse(row["eligible_for_provider_priority_changes"])

    def test_conflicting_status_and_kickoff_are_visible(self):
        report = build_source_reliability_report(
            {"matches": [_record(status_secondary="live",
                                 kickoff_secondary="2026-11-01T15:20:00Z")]},
            minimum_score_samples=1,
        )
        row = report["providers"]["highlightly"]
        self.assertEqual(row["status"]["disagreed"], 1)
        self.assertEqual(row["kickoff_within_5_minutes"]["disagreed"], 1)

    def test_provider_missing_observations_is_not_counted_as_disagreement(self):
        row = _record()
        row["reconciliation"]["home_score"]["observations"] = [
            {"provider": "sportmonks", "value": 2}
        ]
        row["reconciliation"]["away_score"]["observations"] = [
            {"provider": "sportmonks", "value": 1}
        ]
        report = build_source_reliability_report({"matches": [row]})
        self.assertEqual(report["providers"]["highlightly"]["score_pairs"]["compared"], 0)

    def test_duplicate_provider_observations_are_excluded(self):
        row = _record()
        row["reconciliation"]["home_score"]["observations"].append(
            {"provider": "highlightly", "value": 99}
        )
        report = build_source_reliability_report({"matches": [row]}, minimum_score_samples=1)
        self.assertEqual(report["providers"]["highlightly"]["score_pairs"]["compared"], 0)

    def test_report_never_changes_prediction_or_provider_priority(self):
        report = build_source_reliability_report({"matches": [_record()]})
        self.assertFalse(report["prediction_inputs_modified"])
        self.assertFalse(report["provider_priority_modified"])
        self.assertFalse(
            report["providers"]["highlightly"]["eligible_for_provider_priority_changes"]
        )

    def test_invalid_minimum_sample_setting_is_rejected(self):
        for value in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                build_source_reliability_report({}, minimum_score_samples=value)


if __name__ == "__main__":
    unittest.main()
