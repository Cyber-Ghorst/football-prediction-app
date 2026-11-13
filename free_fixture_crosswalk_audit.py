"""Generate a read-only, machine-readable crosswalk progress audit."""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from provider_independent_competition_catalogue import (
    build_provider_independent_competition_catalogue,
)
from provider_crosswalk_review_report import (
    build_provider_crosswalk_review_report,
    load_canonical_crosswalk_catalogue,
)

CANDIDATE_SAMPLE_LIMIT = 25

PROVIDERS = (
    "openligadb", "openfootball", "open_matchday",
    "livescore_football", "bzzoiro", "highlightly", "api_ninjas",
    "football_data_org",
)


def build_crosswalk_audit(
    database_url: str, *, highlightly_use_allowed: bool = False,
    api_ninjas_noncommercial_confirmed: bool = False,
    open_matchday_noncommercial_confirmed: bool = False,
) -> dict[str, Any]:
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    results: dict[str, Any] = {}
    source_leagues_by_provider: dict[str, list[dict[str, Any]]] = {}\n    source_seasons_by_provider: dict[str, list[dict[str, Any]]] = {}
    try:
        canonical_catalogue = load_canonical_crosswalk_catalogue(database_url)
    except Exception as exc:
        return {
            "report_name": "free_fixture_crosswalk_audit",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "providers": {
                provider: {"status": "error", "error_type": type(exc).__name__}
                for provider in PROVIDERS
            },
            "automatic_mapping_approvals": 0,
            "canonical_fixture_writes": 0,
            "prediction_ledger_writes": 0,
        }
    for provider in PROVIDERS:
        if provider == "highlightly" and not highlightly_use_allowed:
            results[provider] = {
                "status": "skipped",
                "reason": "Highlightly terms acknowledgement and non-betting-use confirmation are required.",
            }
            continue
        if provider == "api_ninjas" and not api_ninjas_noncommercial_confirmed:
            results[provider] = {
                "status": "skipped",
                "reason": "API Ninjas free-plan non-commercial-use confirmation is required.",
            }
            continue
        if provider == "open_matchday" and not open_matchday_noncommercial_confirmed:
            results[provider] = {
                "status": "skipped",
                "reason": "Open Matchday non-commercial-use confirmation is required.",
            }
            continue
        try:
            report = build_provider_crosswalk_review_report(
                database_url, provider=provider, snapshot_limit=3,
                canonical_catalogue=canonical_catalogue,
            )
            source_leagues_by_provider[provider] = list(
                report.get("source_entities", {}).get("leagues", [])
            )
            source_seasons_by_provider[provider] = list(
                report.get("source_entities", {}).get("seasons", [])
            )
            categories = {}
            for category, candidates in report.get("candidates", {}).items():
                status_counts = Counter(
                    str(row.get("status") or "unknown")
                    for row in candidates if isinstance(row, dict)
                )
                manual_review_candidates = [
                    row for row in candidates
                    if row.get("status") == "candidate_requires_manual_approval"
                ]
                unmatched_candidates = [
                    row for row in candidates
                    if row.get("status") != "candidate_requires_manual_approval"
                ]
                categories[category] = {
                    "candidate_count": len(candidates),
                    "manual_review_candidate_count": len(manual_review_candidates),
                    "status_counts": dict(sorted(status_counts.items())),
                    "candidates": [
                        *manual_review_candidates,
                        *unmatched_candidates[:CANDIDATE_SAMPLE_LIMIT],
                    ],
                    "candidates_truncated": len(unmatched_candidates) > CANDIDATE_SAMPLE_LIMIT,
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
        "provider_independent_catalogue": build_provider_independent_competition_catalogue(
            source_leagues_by_provider, source_seasons_by_provider
        ),
        "automatic_mapping_approvals": 0,
        "canonical_fixture_writes": 0,
        "prediction_ledger_writes": 0,
    }


def main() -> int:
    enabled = lambda name: os.getenv(name, "").strip().casefold() in {"1", "true", "yes", "on"}
    report = build_crosswalk_audit(
        os.getenv("PROVIDER_DATABASE_URL", ""),
        highlightly_use_allowed=(
            enabled("FREE_FIXTURE_TERMS_ACK_HIGHLIGHTLY")
            and enabled("HIGHLIGHTLY_NON_BETTING_USE_CONFIRMED")
        ),
        api_ninjas_noncommercial_confirmed=(
            enabled("FREE_FIXTURE_TERMS_ACK_API_NINJAS")
            and enabled("FREE_FIXTURE_NONCOMMERCIAL_ACK_API_NINJAS")
        ),
        open_matchday_noncommercial_confirmed=(
            enabled("FREE_FIXTURE_TERMS_ACK_OPEN_MATCHDAY")
            and enabled("FREE_FIXTURE_NONCOMMERCIAL_ACK_OPEN_MATCHDAY")
        ),
    )
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
        "provider_independent_catalogue": {
            "competition_count": report.get("provider_independent_catalogue", {}).get("competition_count", 0),
            "corroborated_competition_count": report.get("provider_independent_catalogue", {}).get("corroborated_competition_count", 0),
            "canonical_seed_review_candidate_count": report.get("provider_independent_catalogue", {}).get("canonical_seed_review_candidate_count", 0),
            "country_unscoped_source_count": report.get("provider_independent_catalogue", {}).get("country_unscoped_source_count", 0),
        },
        "automatic_mapping_approvals": 0,
        "canonical_fixture_writes": 0,
        "prediction_ledger_writes": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
