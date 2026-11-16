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


def _date_value(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _date_normalized_season_label(start_date: Any, end_date: Any) -> str | None:
    start = _date_value(start_date)
    end = _date_value(end_date)
    if not start or not end:
        return None
    try:
        start_year = int(start[:4])
        end_year = int(end[:4])
    except (TypeError, ValueError):
        return None
    if end_year < start_year:
        return None
    return f"{start_year}/{end_year}" if end_year != start_year else str(start_year)


def build_identity_candidate_report(
    rows: list[Mapping[str, Any]],
    approved_parent_links: Mapping[tuple[str, str], str] | None = None,
) -> dict[str, Any]:
    """Create candidate keys only where every required identity dimension exists."""
    competition_candidates = []
    seasons = []
    teams = []
    key_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    approved_parents = dict(approved_parent_links or {})

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
            # A provider parent ID is not a canonical competition ID. Release
            # a deterministic season-key candidate only when the exact parent
            # competition link is already approved or is a Sportmonks native
            # identity anchor. The key remains a candidate, not a season link.
            provider_parent_id = str(row.get("parent_competition_provider_id") or "").strip()
            season_label = row.get("season_label") or row.get("name")
            date_label_candidate = _date_normalized_season_label(
                row.get("start_date"), row.get("end_date")
            )
            canonical_parent_id = approved_parents.get((provider, provider_parent_id))
            if not canonical_parent_id:
                result = {
                    **base,
                    "provider_parent_competition_id": provider_parent_id or None,
                    "season_label": season_label,
                    "date_normalized_season_label_candidate": date_label_candidate,
                    "start_date": _date_value(row.get("start_date")),
                    "end_date": _date_value(row.get("end_date")),
                    "season_date_range_status": (
                        "complete" if row.get("start_date") and row.get("end_date")
                        else "incomplete"
                    ),
                    "status": "held_until_parent_competition_is_approved",
                    "identity_key_candidate": None,
                    "reason": "A verified canonical competition ID is required before season identity can be keyed.",
                }
            else:
                try:
                    season_key = canonical_season_key(canonical_parent_id, season_label)
                except ValueError as exc:
                    result = {
                        **base,
                        "provider_parent_competition_id": provider_parent_id,
                        "canonical_parent_competition_id": canonical_parent_id,
                        "season_label": season_label,
                        "date_normalized_season_label_candidate": date_label_candidate,
                        "start_date": _date_value(row.get("start_date")),
                        "end_date": _date_value(row.get("end_date")),
                        "season_date_range_status": (
                            "complete" if row.get("start_date") and row.get("end_date")
                            else "incomplete"
                        ),
                        "status": "held_invalid_season_identity",
                        "identity_key_candidate": None,
                        "reason": str(exc),
                    }
                else:
                    result = {
                        **base,
                        "provider_parent_competition_id": provider_parent_id,
                        "canonical_parent_competition_id": canonical_parent_id,
                        "season_label": season_label,
                        "date_normalized_season_label_candidate": date_label_candidate,
                        "start_date": _date_value(row.get("start_date")),
                        "end_date": _date_value(row.get("end_date")),
                        "season_date_range_status": (
                            "complete" if row.get("start_date") and row.get("end_date")
                            else "incomplete"
                        ),
                        "status": "season_key_candidate_parent_approved_review_required",
                        "identity_key_candidate": season_key,
                        "date_normalized_identity_key_candidate": (
                            canonical_season_key(canonical_parent_id, date_label_candidate)
                            if date_label_candidate else None
                        ),
                        "reason": (
                            "Parent competition is approved; this deterministic season key is "
                            "only a candidate. Exact season evidence is still required before "
                            "any season provider link can be approved."
                        ),
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
    duplicates = []
    for key, sources in key_groups.items():
        providers = {source["provider"] for source in sources}
        if len(providers) > 1:
            shared.append({"identity_key_candidate": key, "source_entities": sources,
                           "status": "shared_identity_candidate_requires_manual_review"})
        elif len(sources) > 1:
            duplicates.append({"identity_key_candidate": key, "source_entities": sources,
                               "status": "duplicate_within_provider_requires_review"})
    shared_keys = {row["identity_key_candidate"] for row in shared}
    duplicate_keys = {row["identity_key_candidate"] for row in duplicates}
    for row in competition_candidates:
        key = row.get("identity_key_candidate")
        if key in shared_keys:
            row["status"] = "shared_identity_candidate_requires_manual_review"
        elif key in duplicate_keys:
            row["status"] = "duplicate_within_provider_requires_review"

    return {
        "read_only": True,
        "canonical_ids_assigned": 0,
        "provider_links_created": 0,
        "competition_candidates": competition_candidates,
        "shared_competition_candidates": shared,
        "duplicate_competition_candidates": duplicates,
        "season_candidates": seasons,
        "team_candidates": teams,
        "summary": {
            "competition_source_rows": len(competition_candidates),
            "competition_identity_keys_candidate": sum(
                bool(row.get("identity_key_candidate")) for row in competition_candidates
            ),
            "shared_competition_identity_candidates": len(shared),
            "duplicate_competition_identity_candidates": len(duplicates),
            "seasons_held_for_parent_approval": sum(
                row.get("status") == "held_until_parent_competition_is_approved"
                for row in seasons
            ),
            "seasons_with_approved_parent_candidate": sum(
                row.get("status") == "season_key_candidate_parent_approved_review_required"
                for row in seasons
            ),
            "seasons_with_complete_date_range": sum(
                row.get("season_date_range_status") == "complete" for row in seasons
            ),
            "seasons_with_incomplete_date_range": sum(
                row.get("season_date_range_status") == "incomplete" for row in seasons
            ),
            "seasons_with_date_label_requiring_normalization": sum(
                row.get("date_normalized_season_label_candidate")
                and str(row.get("season_label")) != str(row.get("date_normalized_season_label_candidate"))
                for row in seasons
            ),
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
        "start_date", "end_date", "team_type", "gender_scope", "age_group", "squad_scope",
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
            cursor.execute(
                """SELECT link.provider, link.provider_entity_id, link.canonical_entity_id
                   FROM provider_entity_links AS link
                   WHERE link.entity_type = 'league'
                     AND (
                       (link.provider = 'sportmonks'
                        AND link.canonical_entity_id = 'sportmonks:' || link.provider_entity_id)
                       OR EXISTS (
                         SELECT 1
                         FROM provider_entity_link_approval_audit AS approval
                         WHERE approval.link_id = link.link_id
                           AND approval.provider = link.provider
                           AND approval.entity_type = link.entity_type
                           AND approval.provider_entity_id = link.provider_entity_id
                           AND approval.canonical_entity_id = link.canonical_entity_id
                           AND LENGTH(BTRIM(approval.approval_reason)) >= 12
                       )
                     )
                   ORDER BY link.provider, link.provider_entity_id"""
            )
            approved_parent_links = {
                (str(provider).casefold(), str(provider_id)): str(canonical_id)
                for provider, provider_id, canonical_id in cursor.fetchall()
            }
    report = build_identity_candidate_report(rows, approved_parent_links)
    report["approved_parent_competition_links_read"] = len(approved_parent_links)
    report["database_read_only"] = True
    report["source_rows_read"] = len(rows)
    report["database_writes"] = False
    return report
