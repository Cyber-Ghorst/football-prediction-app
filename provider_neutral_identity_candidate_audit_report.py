"""Generate a read-only provider-neutral identity candidate report."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from provider_neutral_identity_candidate_audit import audit_provider_neutral_identity_candidates

REPORT = Path("provider-neutral-identity-candidate-audit.json")


def main() -> int:
    database_url = os.getenv("PROVIDER_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("PROVIDER_DATABASE_URL is not configured.")
    report = audit_provider_neutral_identity_candidates(database_url)
    report["checked_at"] = datetime.now(timezone.utc).isoformat()
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report.get("summary", {}), indent=2))
    print("read_only=true canonical_ids_assigned=0 provider_links_created=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
