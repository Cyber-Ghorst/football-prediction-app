"""Generate a credential-safe, read-only provider-link parity report."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from canonical_repository import (
    audit_provider_link_parity,
    list_provider_link_sources,
)


REPORT_PATH = Path("reports/provider_independent_catalogue/approved_link_parity_latest.json")


def build_report(database_url: str, provider: str) -> dict[str, Any]:
    """Build one provider-scoped report; the underlying audit is SELECT-only."""
    result = audit_provider_link_parity(database_url, provider=provider)
    return {
        "report_schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audit_mode": "read_only",
        "database_writes": False,
        "provider": provider,
        "result": result,
        "interpretation": (
            "Sportmonks source IDs that equal their legacy primary keys are reported "
            "as native identity anchors, not cross-provider approvals. Other links "
            "require exact approval-audit evidence. Counts do not authorize new links; "
            "unapproved, missing-target, or ambiguous records require separate review. "
            "No records are created, modified, approved, or promoted by this report."
        ),
    }


def main() -> int:
    database_url = os.getenv("PROVIDER_DATABASE_URL", "")
    if not database_url:
        print("ERROR: PROVIDER_DATABASE_URL is not configured.", file=sys.stderr)
        return 2
    try:
        providers = list_provider_link_sources(database_url)
        reports = [build_report(database_url, provider) for provider in providers]
        payload: dict[str, Any] = {
            "report_schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "audit_mode": "read_only",
            "database_writes": False,
            "providers": reports,
        }
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:  # Never print connection strings or provider exception text.
        print(
            f"ERROR: parity audit failed ({type(exc).__name__}); details withheld to protect credentials.",
            file=sys.stderr,
        )
        return 1

    print(json.dumps({
        "audit_status": "completed",
        "provider_count": len(reports),
        "providers": [item["provider"] for item in reports],
        "report_path": str(REPORT_PATH),
        "database_writes": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
