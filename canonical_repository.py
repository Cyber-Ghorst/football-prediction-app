"""Read-only compatibility resolver for explicitly approved provider links.

This is a transitional facade over the legacy Sportmonks-keyed repository.
A row in provider_entity_links is not sufficient evidence of approval: the
resolver requires an exact matching append-only approval-audit record and an
existing legacy entity row. It performs SELECT statements only and never
creates schema, writes links, or changes entity identifiers.
"""
from __future__ import annotations

from typing import Any

from provider_data_storage import _connect


ENTITY_TABLES = {
    "league": ("football_leagues", "league_id"),
    "season": ("football_seasons", "season_id"),
    "team": ("football_teams", "team_id"),
    "fixture": ("football_fixtures", "fixture_id"),
}


def classify_approved_link_rows(rows: list[tuple[Any, ...]]) -> dict[str, Any]:
    """Classify matching, already-audited links without guessing between sources."""
    distinct = {
        (str(row[0]), str(row[1]), str(row[2]), str(row[3]))
        for row in rows
    }
    if not distinct:
        return {"status": "unresolved", "source_provider": None,
                "source_entity_id": None}
    if len(distinct) != 1:
        return {"status": "ambiguous", "source_provider": None,
                "source_entity_id": None}
    provider_entity_id, canonical_entity_id, provider, entity_type = next(iter(distinct))
    return {
        "status": "resolved",
        "source_provider": provider,
        "source_entity_id": provider_entity_id,
        "canonical_entity_id": canonical_entity_id,
        "entity_type": entity_type,
    }


def resolve_approved_legacy_source_id(
    database_url: str,
    *,
    provider: str,
    entity_type: str,
    canonical_entity_id: str,
) -> dict[str, Any]:
    """Resolve one canonical target to a provider ID only when explicit approval exists.

    The provider argument is mandatory because a canonical entity may legitimately
    have multiple source-provider links. The result is a source ID, never a
    canonical ID masquerading as a provider ID.
    """
    provider_name = str(provider or "").strip().casefold()
    entity_kind = str(entity_type or "").strip().casefold()
    canonical_id = str(canonical_entity_id or "").strip()
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    if not provider_name:
        raise ValueError("A source provider is required.")
    if entity_kind not in ENTITY_TABLES:
        raise ValueError("Unsupported entity_type.")
    if not canonical_id:
        raise ValueError("A canonical_entity_id is required.")

    table, primary_key = ENTITY_TABLES[entity_kind]
    query = f"""
        SELECT DISTINCT
            link.provider_entity_id,
            link.canonical_entity_id,
            link.provider,
            link.entity_type
        FROM provider_entity_links AS link
        INNER JOIN provider_entity_link_approval_audit AS approval
            ON approval.link_id = link.link_id
           AND approval.provider = link.provider
           AND approval.entity_type = link.entity_type
           AND approval.provider_entity_id = link.provider_entity_id
           AND approval.canonical_entity_id = link.canonical_entity_id
        INNER JOIN {table} AS legacy_entity
            ON legacy_entity.{primary_key} = link.canonical_entity_id
        WHERE link.provider = %s
          AND link.entity_type = %s
          AND link.canonical_entity_id = %s
        ORDER BY link.provider_entity_id
    """
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (provider_name, entity_kind, canonical_id))
            rows = cursor.fetchall()
    result = classify_approved_link_rows(rows)
    if result["status"] == "resolved":
        # Guard against a malformed/mock result escaping the requested scope.
        if (result["source_provider"] != provider_name
                or result["entity_type"] != entity_kind
                or result["canonical_entity_id"] != canonical_id):
            return {"status": "unresolved", "source_provider": None,
                    "source_entity_id": None}
    return result


