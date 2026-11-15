"""Read-only coverage audit for provider-link approval evidence.

Approval evidence is matched on the complete link identity tuple. A missing
approval record is reported separately from verified OpenScores evidence,
reconciled OpenScores fixtures and Sportmonks native identity anchors.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from provider_data_storage import _connect

REPORT = Path("provider-link-approval-evidence-audit.json")

SUMMARY_SQL = """
SELECT
    link.provider,
    link.entity_type,
    COUNT(DISTINCT link.link_id) AS total_links,
    COUNT(DISTINCT CASE WHEN EXISTS (
        SELECT 1 FROM provider_entity_link_approval_audit AS approval
        WHERE approval.link_id = link.link_id
          AND approval.provider = link.provider
          AND approval.entity_type = link.entity_type
          AND approval.provider_entity_id = link.provider_entity_id
          AND approval.canonical_entity_id = link.canonical_entity_id
          AND LENGTH(BTRIM(approval.approval_reason)) >= 12
    ) THEN link.link_id END) AS exact_approval_matches,
    COUNT(DISTINCT CASE WHEN EXISTS (
        SELECT 1 FROM provider_entity_link_approval_audit AS approval
        WHERE approval.link_id = link.link_id
    ) AND NOT EXISTS (
        SELECT 1 FROM provider_entity_link_approval_audit AS approval
        WHERE approval.link_id = link.link_id
          AND approval.provider = link.provider
          AND approval.entity_type = link.entity_type
          AND approval.provider_entity_id = link.provider_entity_id
          AND approval.canonical_entity_id = link.canonical_entity_id
          AND LENGTH(BTRIM(approval.approval_reason)) >= 12
    ) THEN link.link_id END) AS link_id_present_but_tuple_or_reason_invalid,
    COUNT(DISTINCT CASE WHEN NOT EXISTS (
        SELECT 1 FROM provider_entity_link_approval_audit AS approval
        WHERE approval.link_id = link.link_id
    ) THEN link.link_id END) AS no_approval_record_for_link_id,
    COUNT(DISTINCT CASE WHEN EXISTS (
        SELECT 1 FROM provider_entity_link_verifications AS verification
        WHERE verification.link_id = link.link_id
          AND verification.provider = link.provider
          AND verification.entity_type = link.entity_type
          AND verification.provider_entity_id = link.provider_entity_id
          AND verification.canonical_entity_id = link.canonical_entity_id
          AND verification.verification_status = 'verified'
    ) THEN link.link_id END) AS verified_links,
    COUNT(DISTINCT CASE WHEN EXISTS (
        SELECT 1 FROM provider_entity_link_verifications AS verification
        WHERE verification.link_id = link.link_id
          AND verification.provider = link.provider
          AND verification.entity_type = link.entity_type
          AND verification.provider_entity_id = link.provider_entity_id
          AND verification.canonical_entity_id = link.canonical_entity_id
          AND verification.verification_status = 'review_required'
    ) THEN link.link_id END) AS review_required_links,
    COUNT(DISTINCT CASE WHEN EXISTS (
        SELECT 1 FROM provider_entity_link_verifications AS verification
        WHERE verification.link_id = link.link_id
          AND verification.provider = link.provider
          AND verification.entity_type = link.entity_type
          AND verification.provider_entity_id = link.provider_entity_id
          AND verification.canonical_entity_id = link.canonical_entity_id
          AND verification.verification_status = 'rejected'
    ) THEN link.link_id END) AS rejected_links,
    COUNT(DISTINCT CASE WHEN link.provider = 'sportmonks'
      AND link.canonical_entity_id = 'sportmonks:' || link.provider_entity_id
      THEN link.link_id END) AS sportmonks_native_identity_anchors,
    COUNT(DISTINCT CASE WHEN link.provider = 'openscores'
      AND link.entity_type = 'fixture'
      AND EXISTS (
        SELECT 1 FROM provider_fixture_observations AS observation
        WHERE observation.provider = 'openscores'
          AND observation.provider_fixture_id = link.provider_entity_id
          AND observation.canonical_fixture_id = link.canonical_entity_id
          AND observation.reconciliation_status IN ('matched', 'outside_upcoming_window')
      ) THEN link.link_id END) AS reconciled_openscores_fixture_links
