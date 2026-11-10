import unittest

from learning_experiments import run_offline_experiments


class LearningExperimentTests(unittest.TestCase):
    def _dataset(self, count=30):
        rows = []
        for index in range(count):
            split = "train" if index < 21 else "validation" if index < 26 else "test"
            outcome = ("home", "draw", "away")[index % 3]
            rows.append({
                "record_id": f"record-{index}",
                "split": split,
                "target": {"outcome": outcome},
                "baseline_probabilities": {
                    "home_win": 60.0, "draw": 25.0, "away_win": 15.0,
                },
            })
        return {"dataset_schema_version": "football-learning-dataset-v1", "rows": rows}

    def test_insufficient_sample_blocks_all_comparisons(self):
        report = run_offline_experiments(self._dataset(12))
        self.assertEqual(report["status"], "blocked_insufficient_sample")
        self.assertFalse(report["sample_gate"]["passed"])
        self.assertIsNone(report["results"]["validation"]["incumbent"])
        self.assertFalse(report["method"]["production_promotion_permitted"])

    def test_scores_incumbent_and_train_only_prior_on_holdouts(self):
        report = run_offline_experiments(self._dataset())
        self.assertEqual(report["status"], "ready_for_offline_comparison")
        self.assertEqual(report["sample_gate"]["valid_targets_by_split"], {
            "train": 21, "validation": 5, "test": 4,
        })
        self.assertEqual(report["results"]["validation"]["incumbent"]["matches"], 5)
        self.assertEqual(report["results"]["test"]["candidate"]["matches"], 4)
        self.assertEqual(report["candidate_training_prior_pct"], {
            "home_win": 33.333333, "draw": 33.333333, "away_win": 33.333333,
        })
        self.assertFalse(report["method"]["production_promotion_permitted"])

    def test_validation_and_test_targets_do_not_change_candidate_fit(self):
        dataset = self._dataset()
        first = run_offline_experiments(dataset)
        for row in dataset["rows"]:
            if row["split"] in {"validation", "test"}:
                row["target"]["outcome"] = "home"
        second = run_offline_experiments(dataset)
        self.assertEqual(
            first["candidate_training_prior_pct"],
            second["candidate_training_prior_pct"],
        )

    def test_candidate_is_fitted_from_training_partition_only(self):
        dataset = self._dataset()
        for row in dataset["rows"]:
            if row["split"] == "train":
                row["target"]["outcome"] = "home"
            else:
                row["target"]["outcome"] = "away"
        report = run_offline_experiments(dataset)
        prior = report["candidate_training_prior_pct"]
        self.assertGreater(prior["home_win"], prior["draw"])
        self.assertGreater(prior["home_win"], prior["away_win"])

    def test_invalid_probabilities_are_not_scored(self):
        dataset = self._dataset()
        dataset["rows"][21]["baseline_probabilities"] = {
            "home_win": 80, "draw": 80, "away_win": 0,
        }
        report = run_offline_experiments(dataset)
        self.assertEqual(report["results"]["validation"]["incumbent"]["matches"], 4)
        self.assertEqual(report["results"]["validation"]["candidate"]["matches"], 5)

    def test_invalid_gate_and_dataset_shape_raise(self):
        with self.assertRaises(ValueError):
            run_offline_experiments(self._dataset(), minimum_fixtures=0)
        with self.assertRaises(ValueError):
            run_offline_experiments({"rows": "not-a-list"})


if __name__ == "__main__":
    unittest.main()
