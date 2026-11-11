"""Scheduled promotion of explicitly approved future fixtures into the app catalogue.

All provider and licence switches default to disabled. No mapping is inferred
or approved here; this runner only consumes links already explicitly approved
in CockroachDB and stages fixtures that pass the existing promotion gates.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from free_fixture_canonical_promotion import review_and_promote_free_fixture_observations
from temporary_fixture_store import add_temporary_upcoming_fixtures


PROVIDER_ACKS = {
    "openligadb": {
        "enabled": "FREE_FIXTURE_AUTO_PROMOTE_OPENLIGADB",
        "terms": "FREE_FIXTURE_TERMS_ACK_OPENLIGADB",
    },
    "openfootball": {
        "enabled": "FREE_FIXTURE_AUTO_PROMOTE_OPENFOOTBALL",
        "terms": "FREE_FIXTURE_TERMS_ACK_OPENFOOTBALL",
    },
    "open_matchday": {
        "enabled": "FREE_FIXTURE_AUTO_PROMOTE_OPEN_MATCHDAY",
        "terms": "FREE_FIXTURE_TERMS_ACK_OPEN_MATCHDAY",
        "noncommercial": "FREE_FIXTURE_NONCOMMERCIAL_ACK_OPEN_MATCHDAY",
    },
    "livescore_football": {
        "enabled": "FREE_FIXTURE_AUTO_PROMOTE_LIVESCORE",
        "terms": "FREE_FIXTURE_TERMS_ACK_LIVESCORE",
    },
    "bzzoiro": {
        "enabled": "FREE_FIXTURE_AUTO_PROMOTE_BZZOIRO",
        "terms": "FREE_FIXTURE_TERMS_ACK_BZZOIRO",
    },
    "highlightly": {
        "enabled": "FREE_FIXTURE_AUTO_PROMOTE_HIGHLIGHTLY",
        "terms": "FREE_FIXTURE_TERMS_ACK_HIGHLIGHTLY",
        "non_betting": "HIGHLIGHTLY_NON_BETTING_USE_CONFIRMED",
    },
    "api_ninjas": {
        "enabled": "FREE_FIXTURE_AUTO_PROMOTE_API_NINJAS",
        "terms": "FREE_FIXTURE_TERMS_ACK_API_NINJAS",
        "noncommercial": "FREE_FIXTURE_NONCOMMERCIAL_ACK_API_NINJAS",
    },
}


def _enabled(env: Mapping[str, str], key: str | None) -> bool:
    if not key:
        return False
    return str(env.get(key, "")).strip().casefold() in {"1", "true", "yes", "on"}


def run_automatic_fixture_promotion(
    provider_database_url: str,
    temporary_database_url: str,
    *,
    env: Mapping[str, str] | None = None,
    now: datetime | None = None,
    promotion_fn: Callable[..., dict[str, Any]] = review_and_promote_free_fixture_observations,
    staging_fn: Callable[..., dict[str, Any]] = add_temporary_upcoming_fixtures,
) -> dict[str, Any]:
    """Promote only explicitly enabled, terms-acknowledged and crosswalked fixtures."""
    settings = os.environ if env is None else env
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware.")
    current = current.astimezone(timezone.utc)
    globally_enabled = _enabled(settings, "FREE_FIXTURE_AUTO_PROMOTION_ENABLED")
    results: dict[str, Any] = {}
    canonical_writes = 0
    temporary_inserts = 0

    for provider, keys in PROVIDER_ACKS.items():
        if not globally_enabled:
            results[provider] = {"status": "skipped", "reason": "global_auto_promotion_disabled"}
            continue
        if not _enabled(settings, keys["enabled"]):
            results[provider] = {"status": "skipped", "reason": "provider_auto_promotion_disabled"}
            continue
        if not _enabled(settings, keys["terms"]):
            results[provider] = {"status": "skipped", "reason": "provider_terms_not_acknowledged"}
            continue
        noncommercial_key = keys.get("noncommercial")
        if noncommercial_key and not _enabled(settings, noncommercial_key):
            results[provider] = {"status": "skipped", "reason": "noncommercial_use_not_confirmed"}
            continue
        non_betting_key = keys.get("non_betting")
        if non_betting_key and not _enabled(settings, non_betting_key):
            results[provider] = {
                "status": "skipped",
                "reason": "highlightly_non_betting_use_not_confirmed",
            }
            continue
        if not provider_database_url or not temporary_database_url:
            results[provider] = {"status": "error", "reason": "required_database_url_missing"}
            continue

        try:
            promotion = promotion_fn(
                provider_database_url,
                provider=provider,
                promote=True,
                now=current,
                snapshot_limit=3,
                max_age_hours=24,
                window_days=7,
                licence_acknowledged=True,
                open_matchday_noncommercial_confirmed=(
                    provider == "open_matchday" and _enabled(settings, noncommercial_key)
                ),
                api_ninjas_noncommercial_confirmed=(
                    provider == "api_ninjas" and _enabled(settings, noncommercial_key)
                ),
                highlightly_non_betting_confirmed=(
                    provider == "highlightly" and _enabled(settings, non_betting_key)
                ),
            )
            provider_writes = int(promotion.get("canonical_fixture_writes") or 0)
            canonical_writes += provider_writes
            staging_fixtures = promotion.get("staging_fixtures") or []
            try:
                staging_report = (
                    staging_fn(temporary_database_url, staging_fixtures)
                    if staging_fixtures else {
                        "fixtures_inserted": 0,
                        "fixtures_already_present": 0,
                        "fixtures_removed": 0,
                        "prediction_ledger_modified": 0,
                    }
                )
            except Exception as staging_exc:
                results[provider] = {
                    "status": "canonical_promoted_staging_failed",
                    "error_type": type(staging_exc).__name__,
                    "canonical_fixture_writes": provider_writes,
                    "decisions": promotion.get("decisions") or {},
                    "prediction_ledger_writes": 0,
                }
                continue
            temporary_inserts += int(staging_report.get("fixtures_inserted") or 0)
            results[provider] = {
                "status": "completed",
                "decisions": promotion.get("decisions") or {},
                "canonical_fixture_writes": provider_writes,
                "neon_staging": {
                    "fixtures_inserted": int(staging_report.get("fixtures_inserted") or 0),
                    "fixtures_already_present": int(staging_report.get("fixtures_already_present") or 0),
                    "fixtures_removed": int(staging_report.get("fixtures_removed") or 0),
                },
                "prediction_ledger_writes": 0,
            }
        except Exception as exc:
            results[provider] = {
                "status": "error",
                "error_type": type(exc).__name__,
            }

    return {
        "report_name": "free_fixture_auto_promotion",
        "generated_at_utc": current.isoformat(),
        "automatic_promotion_enabled": globally_enabled,
        "providers": results,
        "canonical_fixture_writes": canonical_writes,
        "temporary_fixture_inserts": temporary_inserts,
        "prediction_ledger_writes": 0,
    }


def main() -> int:
    report = run_automatic_fixture_promotion(
        os.getenv("PROVIDER_DATABASE_URL", ""),
        os.getenv("DATABASE_URL", ""),
    )
    output = Path(os.getenv(
        "FREE_FIXTURE_AUTO_PROMOTION_PATH",
        "reports/free_fixture_auto_promotion/latest.json",
    ))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "report_name": report["report_name"],
        "output": str(output),
        "automatic_promotion_enabled": report["automatic_promotion_enabled"],
        "providers": {
            provider: {
                "status": value["status"],
                "reason": value.get("reason"),
                "decisions": value.get("decisions"),
                "canonical_fixture_writes": value.get("canonical_fixture_writes", 0),
                "neon_staging": value.get("neon_staging"),
            }
            for provider, value in report["providers"].items()
        },
        "canonical_fixture_writes": report["canonical_fixture_writes"],
        "temporary_fixture_inserts": report["temporary_fixture_inserts"],
        "prediction_ledger_writes": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