FROM provider_entity_links AS link
GROUP BY link.provider, link.entity_type
ORDER BY link.provider, link.entity_type
"""

ORPHAN_APPROVAL_SQL = """
SELECT approval.provider, approval.entity_type, COUNT(*) AS orphan_approval_records
FROM provider_entity_link_approval_audit AS approval
WHERE NOT EXISTS (
    SELECT 1 FROM provider_entity_links AS link
    WHERE link.link_id = approval.link_id
      AND link.provider = approval.provider
      AND link.entity_type = approval.entity_type
      AND link.provider_entity_id = approval.provider_entity_id
      AND link.canonical_entity_id = approval.canonical_entity_id
)
GROUP BY approval.provider, approval.entity_type
ORDER BY approval.provider, approval.entity_type
"""

UNMATCHED_SAMPLE_SQL = """
SELECT
    link.provider, link.entity_type, link.link_id,
    link.provider_entity_id, link.canonical_entity_id,
    CASE WHEN EXISTS (
        SELECT 1 FROM provider_entity_link_approval_audit AS approval
        WHERE approval.link_id = link.link_id
    ) THEN 'link_id_present_but_tuple_or_reason_invalid'
    ELSE 'no_approval_record_for_link_id' END AS approval_record_state,
    EXISTS (
        SELECT 1 FROM provider_entity_link_verifications AS verification
        WHERE verification.link_id = link.link_id
          AND verification.provider = link.provider
          AND verification.entity_type = link.entity_type
          AND verification.provider_entity_id = link.provider_entity_id
          AND verification.canonical_entity_id = link.canonical_entity_id
          AND verification.verification_status = 'verified'
    ) AS has_exact_verified_evidence,
    EXISTS (
        SELECT 1 FROM provider_fixture_observations AS observation
        WHERE link.provider = 'openscores'
          AND link.entity_type = 'fixture'
          AND observation.provider = 'openscores'
          AND observation.provider_fixture_id = link.provider_entity_id
          AND observation.canonical_fixture_id = link.canonical_entity_id
          AND observation.reconciliation_status IN ('matched', 'outside_upcoming_window')
    ) AS has_exact_reconciled_fixture_evidence,
    (link.provider = 'sportmonks'
      AND link.canonical_entity_id = 'sportmonks:' || link.provider_entity_id)
      AS is_sportmonks_native_identity_anchor
FROM provider_entity_links AS link
WHERE NOT EXISTS (
    SELECT 1 FROM provider_entity_link_approval_audit AS approval
    WHERE approval.link_id = link.link_id
      AND approval.provider = link.provider
      AND approval.entity_type = link.entity_type
      AND approval.provider_entity_id = link.provider_entity_id
      AND approval.canonical_entity_id = link.canonical_entity_id
      AND LENGTH(BTRIM(approval.approval_reason)) >= 12
)
ORDER BY link.provider, link.entity_type, link.provider_entity_id
LIMIT 30
"""

OPENSCORES_SAMPLE_SQL = """
SELECT
    link.link_id, link.entity_type, link.provider_entity_id, link.canonical_entity_id,
    EXISTS (
        SELECT 1 FROM provider_entity_link_approval_audit AS approval
        WHERE approval.link_id = link.link_id
          AND approval.provider = link.provider
          AND approval.entity_type = link.entity_type
          AND approval.provider_entity_id = link.provider_entity_id
          AND approval.canonical_entity_id = link.canonical_entity_id
          AND LENGTH(BTRIM(approval.approval_reason)) >= 12
    ) AS has_exact_approval_evidence,
    EXISTS (
        SELECT 1 FROM provider_entity_link_verifications AS verification
        WHERE verification.link_id = link.link_id
          AND verification.provider = link.provider
          AND verification.entity_type = link.entity_type
          AND verification.provider_entity_id = link.provider_entity_id
          AND verification.canonical_entity_id = link.canonical_entity_id
          AND verification.verification_status = 'verified'
    ) AS has_exact_verified_evidence,
    EXISTS (
        SELECT 1 FROM provider_fixture_observations AS observation
        WHERE link.entity_type = 'fixture'
          AND observation.provider = 'openscores'
          AND observation.provider_fixture_id = link.provider_entity_id
          AND observation.canonical_fixture_id = link.canonical_entity_id
          AND observation.reconciliation_status IN ('matched', 'outside_upcoming_window')
    ) AS has_exact_reconciled_fixture_evidence
