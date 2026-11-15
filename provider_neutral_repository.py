"""Read-only compatibility facade for provider-shaped repository rows.

The current repository IDs remain untouched. This module exposes their
namespaced source identities in a provider-neutral shape without assigning
application-owned canonical UUIDs or writing any mappings.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from provider_data_storage import _connect


TABLE_COLUMNS = {
    "leagues": (
        "league_id", "name", "country", "competition_type", "logo_url",
        "source_provider", "provider_updated_at", "collected_at", "raw_payload",
    ),
    "seasons": (
        "season_id", "league_id", "name", "start_date", "end_date", "is_current",
        "source_provider", "provider_updated_at", "collected_at", "raw_payload",
    ),
    "teams": (
        "team_id", "name", "short_name", "country", "logo_url", "source_provider",
        "provider_updated_at", "collected_at", "raw_payload",
    ),
    "fixtures": (
        "fixture_id", "season_id", "league_id", "home_team_id", "away_team_id",
        "starting_at", "status", "home_goals", "away_goals", "venue",
        "source_provider", "provider_updated_at", "collected_at", "raw_payload",
    ),
    "statistics": (
        "statistic_id", "fixture_id", "team_id", "statistic_type", "statistic_value",
        "source_provider", "provider_statistic_id", "provider_updated_at",
        "collected_at", "raw_payload",
    ),
}


def split_provider_identity(value: Any, declared_provider: Any) -> dict[str, Any]:
    """Parse a namespaced source ID without assuming any provider is canonical."""
    raw = str(value or "").strip()
    provider = str(declared_provider or "").strip().casefold()
    if not raw or not provider:
        return {
            "provider": provider or None, "provider_entity_id": None,
            "legacy_repository_id": raw or None, "identity_status": "missing_identity",
        }
    if ":" not in raw:
        return {
            "provider": provider, "provider_entity_id": raw,
            "legacy_repository_id": raw, "identity_status": "legacy_unprefixed",
        }
    prefix, provider_id = raw.split(":", 1)
    if not prefix or not provider_id:
        status = "invalid_namespaced_identity"
    elif prefix.casefold() != provider:
        status = "provider_prefix_mismatch"
    else:
        status = "namespaced_source_identity"
    return {
        "provider": provider, "provider_entity_id": provider_id or None,
        "legacy_repository_id": raw, "identity_status": status,
    }


def _source_ref(value: Any, provider: Any) -> dict[str, Any] | None:
    if value is None or str(value).strip() == "":
        return None
    return split_provider_identity(value, provider)


def normalize_repository_rows(raw: Mapping[str, list[Mapping[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    """Convert existing rows to normalized source records; never create canonical IDs."""
    output: dict[str, list[dict[str, Any]]] = {
        key: [] for key in TABLE_COLUMNS
    }
    for row in raw.get("leagues", []):
        provider = row.get("source_provider")
        output["leagues"].append({
            "source_identity": split_provider_identity(row.get("league_id"), provider),
            "name": row.get("name"), "country": row.get("country"),
            "competition_type": row.get("competition_type"),
            "logo_url": row.get("logo_url"), "provider_updated_at": row.get("provider_updated_at"),
            "collected_at": row.get("collected_at"), "raw_payload": row.get("raw_payload"),
        })
    for row in raw.get("seasons", []):
        provider = row.get("source_provider")
        output["seasons"].append({
            "source_identity": split_provider_identity(row.get("season_id"), provider),
            "competition_source_identity": _source_ref(row.get("league_id"), provider),
            "name": row.get("name"), "start_date": row.get("start_date"),
            "end_date": row.get("end_date"), "is_current": row.get("is_current"),
            "provider_updated_at": row.get("provider_updated_at"),
            "collected_at": row.get("collected_at"), "raw_payload": row.get("raw_payload"),
        })
    for row in raw.get("teams", []):
        provider = row.get("source_provider")
        output["teams"].append({
            "source_identity": split_provider_identity(row.get("team_id"), provider),
            "name": row.get("name"), "short_name": row.get("short_name"),
            "country": row.get("country"), "logo_url": row.get("logo_url"),
            "provider_updated_at": row.get("provider_updated_at"),
            "collected_at": row.get("collected_at"), "raw_payload": row.get("raw_payload"),
        })
    for row in raw.get("fixtures", []):
        provider = row.get("source_provider")
        output["fixtures"].append({
            "source_identity": split_provider_identity(row.get("fixture_id"), provider),
            "season_source_identity": _source_ref(row.get("season_id"), provider),
            "competition_source_identity": _source_ref(row.get("league_id"), provider),
            "home_team_source_identity": _source_ref(row.get("home_team_id"), provider),
            "away_team_source_identity": _source_ref(row.get("away_team_id"), provider),
            "starting_at": row.get("starting_at"), "status": row.get("status"),
            "home_goals": row.get("home_goals"), "away_goals": row.get("away_goals"),
            "venue": row.get("venue"), "provider_updated_at": row.get("provider_updated_at"),
            "collected_at": row.get("collected_at"), "raw_payload": row.get("raw_payload"),
        })
    for row in raw.get("statistics", []):
        provider = row.get("source_provider")
        output["statistics"].append({
            "source_identity": split_provider_identity(
                row.get("provider_statistic_id") or row.get("statistic_id"), provider,
            ),
            "fixture_source_identity": _source_ref(row.get("fixture_id"), provider),
            "team_source_identity": _source_ref(row.get("team_id"), provider),
            "statistic_type": row.get("statistic_type"),
            "statistic_value": row.get("statistic_value"),
            "provider_updated_at": row.get("provider_updated_at"),
            "collected_at": row.get("collected_at"), "raw_payload": row.get("raw_payload"),
        })
    return output


def build_provider_neutral_audit(raw: Mapping[str, list[Mapping[str, Any]]],
                                 approved_links: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    normalized = normalize_repository_rows(raw)
    counts = {key: len(rows) for key, rows in normalized.items()}
    provider_counts: dict[str, dict[str, int]] = {}
    invalid: list[dict[str, Any]] = []
    for entity_type, rows in normalized.items():
        for row in rows:
            identity = row.get("source_identity")
            provider = (identity or {}).get("provider") or "unknown"
            provider_counts.setdefault(provider, Counter())[entity_type] += 1
            if not identity or identity.get("identity_status") not in {
                "namespaced_source_identity", "legacy_unprefixed",
            }:
                invalid.append({
                    "entity_type": entity_type,
                    "legacy_repository_id": (identity or {}).get("legacy_repository_id"),
                    "provider": provider,
                    "status": (identity or {}).get("identity_status", "missing_identity"),
                })
    links = approved_links or []
    link_counts = Counter(str(row.get("provider") or "unknown") for row in links)
    return {
        "read_only": True,
        "writes_performed": 0,
        "application_owned_canonical_ids_assigned": 0,
        "provider_links_created": 0,
        "normalized_entity_counts": counts,
        "provider_entity_counts": {
            provider: dict(values) for provider, values in sorted(provider_counts.items())
        },
        "existing_approved_link_counts": dict(sorted(link_counts.items())),
        "invalid_source_identity_count": len(invalid),
        "invalid_source_identities": invalid,
        "normalized_records": normalized,
        "interpretation": (
            "These are normalized provider source records, not application-owned canonical entities. "
            "Existing legacy repository IDs and provider provenance are preserved."
        ),
    }


def read_provider_neutral_repository(database_url: str) -> dict[str, Any]:
    """Read existing repository tables only; deliberately does not run schema DDL."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    raw: dict[str, list[dict[str, Any]]] = {}
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            for entity_type, columns in TABLE_COLUMNS.items():
                table = {
                    "leagues": "football_leagues",
                    "seasons": "football_seasons",
                    "teams": "football_teams",
                    "fixtures": "football_fixtures",
                    "statistics": "football_fixture_statistics",
                }[entity_type]
                cursor.execute(
                    f"SELECT {', '.join(columns)} FROM {table} ORDER BY 1"
                )
                raw[entity_type] = [
                    dict(zip(columns, values)) for values in cursor.fetchall()
                ]
            cursor.execute(
                """SELECT provider, entity_type, provider_entity_id, canonical_entity_id
                   FROM provider_entity_links
                   ORDER BY provider, entity_type, provider_entity_id"""
            )
            link_columns = (
                "provider", "entity_type", "provider_entity_id", "canonical_entity_id",
            )
            links = [dict(zip(link_columns, values)) for values in cursor.fetchall()]
            cursor.execute(
                """SELECT provider, entity_type, COUNT(*)
                   FROM provider_entity_links
                   GROUP BY provider, entity_type
                   ORDER BY provider, entity_type"""
            )
            link_breakdown = [
                {"provider": row[0], "entity_type": row[1], "count": int(row[2])}
                for row in cursor.fetchall()
            ]
            cursor.execute(
                """SELECT provider, entity_type, COUNT(*)
                   FROM provider_entity_link_approval_audit
                   GROUP BY provider, entity_type
                   ORDER BY provider, entity_type"""
            )
            audit_breakdown = [
                {"provider": row[0], "entity_type": row[1], "audit_rows": int(row[2])}
                for row in cursor.fetchall()
            ]
            cursor.execute(
                """SELECT l.provider, l.entity_type,
                          COUNT(DISTINCT l.link_id) AS link_count,
                          COUNT(DISTINCT a.audit_id) AS audit_count
                   FROM provider_entity_links l
                   LEFT JOIN provider_entity_link_approval_audit a
                     ON a.link_id = l.link_id
                    AND a.provider = l.provider
                    AND a.entity_type = l.entity_type
                    AND a.provider_entity_id = l.provider_entity_id
                    AND a.canonical_entity_id = l.canonical_entity_id
                   GROUP BY l.provider, l.entity_type
                   ORDER BY l.provider, l.entity_type"""
            )
            audit_coverage = [
                {"provider": row[0], "entity_type": row[1],
                 "link_count": int(row[2]), "matching_audit_rows": int(row[3])}
                for row in cursor.fetchall()
            ]
            cursor.execute(
                """SELECT provider, entity_type, provider_entity_id, canonical_entity_id
                   FROM provider_entity_links
                   WHERE provider = 'openscores'
                   ORDER BY entity_type, provider_entity_id
                   LIMIT 30"""
            )
            link_samples = [
                {"provider": row[0], "entity_type": row[1],
                 "provider_entity_id": row[2], "canonical_entity_id": row[3]}
                for row in cursor.fetchall()
            ]
    report = build_provider_neutral_audit(raw, links)
    report["database_read_only"] = True
    report["table_rows_read"] = dict(report["normalized_entity_counts"])
    report["provider_link_breakdown"] = link_breakdown
    report["approval_audit_breakdown"] = audit_breakdown
    report["provider_link_audit_coverage"] = audit_coverage
    report["openscores_link_samples"] = link_samples
    return report
