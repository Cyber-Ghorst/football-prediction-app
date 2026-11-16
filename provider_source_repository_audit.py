"""Read-only audit of all currently staged provider-native source catalogues."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from provider_source_repository import audit_provider_source_evidence

REPORT = Path("provider-source-repository-audit.json")
PROVIDERS = ("api_football", "api_ninjas", "highlightly", "livescore_football", "sportmonks")


def main() -> int:
    database_url = os.getenv("PROVIDER_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("PROVIDER_DATABASE_URL is not configured.")
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "database_writes": False,
        "providers": {
            provider: audit_provider_source_evidence(database_url, provider)
            for provider in PROVIDERS
        },
        "canonical_entities_created": 0,
        "cross_provider_links_created": 0,
        "fixtures_ingested": 0,
        "prediction_ledger_touched": False,
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
