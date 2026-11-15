"""Run the read-only provider-neutral repository compatibility audit."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from provider_neutral_repository import read_provider_neutral_repository


def main() -> int:
    database_url = os.getenv("PROVIDER_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("PROVIDER_DATABASE_URL is not configured.")
    report = read_provider_neutral_repository(database_url)
    report["checked_at"] = datetime.now(timezone.utc).isoformat()
    report["canonical_migration_performed"] = False
    report["prediction_model_modified"] = False
    report["prediction_ledger_touched"] = False
    Path("provider-neutral-repository-audit.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "checked_at": report["checked_at"],
        "read_only": report["read_only"],
        "table_rows_read": report["table_rows_read"],
        "provider_entity_counts": report["provider_entity_counts"],
        "existing_approved_link_counts": report["existing_approved_link_counts"],
        "invalid_source_identity_count": report["invalid_source_identity_count"],
        "writes_performed": report["writes_performed"],
        "report": "provider-neutral-repository-audit.json",
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
