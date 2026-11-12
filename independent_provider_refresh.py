"""Independent data-provider refresh; deliberately separate from future-fixture discovery."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from football_data_org_pipeline import collect_football_data_org_observations


def refresh_independent_data_providers(
    database_url: str,
    *,
    token: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Collect football-data.org observations independently of discovery sources."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware.")
    current = current.astimezone(timezone.utc)
    date_from = current.date().isoformat()
    date_to = (current.date() + timedelta(days=7)).isoformat()
    if not token:
        return {
            "generated_at_utc": current.isoformat(),
            "provider_group": "independent_data",
            "providers": {
                "football_data_org": {
                    "provider": "football_data_org",
                    "status": "skipped",
                    "reason": "FOOTBALL_DATA_ORG_API_TOKEN is not configured.",
                    "observation_count": 0,
                    "canonical_fixture_writes": 0,
                    "prediction_ledger_writes": 0,
                }
            },
            "canonical_fixture_writes": 0,
            "prediction_ledger_writes": 0,
        }
    try:
        result = collect_football_data_org_observations(
            database_url,
            date_from=date_from,
            date_to=date_to,
            api_token=token,
        )
        provider_result = {"provider": "football_data_org", "status": "ok", **result}
    except Exception as exc:
        provider_result = {
            "provider": "football_data_org",
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc)[:300],
            "observation_count": 0,
            "canonical_fixture_writes": 0,
            "prediction_ledger_writes": 0,
        }
    return {
        "generated_at_utc": current.isoformat(),
        "provider_group": "independent_data",
        "window": {"date_from": date_from, "date_to": date_to},
        "providers": {"football_data_org": provider_result},
        "canonical_fixture_writes": 0,
        "prediction_ledger_writes": 0,
    }


def main() -> int:
    report = refresh_independent_data_providers(
        os.getenv("PROVIDER_DATABASE_URL", ""),
        token=(
            os.getenv("FOOTBALL_DATA_ORG_API_TOKEN")
            or os.getenv("FOOTBALL_DATA_ORG_TOKEN")
            or os.getenv("FOOTBALL_DATA_API_KEY")
            or None
        ),
    )
    print(json.dumps(report, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
