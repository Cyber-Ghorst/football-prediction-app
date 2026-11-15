"""Read-only audit of provider-native source staging tables."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from provider_source_repository import audit_provider_source_evidence

REPORT = Path("provider-source-repository-audit.json")


def main() -> int:
    database_url = os.getenv("PROVIDER_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("PROVIDER_DATABASE_URL is not configured.")
    report = audit_provider_source_evidence(database_url, "livescore_football")
    report["checked_at"] = datetime.now(timezone.utc).isoformat()
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