def audit_provider_link_parity(
    database_url: str,
    *,
    provider: str,
) -> dict[str, Any]:
    """Read-only inventory of approval, verification and native identity evidence.

    Sportmonks links whose canonical IDs use the legacy Sportmonks namespace
    are native identity anchors. OpenScores has a separate verification ledger;
    only exact matching rows marked verified count as verified crosswalks.
    Other cross-provider links require an exact approval-audit match.
    """
    provider_name = str(provider or "").strip().casefold()
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    if not provider_name:
        raise ValueError("A source provider is required.")

    entity_reports: dict[str, dict[str, int]] = {}
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY", ())
            for entity_kind, (table, primary_key) in ENTITY_TABLES.items():
                cursor.execute(
                    f"""
                    SELECT
                        COUNT(DISTINCT link.link_id) AS total_links,
                        COUNT(DISTINCT CASE
                            WHEN approval.link_id IS NOT NULL THEN link.link_id
                        END) AS approved_links,
                        COUNT(DISTINCT CASE
                            WHEN approval.link_id IS NULL
                             AND NOT (link.provider = 'sportmonks'
                                      AND link.canonical_entity_id = 'sportmonks:' || link.provider_entity_id)
                             AND NOT (link.provider = 'openscores'
                                      AND verification.verification_status = 'verified')
                             AND NOT (link.provider = 'openscores'
                                      AND link.entity_type = 'fixture'
                                      AND fixture_observation.observation_id IS NOT NULL)
                            THEN link.link_id
                        END) AS unapproved_links,
                        COUNT(DISTINCT CASE
                            WHEN link.provider = 'sportmonks'
                             AND link.canonical_entity_id = 'sportmonks:' || link.provider_entity_id
                            THEN link.link_id
                        END) AS native_identity_anchors,
                        COUNT(DISTINCT CASE
                            WHEN link.provider = 'sportmonks'
                             AND link.canonical_entity_id = 'sportmonks:' || link.provider_entity_id
                             AND legacy_entity.{primary_key} IS NULL
                            THEN link.link_id
                        END) AS native_identity_anchors_missing_target,
                        COUNT(DISTINCT CASE
                            WHEN verification.verification_status = 'verified'
                            THEN link.link_id
                        END) AS verified_links,
                        COUNT(DISTINCT CASE
                            WHEN verification.verification_status = 'review_required'
                            THEN link.link_id
                        END) AS review_required_links,
                        COUNT(DISTINCT CASE
                            WHEN verification.verification_status = 'rejected'
                            THEN link.link_id
                        END) AS rejected_links,
                        COUNT(DISTINCT CASE
                            WHEN link.provider = 'openscores'
                             AND link.entity_type = 'fixture'
                             AND fixture_observation.observation_id IS NOT NULL
                            THEN link.link_id
                        END) AS reconciled_fixture_links,
                        COUNT(DISTINCT CASE
                            WHEN link.provider = 'openscores'
                             AND link.entity_type = 'fixture'
                             AND fixture_observation.observation_id IS NULL
                            THEN link.link_id
                        END) AS unreconciled_fixture_links,
                        COUNT(DISTINCT CASE
                            WHEN approval.link_id IS NOT NULL
                             AND legacy_entity.{primary_key} IS NULL
                            THEN link.link_id
                        END) AS approved_targets_missing,
                        COUNT(DISTINCT CASE
                            WHEN approval.link_id IS NOT NULL
                             AND legacy_entity.{primary_key} IS NOT NULL
                            THEN link.link_id
                        END) AS approved_links_with_legacy_target
                    FROM provider_entity_links AS link
                    LEFT JOIN provider_entity_link_approval_audit AS approval
                      ON approval.link_id = link.link_id
                     AND approval.provider = link.provider
                     AND approval.entity_type = link.entity_type
                     AND approval.provider_entity_id = link.provider_entity_id
                     AND approval.canonical_entity_id = link.canonical_entity_id
                     AND LENGTH(BTRIM(approval.approval_reason)) >= 12
                    LEFT JOIN provider_entity_link_verifications AS verification
                      ON verification.link_id = link.link_id
                     AND verification.provider = link.provider
                     AND verification.entity_type = link.entity_type
                     AND verification.provider_entity_id = link.provider_entity_id
                     AND verification.canonical_entity_id = link.canonical_entity_id
                    LEFT JOIN provider_fixture_observations AS fixture_observation
                      ON fixture_observation.provider = 'openscores'
                     AND fixture_observation.provider_fixture_id = link.provider_entity_id
                     AND fixture_observation.canonical_fixture_id = link.canonical_entity_id
                     AND fixture_observation.reconciliation_status IN ('matched', 'outside_upcoming_window')
                    LEFT JOIN {table} AS legacy_entity
                      ON legacy_entity.{primary_key} = link.canonical_entity_id
                    WHERE link.provider = %s AND link.entity_type = %s
                    """,
                    (provider_name, entity_kind),
                )
                row = cursor.fetchone()
                entity_reports[entity_kind] = {
                    "total_links": int(row[0] or 0),
                    "approved_links": int(row[1] or 0),
                    "unapproved_links": int(row[2] or 0),
                    "native_identity_anchors": int(row[3] or 0),
                    "native_identity_anchors_missing_target": int(row[4] or 0),
                    "verified_links": int(row[5] or 0),
                    "review_required_links": int(row[6] or 0),
                    "rejected_links": int(row[7] or 0),
                    "reconciled_fixture_links": int(row[8] or 0),
                    "unreconciled_fixture_links": int(row[9] or 0),
                    "approved_targets_missing": int(row[10] or 0),
                    "approved_links_with_legacy_target": int(row[11] or 0),
                }

                cursor.execute(
                    f"""
                    SELECT COUNT(*) FROM (
                        SELECT link.canonical_entity_id
                        FROM provider_entity_links AS link
                        LEFT JOIN provider_entity_link_approval_audit AS approval
                          ON approval.link_id = link.link_id
                         AND approval.provider = link.provider
                         AND approval.entity_type = link.entity_type
                         AND approval.provider_entity_id = link.provider_entity_id
                         AND approval.canonical_entity_id = link.canonical_entity_id
                         AND LENGTH(BTRIM(approval.approval_reason)) >= 12
                        LEFT JOIN provider_entity_link_verifications AS verification
                          ON verification.link_id = link.link_id
                         AND verification.provider = link.provider
                         AND verification.entity_type = link.entity_type
                         AND verification.provider_entity_id = link.provider_entity_id
                         AND verification.canonical_entity_id = link.canonical_entity_id
                        LEFT JOIN provider_fixture_observations AS fixture_observation
                          ON fixture_observation.provider = 'openscores'
                         AND fixture_observation.provider_fixture_id = link.provider_entity_id
                         AND fixture_observation.canonical_fixture_id = link.canonical_entity_id
                         AND fixture_observation.reconciliation_status IN ('matched', 'outside_upcoming_window')
                        WHERE link.provider = %s AND link.entity_type = %s
                          AND (approval.link_id IS NOT NULL
                               OR verification.verification_status = 'verified'
                               OR fixture_observation.observation_id IS NOT NULL)
                        GROUP BY link.canonical_entity_id
                        HAVING COUNT(DISTINCT link.provider_entity_id) > 1
                    ) AS ambiguous_targets
                    """,
                    (provider_name, entity_kind),
                )
                entity_reports[entity_kind]["ambiguous_canonical_targets"] = int(
                    cursor.fetchone()[0] or 0
                )

    totals = {
        key: sum(report[key] for report in entity_reports.values())
        for key in (
            "total_links", "approved_links", "unapproved_links",
            "native_identity_anchors", "native_identity_anchors_missing_target",
            "verified_links", "review_required_links", "rejected_links",
            "reconciled_fixture_links", "unreconciled_fixture_links",
            "approved_targets_missing", "approved_links_with_legacy_target",
        )
    }
    totals["ambiguous_canonical_targets"] = sum(
        report["ambiguous_canonical_targets"] for report in entity_reports.values()
    )
    return {
        "provider": provider_name,
        "read_only": True,
        "entity_types": entity_reports,
        "totals": totals,
    }


def list_provider_link_sources(database_url: str) -> list[str]:
    """Return provider names represented in the link table using a read-only query."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY", ())
            cursor.execute(
                "SELECT DISTINCT provider FROM provider_entity_links "
                "WHERE provider IS NOT NULL ORDER BY provider",
                (),
            )
            return [str(row[0]).strip().casefold() for row in cursor.fetchall()
                    if row and str(row[0] or "").strip()]