FROM provider_entity_links AS link
WHERE link.provider = 'openscores'
ORDER BY link.entity_type, link.provider_entity_id
LIMIT 12
"""


def _rows(cursor, columns: tuple[str, ...]) -> list[dict[str, Any]]:
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def audit_provider_link_approval_evidence(database_url: str) -> dict[str, Any]:
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    summary_columns = (
        "provider", "entity_type", "total_links", "exact_approval_matches",
        "link_id_present_but_tuple_or_reason_invalid", "no_approval_record_for_link_id",
        "verified_links", "review_required_links", "rejected_links",
        "sportmonks_native_identity_anchors", "reconciled_openscores_fixture_links",
    )
    orphan_columns = ("provider", "entity_type", "orphan_approval_records")
    unmatched_columns = (
        "provider", "entity_type", "link_id", "provider_entity_id",
        "canonical_entity_id", "approval_record_state", "has_exact_verified_evidence",
        "has_exact_reconciled_fixture_evidence", "is_sportmonks_native_identity_anchor",
    )
    openscores_columns = (
        "link_id", "entity_type", "provider_entity_id", "canonical_entity_id",
        "has_exact_approval_evidence", "has_exact_verified_evidence",
        "has_exact_reconciled_fixture_evidence",
    )
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY", ())
            cursor.execute(SUMMARY_SQL)
            summary = _rows(cursor, summary_columns)
            cursor.execute(ORPHAN_APPROVAL_SQL)
            orphan_approvals = _rows(cursor, orphan_columns)
            cursor.execute(UNMATCHED_SAMPLE_SQL)
            unmatched_samples = _rows(cursor, unmatched_columns)
            cursor.execute(OPENSCORES_SAMPLE_SQL)
            openscores_samples = _rows(cursor, openscores_columns)

    return {
        "read_only": True,
        "database_writes": False,
        "matching_rule": [
            "link_id", "provider", "entity_type",
            "provider_entity_id", "canonical_entity_id",
        ],
        "approval_reason_minimum_length": 12,
        "provider_entity_type_counts": summary,
        "orphan_approval_record_counts": orphan_approvals,
        "unmatched_link_samples": unmatched_samples,
        "unmatched_link_sample_limit": 30,
        "openscores_link_samples": openscores_samples,
        "openscores_sample_limit": 12,
        "interpretation": (
            "No exact approval match does not automatically mean a link is invalid. "
            "OpenScores verification and reconciled fixture observations, plus Sportmonks "
            "native identity anchors, are reported as separate evidence paths. "
            "Samples are diagnostic only; no link is approved or modified."
        ),
        "canonical_ids_assigned": 0,
        "provider_links_created": 0,
        "fixtures_ingested": 0,
        "prediction_ledger_touched": False,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    database_url = os.getenv("PROVIDER_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("PROVIDER_DATABASE_URL is not configured.")
    report = audit_provider_link_approval_evidence(database_url)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
                      encoding="utf-8")
    print(json.dumps({
        "checked_at": report["checked_at"],
        "read_only": report["read_only"],
        "provider_entity_type_counts": report["provider_entity_type_counts"],
        "orphan_approval_record_counts": report["orphan_approval_record_counts"],
        "unmatched_link_sample_count": len(report["unmatched_link_samples"]),
        "openscores_link_sample_count": len(report["openscores_link_samples"]),
        "canonical_ids_assigned": report["canonical_ids_assigned"],
        "provider_links_created": report["provider_links_created"],
        "report": str(REPORT),
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
