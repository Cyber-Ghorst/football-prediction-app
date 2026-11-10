import json
import tempfile
import unittest
from pathlib import Path

from learning_dataset import build_learning_dataset, export_learning_dataset


class LearningDatasetTests(unittest.TestCase):
    def _record(self, index=1, *, kickoff=None, predicted=None, score=(2, 1),
                fixture_id=None, record_id=None, snapshot_at=None):
        kickoff = kickoff or f"2026-11-{index:02d}T12:00:00+00:00"
        predicted = predicted or f"2026-11-{index:02d}T10:00:00+00:00"
        snapshot_at = snapshot_at or predicted
        fixture_id = fixture_id or f"fixture-{index}"
        snapshot = {
            "schema_version": "prediction-features-v1",
            "captured_at": snapshot_at,
            "recency_policy": "latest_5_60pct_previous_5_40pct",
            "teams": {
                "home": {"team_name": f"Home {index}", "recent_matches": [
                    {"goals_for": 2, "goals_against": 1, "opponent_strength": None}
                ]},
                "away": {"team_name": f"Away {index}", "recent_matches": []},
            },
            "calculated": {
                "home_rating": 70.0,
                "away_rating": 60.0,
                "component_ratings": {"home": {"form": 75.0}},
                "model_weights": {"recent_form": 0.2},
                "probabilities": {"home_win": 60, "draw": 25, "away_win": 15},
            },
        }
        return {
            "record_id": record_id or f"record-{index}",
            "fixture_provider": "sportmonks",
            "fixture_id": fixture_id,
            "predicted_at": predicted,
            "kickoff_at": kickoff,
            "competition": "Test League",
            "country": "Testland",
            "season": "2026",
            "home_team": f"Home {index}",
            "away_team": f"Away {index}",
            "feature_snapshot_json": json.dumps(snapshot),
            "actual_home_goals": str(score[0]),
            "actual_away_goals": str(score[1]),
            "actual_result_provider": "sportmonks",
            "actual_result_fixture_id": fixture_id,
            "actual_result_verified_at": "2026-11-30T18:00:00+00:00",
            "actual_result_verification": "exact_fixture_team_competition_season_and_score",
        }

    def test_only_verified_pre_kickoff_snapshots_are_exported(self):
        valid = self._record()
        manual = self._record(2)
        manual["actual_result_verification"] = "manual"
        late = self._record(3, predicted="2026-11-03T13:00:00+00:00")
        late["kickoff_at"] = "2026-11-03T12:00:00+00:00"
        missing = self._record(4)
        missing["feature_snapshot_json"] = ""
        dataset = build_learning_dataset([valid, manual, late, missing])
        self.assertEqual(dataset["audit"]["unique_verified_fixtures"], 1)
        self.assertEqual(len(dataset["rows"]), 1)
        self.assertEqual(dataset["rows"][0]["target"]["outcome"], "home")
        self.assertFalse(dataset["sample_gate"]["offline_experiment_allowed"])
        self.assertFalse(dataset["sample_gate"]["production_promotion_permitted"])

    def test_snapshot_must_be_at_or_before_prediction_and_before_kickoff(self):
        row = self._record(snapshot_at="2026-11-07T10:01:00+00:00")
        dataset = build_learning_dataset([row])
        self.assertEqual(dataset["audit"]["unique_verified_fixtures"], 0)
        self.assertIn(
            "snapshot_not_strictly_pre_kickoff",
            dataset["audit"]["excluded_reasons"],
        )

    def test_latest_valid_forecast_is_selected_once_per_fixture(self):
        kickoff = "2026-11-07T12:00:00+00:00"
        older = self._record(kickoff=kickoff, predicted="2026-11-07T09:00:00+00:00", record_id="older")
        newer = self._record(kickoff=kickoff, predicted="2026-11-07T10:00:00+00:00", record_id="newer")
        dataset = build_learning_dataset([newer, older])
        self.assertEqual(dataset["audit"]["eligible_records_before_deduplication"], 2)
        self.assertEqual(dataset["audit"]["duplicate_fixture_records_excluded"], 1)
        self.assertEqual(dataset["rows"][0]["record_id"], "newer")

    def test_conflicting_verified_scores_exclude_fixture(self):
        first = self._record(record_id="first", score=(1, 0))
        second = self._record(record_id="second", score=(0, 1))
        dataset = build_learning_dataset([first, second])
        self.assertEqual(dataset["audit"]["conflicting_verified_fixtures_excluded"], 1)
        self.assertEqual(dataset["rows"], [])

    def test_outcome_data_never_enters_feature_vector(self):
        dataset = build_learning_dataset([self._record()])
        row = dataset["rows"][0]
        self.assertNotIn("actual_home_goals", row["features"])
        self.assertNotIn("actual_away_goals", row["features"])
        self.assertNotIn("probabilities", row["features"]["calculated"])
        self.assertEqual(row["baseline_probabilities"]["home_win"], 60.0)
        self.assertEqual(row["target"]["home_goals"], 2)

    def test_chronological_splits_have_no_fixture_overlap(self):
        records = [self._record(index=i) for i in range(1, 21)]
        dataset = build_learning_dataset(records)
        rows = dataset["rows"]
        self.assertEqual([row["kickoff_at"] for row in rows], sorted(row["kickoff_at"] for row in rows))
        split = dataset["split_fixture_identities"]
        self.assertEqual(len(set(split["train"]) & set(split["validation"])), 0)
        self.assertEqual(len(set(split["validation"]) & set(split["test"])), 0)
        self.assertEqual(len(split["train"]) + len(split["validation"]) + len(split["test"]), 20)
        self.assertEqual([row["split"] for row in rows[:14]], ["train"] * 14)
        self.assertEqual(dataset["sample_gate"]["status"], "insufficient_sample")

    def test_missing_or_unsupported_feature_schema_is_rejected(self):
        row = self._record()
        snapshot = json.loads(row["feature_snapshot_json"])
        snapshot["schema_version"] = "future-version"
        row["feature_snapshot_json"] = json.dumps(snapshot)
        dataset = build_learning_dataset([row])
        self.assertIn("unsupported_feature_schema", dataset["audit"]["excluded_reasons"])

    def test_non_finite_features_are_rejected(self):
        row = self._record()
        snapshot = json.loads(row["feature_snapshot_json"])
        snapshot["calculated"]["home_rating"] = float("inf")
        row["feature_snapshot_json"] = json.dumps(snapshot)
        dataset = build_learning_dataset([row])
        self.assertIn("non_finite_or_non_json_feature", dataset["audit"]["excluded_reasons"])

    def test_export_is_deterministic_and_round_trips(self):
        records = [self._record(index=i) for i in range(1, 4)]
        with tempfile.TemporaryDirectory() as directory:
            first_path = Path(directory) / "one.json"
            second_path = Path(directory) / "two.json"
            first = export_learning_dataset(records, first_path)
            second = export_learning_dataset(records, second_path)
            self.assertEqual(first, second)
            self.assertEqual(first_path.read_text(encoding="utf-8"), second_path.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(first_path.read_text(encoding="utf-8"))["audit"]["unique_verified_fixtures"], 3)

    def test_invalid_sample_gate_is_rejected(self):
        with self.assertRaises(ValueError):
            build_learning_dataset([], minimum_experiment_fixtures=0)


if __name__ == "__main__":
    unittest.main()
