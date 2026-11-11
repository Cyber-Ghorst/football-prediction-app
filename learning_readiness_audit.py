"""Read-only live-ledger audit for leakage-safe offline learning readiness."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from learning_dataset import build_learning_dataset
from learning_experiments import run_offline_experiments
from prediction_storage import load_prediction_ledger


def build_learning_readiness_audit(database_url: str) -> dict[str, Any]:
    if not database_url:
        raise ValueError("DATABASE_URL is required.")
    records = load_prediction_ledger(database_url)
    dataset = build_learning_dataset(records)
    experiments = run_offline_experiments(dataset)
    return {
        "report_name": "learning_readiness_audit",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "ledger_record_count": len(records),
        "dataset_audit": dataset.get("audit", {}),
        "sample_gate": dataset.get("sample_gate", {}),
        "split_fixture_counts": {
            split: len(rows)
            for split, rows in dataset.get("split_fixture_identities", {}).items()
        },
        "offline_experiment": {
            "status": experiments.get("status"),
            "sample_gate": experiments.get("sample_gate"),
            "results": experiments.get("results"),
            "candidate_training_prior_pct": experiments.get("candidate_training_prior_pct"),
            "production_promotion_permitted": False,
        },
        "safety": {
            "database_access": "read_only",
            "raw_ledger_records_exported": False,
            "raw_feature_vectors_exported": False,
            "live_model_modified": False,
            "model_weights_modified": False,
            "tvd_modified": False,
            "prediction_ledger_writes": 0,
            "production_promotion_permitted": False,
        },
    }


def main() -> int:
    database_url = os.getenv("DATABASE_URL", "").strip()
    report = build_learning_readiness_audit(database_url)
    output = Path(os.getenv(
        "LEARNING_READINESS_REPORT_PATH",
        "learning-readiness-report.json",
    ))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "report_name": report["report_name"],
        "output": str(output),
        "ledger_records": report["ledger_record_count"],
        "verified_unique_fixtures": report["sample_gate"].get("verified_fixtures", 0),
        "sample_gate_status": report["sample_gate"].get("status"),
        "offline_experiment_status": report["offline_experiment"].get("status"),
        "production_promotion_permitted": False,
        "live_model_modified": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
