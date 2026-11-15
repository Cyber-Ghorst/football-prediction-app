"""Read-only identity candidate audit across staged provider source entities.

Candidate keys are not canonical IDs. This module never persists identities,
approves links, or compares provider IDs as if they were globally unique.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from provider_data_storage import _connect
from provider_neutral_identity import (
    canonical_competition_key,
    canonical_season_key,
    canonical_team_key,
)


def _missing(row: Mapping[str, Any], fields: tuple[str, ...]) -> list[str]:
    return [field for field in fields if not str(row.get(field) or "").strip()]


def build_identity_candidate_report(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Create candidate keys only where every required identity dimension exists."""
    competition_candidates = []
    seasons = []
    teams = []
    key_groups: dict[str, list[dict[str, str]]] = defaultdict(list)

    for row in rows:
        provider = str(row.get("provider") or "").strip().casefold()
        entity_type = str(row.get("entity_type") or "").strip().casefold()
        provider_id = str(row.get("provider_entity_id") or "").strip()
        base = {
            "provider": provider,
            "provider_entity_id": provider_id,
            "name": row.get("name"),
        }
        if not provider or not provider_id:
            continue

        if entity_type == "competition":
            required = ("name", "country", "competition_type")
            missing = _missing(row, required)
            if missing:
                result = {**base, "status": "held_missing_identity_dimensions",
                          "missing_dimensions": missing, "identity_key_candidate": None}
            else:
                key = canonical_competition_key(
                    row.get("name"), row.get("country"), row.get("competition_type")
                )
                result = {**base, "country": row.get("country"),
                          "competition_type": row.get("competition_type"),
                          "status": "single_source_identity_candidate",
                          "missing_dimensions": [], "identity_key_candidate": key}
                key_groups[key].append({"provider": provider, "provider_entity_id": provider_id})
            competition_candidates.append(result)

        elif entity_type == "season":
            # A provider parent ID is not a canonical competition ID.
            result = {
                **base,
                "provider_parent_competition_id": row.get("parent_competition_provider_id"),
                "season_label": row.get("season_label") or row.get("name"),
                "status": "held_until_parent_competition_is_approved",
                "identity_key_candidate": None,
                "reason": "A verified canonical competition ID is required before season identity can be keyed.",
            }
            seasons.append(result)

        elif entity_type == "team":
            required = ("name", "country", "team_type", "gender_scope", "age_group", "squad_scope")
            missing = _missing(row, required)
            if missing:
                result = {
                    **base, "status": "held_missing_team_scope",
                    "missing_dimensions": missing, "identity_key_candidate": None,
                }
            else:
                try:
                    key = canonical_team_key(
                        row.get("name"), row.get("country"), row.get("team_type"),
                        row.get("gender_scope"), row.get("age_group"), row.get("squad_scope"),
                    )
                except ValueError as exc:
                    result = {**base, "status": "held_invalid_team_scope",
                              "reason": str(exc), "identity_key_candidate": None}
                else:
                    result = {**base, "status": "single_source_identity_candidate",
                              "missing_dimensions": [], "identity_key_candidate": key}
            teams.append(result)

    shared = []
    for key, sources in key_groups.items():
        if len(sources) > 1:
            shared.append({"identity_key_candidate": key, "source_entities": sources,
                           "status": "shared_identity_candidate_requires_manual_review"})
    shared_keys = {row["identity_key_candidate"] for row in shared}
    for row in competition_candidates:
        if row.get("identity_key_candidate") in shared_keys:
            row["status"] = "shared_identity_candidate_requires_manual_review"

    return {
        "read_only": True,
        "canonical_ids_assigned": 0,
        "provider_links_created": 0,
        "competition_candidates": competition_candidates,
        "shared_competition_candidates": shared,
        "season_candidates": seasons,
        "team_candidates": teams,
        "summary": {
            "competition_source_rows": len(competition_candidates),
            "competition_identity_keys_candidate": sum(
                bool(row.get("identity_key_candidate")) for row in competition_candidates
            ),
            "shared_competition_identity_candidates": len(shared),
            "seasons_held_for_parent_approval": len(seasons),
            "team_source_rows": len(teams),
            "teams_held_for_scope_evidence": sum(
                row.get("status") != "single_source_identity_candidate" for row in teams
            ),
        },
        "interpretation": (
            "Deterministic keys are review candidates only. They are not canonical IDs, "
            "and no provider link is approved or written by this audit."
        ),
    }


def audit_provider_neutral_identity_candidates(database_url: str) -> dict[str, Any]:
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    columns = (
        "provider", "entity_type", "provider_entity_id", "name", "country",
        "competition_type", "parent_competition_provider_id", "season_label",
        "team_type", "gender_scope", "age_group", "squad_scope",
    )
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(
                f"""SELECT {', '.join(columns)}
                    FROM provider_source_entities
                    ORDER BY provider, entity_type, provider_entity_id"""
            )
            rows = [dict(zip(columns, values)) for values in cursor.fetchall()]
    report = build_identity_candidate_report(rows)
    report["database_read_only"] = True
    report["source_rows_read"] = len(rows)
    report["database_writes"] = False
    return report
