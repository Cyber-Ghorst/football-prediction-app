"""Generate a read-only, machine-readable crosswalk progress audit."""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from provider_crosswalk_review_report import build_provider_crosswalk_review_report

PROVIDERS = (
    "openligadb", "openfootball", "open_matchday",
    "livescore_football", "bzzoiro",
)


def build_crosswalk_audit(database_url: str) -> dict[str, Any]:
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    results: dict[str, Any] = {}
    for provider in PROVIDERS:
        try:
            report = build_provider_crosswalk_review_report(
                database_url, provider=provider, snapshot_limit=5,
            )
            categories = {}
            for category, candidates in report.get("candidates", {}).items():
                status_counts = Counter(
                    str(row.get("status") or "unknown")
                    for row in candidates if isinstance(row, dict)
                )
                categories[category] = {
                    "candidate_count": len(candidates),
                    "status_counts": dict(sorted(status_counts.items())),
                    "candidates": candidates,
                }
            results[provider] = {
                "status": "ok",
                "snapshot_count": report.get("snapshot_count", 0),
                "observation_count": report.get("observation_count", 0),
                "source_entity_counts": report.get("source_entity_counts", {}),
                "existing_link_counts": report.get("existing_link_counts", {}),
                "categories": categories,
            }
        except Exception as exc:
            results[provider] = {
                "status": "error",
                "error_type": type(exc).__name__,
            }
    return {
        "report_name": "free_fixture_crosswalk_audit",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "providers": results,
        "automatic_mapping_approvals": 0,
        "canonical_fixture_writes": 0,
        "prediction_ledger_writes": 0,
    }


def main() -> int:
    report = build_crosswalk_audit(os.getenv("PROVIDER_DATABASE_URL", ""))
    output = Path(os.getenv(
        "FREE_FIXTURE_CROSSWALK_AUDIT_PATH",
        "reports/free_fixture_crosswalk_audit/latest.json",
    ))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({
        "report_name": report["report_name"],
        "output": str(output),
        "providers": {
            provider: {
                "status": data["status"],
                "snapshots": data.get("snapshot_count", 0),
                "observations": data.get("observation_count", 0),
                "source_entity_counts": data.get("source_entity_counts", {}),
                "existing_link_counts": data.get("existing_link_counts", {}),
            }
            for provider, data in report["providers"].items()
        },
        "automatic_mapping_approvals": 0,
        "canonical_fixture_writes": 0,
        "prediction_ledger_writes": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
