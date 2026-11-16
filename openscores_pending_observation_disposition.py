"""Auditable disposition of the 150 operator-rejected OpenScores observations."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from openscores_observation_store import (
    audit_pending_openscores_observations,
    discard_pending_openscores_observations,
)

REPORT = Path("openscores-pending-observation-disposition-report.json")


def main() -> int:
    mode = sys.argv[1].strip().casefold() if len(sys.argv) > 1 else "audit"
    database_url = os.getenv("PROVIDER_DATABASE_URL", "").strip()
    report = {
        "operation": f"openscores_pending_disposition_{mode}",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": mode == "audit",
        "database_writes": mode == "discard",
        "raw_records_deleted": 0,
        "provider_links_modified": 0,
        "canonical_fixtures_modified": 0,
        "canonical_ids_assigned": 0,
        "provider_links_created": 0,
        "prediction_model_modified": False,
        "prediction_ledger_touched": False,
    }
    try:
        if mode == "audit":
            report.update(audit_pending_openscores_observations(database_url))
            report["status"] = "pass" if report.get("preflight_passed") else "blocked"
        elif mode == "discard":
            report.update(discard_pending_openscores_observations(database_url))
            report["status"] = report.get("status", "discarded_by_operator")
        else:
            raise ValueError("mode must be 'audit' or 'discard'")
    except Exception as exc:
        report["status"] = "blocked"
        report["error_type"] = type(exc).__name__
        report["error"] = str(exc)[:500]
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
                      encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "mode": mode,
        "pending_entity_mapping": report.get("pending_entity_mapping"),
        "matched": report.get("matched"),
        "discarded_by_operator": report.get("discarded_by_operator"),
        "updated": report.get("updated", 0),
        "raw_records_deleted": 0,
        "provider_links_modified": 0,
        "report": str(REPORT),
    }, indent=2))
    return 0 if report["status"] in {"pass", "discarded_by_operator", "already_discarded"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
