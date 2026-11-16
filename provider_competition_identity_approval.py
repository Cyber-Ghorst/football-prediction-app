"""Approve only the three exact shared competition identity candidates reviewed in Layer 12.

This operation creates API-Football -> existing Sportmonks canonical competition
links only after verifying source rows, normalized name/country/type equality,
canonical target rows, and absence of conflicting prior links. It does not
create canonical competitions or approve seasons, teams, or fixtures.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from football_repository import ensure_football_repository
from provider_data_storage import _connect
from provider_entity_crosswalk import save_explicit_provider_entity_links
from provider_neutral_identity import canonical_competition_key

TARGETS = (
    {"api_football_id": "135", "sportmonks_id": "384", "name": "Serie A", "country": "Italy"},
    {"api_football_id": "140", "sportmonks_id": "564", "name": "La Liga", "country": "Spain"},
    {"api_football_id": "39", "sportmonks_id": "8", "name": "Premier League", "country": "England"},
)
REPORT = Path("provider-competition-identity-approval-report.json")
APPROVAL_REASON = (
    "Layer 12 reviewed approval: API-Football and Sportmonks source records have "
    "the same exact normalized competition name, country and competition type; "
    "the target is the existing Sportmonks canonical league. API-Football free-plan "
    "2026 season access is unavailable, so this approval is competition-only and "
    "does not approve any season, team, fixture or current-season roster identity."
)


def build_approval_plan(
    source_rows: list[Mapping[str, Any]],
    canonical_rows: list[Mapping[str, Any]],
    existing_links: list[Mapping[str, Any]],
    approval_rows: list[Mapping[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    source_index: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in source_rows:
        source_index.setdefault(
            (str(row.get("provider") or "").casefold(), str(row.get("provider_entity_id") or "")), []
        ).append(row)
    canonical_index = {str(row.get("league_id")): row for row in canonical_rows}
    existing_index = {
        (str(row.get("provider") or "").casefold(), str(row.get("entity_type") or "").casefold(),
         str(row.get("provider_entity_id") or "")): row
        for row in existing_links
    }
    approval_index = {
        (str(row.get("provider") or "").casefold(), str(row.get("entity_type") or "").casefold(),
         str(row.get("provider_entity_id") or ""), str(row.get("canonical_entity_id") or "")): row
        for row in approval_rows
    }
    plan: list[dict[str, str]] = []
    held: list[dict[str, Any]] = []
    for target in TARGETS:
        api_key = ("api_football", target["api_football_id"])
        sm_key = ("sportmonks", target["sportmonks_id"])
        api_matches = source_index.get(api_key, [])
        sm_matches = source_index.get(sm_key, [])
        if len(api_matches) != 1 or len(sm_matches) != 1:
            held.append({
                "target": target, "reason": "source_identity_not_unique",
                "api_football_rows": len(api_matches), "sportmonks_rows": len(sm_matches),
            })
            continue
        api_row, sm_row = api_matches[0], sm_matches[0]
        canonical_id = f"sportmonks:{target['sportmonks_id']}"
        canonical_row = canonical_index.get(canonical_id)
        if canonical_row is None:
            held.append({"target": target, "reason": "existing_canonical_target_missing",
                         "canonical_entity_id": canonical_id})
            continue
        try:
            api_identity = canonical_competition_key(
                api_row.get("name"), api_row.get("country"), api_row.get("competition_type")
            )
            sm_identity = canonical_competition_key(
                sm_row.get("name"), sm_row.get("country"), sm_row.get("competition_type")
            )
            canonical_identity = canonical_competition_key(
                canonical_row.get("name"), canonical_row.get("country"), sm_row.get("competition_type")
            )
        except ValueError as exc:
            held.append({"target": target, "reason": "identity_dimension_unverified", "detail": str(exc)})
            continue
        if not (
            api_identity == sm_identity == canonical_identity
            and str(api_row.get("name") or "").casefold() == target["name"].casefold()
            and str(api_row.get("country") or "").casefold() == target["country"].casefold()
        ):
            held.append({
                "target": target, "reason": "normalized_identity_or_expected_name_country_mismatch",
                "api_identity_key": api_identity, "sportmonks_identity_key": sm_identity,
                "canonical_identity_key": canonical_identity,
            })
            continue
        existing = existing_index.get(("api_football", "league", target["api_football_id"]))
        if existing is not None:
            if str(existing.get("canonical_entity_id")) != canonical_id:
                held.append({
                    "target": target, "reason": "conflicting_existing_provider_link",
                    "existing_canonical_entity_id": existing.get("canonical_entity_id"),
                })
                continue
            approved = approval_index.get(
                ("api_football", "league", target["api_football_id"], canonical_id)
            )
            if approved is None or len(str(approved.get("approval_reason") or "").strip()) < 12:
                held.append({
                    "target": target, "reason": "existing_link_lacks_exact_approval_record",
                    "canonical_entity_id": canonical_id,
                })
                continue
            held.append({"target": target, "reason": "already_exactly_approved",
                         "canonical_entity_id": canonical_id})
            continue
        plan.append({
            "provider": "api_football", "entity_type": "league",
            "provider_entity_id": target["api_football_id"],
            "canonical_entity_id": canonical_id,
        })
    return plan, held


def approve_reviewed_competitions(database_url: str) -> dict[str, Any]:
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    ensure_football_repository(database_url)
    canonical_ids = [f"sportmonks:{row['sportmonks_id']}" for row in TARGETS]
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(
                """SELECT provider, provider_entity_id, name, country, competition_type
                   FROM provider_source_entities
                   WHERE entity_type = 'competition'
                     AND ((provider = 'api_football' AND provider_entity_id IN ('135','140','39'))
                       OR (provider = 'sportmonks' AND provider_entity_id IN ('384','564','8')))
                   ORDER BY provider, provider_entity_id"""
            )
            source_rows = [
                dict(zip(("provider","provider_entity_id","name","country","competition_type"), row))
                for row in cursor.fetchall()
            ]
            cursor.execute(
                """SELECT league_id, name, country
                   FROM football_leagues
                   WHERE league_id = ANY(%s)
                   ORDER BY league_id""",
                (canonical_ids,),
            )
            canonical_rows = [
                dict(zip(("league_id","name","country"), row)) for row in cursor.fetchall()
            ]
            cursor.execute(
                """SELECT provider, entity_type, provider_entity_id, canonical_entity_id
                   FROM provider_entity_links
                   WHERE provider = 'api_football' AND entity_type = 'league'
                     AND provider_entity_id IN ('135','140','39')"""
            )
            existing_links = [
                dict(zip(("provider","entity_type","provider_entity_id","canonical_entity_id"), row))
                for row in cursor.fetchall()
            ]
            cursor.execute(
                """SELECT provider, entity_type, provider_entity_id, canonical_entity_id, approval_reason
                   FROM provider_entity_link_approval_audit
                   WHERE provider = 'api_football' AND entity_type = 'league'
                     AND provider_entity_id IN ('135','140','39')"""
            )
            approval_rows = [
                dict(zip(("provider","entity_type","provider_entity_id","canonical_entity_id","approval_reason"), row))
                for row in cursor.fetchall()
            ]
    plan, held = build_approval_plan(source_rows, canonical_rows, existing_links, approval_rows)
    saved = save_explicit_provider_entity_links(
        database_url, links=plan, approval_reason=APPROVAL_REASON
    ) if plan else 0
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "operation": "reviewed_competition_identity_approval",
        "write_scope": "three_api_football_competition_links_only",
        "candidates_reviewed": len(TARGETS),
        "new_links_approved_and_written": saved,
        "already_approved": sum(row.get("reason") == "already_exactly_approved" for row in held),
        "held": held,
        "approved_links": plan,
        "approval_reason": APPROVAL_REASON,
        "api_football_current_2026_roster_limitation": (
            "Free plan rejected 2026 season access; this competition-only approval does not "
            "validate current-season teams or season identities."
        ),
        "canonical_competitions_created": 0,
        "seasons_approved": 0,
        "teams_approved": 0,
        "fixtures_written": 0,
        "predictions_written": 0,
        "prediction_ledger_touched": False,
    }


def main() -> int:
    report = approve_reviewed_competitions(os.getenv("PROVIDER_DATABASE_URL", "").strip())
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
                      encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
