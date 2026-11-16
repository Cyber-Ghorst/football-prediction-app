"""Read-only identity candidate audit across staged provider source entities.

Candidate keys are not canonical IDs. This module never persists identities,
approves links, or compares provider IDs as if they were globally unique.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from provider_data_storage import _connect
from provider_season_provenance import is_verified_2026_27_snapshot
from provider_neutral_identity import (
    canonical_competition_key,
    canonical_season_key,
    canonical_team_key,
)



# Reviewed official 2026/27 competition references for source rows whose
# provider payload omits country and/or competition_type. This is candidate-view
# evidence only; provider source rows and identity links remain unchanged.
OFFICIAL_COMPETITION_IDENTITY_EVIDENCE = {
    ("highlightly", "33973"): {
        "competition_type": "league",
        "official_reference_urls": ("https://www.premierleague.com/en/news/4365156",),
    },
    ("highlightly", "119924"): {
        "competition_type": "league",
        "official_reference_urls": ("https://www.laliga.com/en-US/laliga-easports/clubs",),
    },
    ("highlightly", "115669"): {
        "competition_type": "league",
        "official_reference_urls": ("https://www.legaseriea.it/serie-a/statistiche/clubs",),
    },
    ("highlightly", "67162"): {
        "competition_type": "league",
        "official_reference_urls": ("https://www.bundesliga.com/en/bundesliga/clubs",),
    },
    ("highlightly", "52695"): {
        "competition_type": "league",
        "official_reference_urls": ("https://ligue1.com/en/articles/l1_article_5292-",),
    },
    ("livescore_football", "ger.1"): {
        "competition_type": "league",
        "identity_name": "Bundesliga",
        "official_reference_urls": ("https://www.bundesliga.com/en/bundesliga/clubs",),
    },
    ("livescore_football", "fra.1"): {
        "competition_type": "league",
        "identity_name": "Ligue 1",
        "official_reference_urls": ("https://ligue1.com/en/articles/l1_article_5292-",),
    },
    # API Ninjas exposes these provider-native competition slugs without
    # country/type metadata. The explicit slug-to-official-reference mapping
    # is used only to build review candidates; it does not approve a link.
    ("api_ninjas", "epl"): {
        "country": "England",
        "competition_type": "league",
        "official_reference_urls": ("https://www.premierleague.com/en/tables/premier-league/2026-27?ha=H",),
    },
    ("api_ninjas", "laliga"): {
        "country": "Spain",
        "competition_type": "league",
        "official_reference_urls": ("https://www.laliga.com/en-ES/laliga-easports/standing",),
    },
    ("api_ninjas", "seriea"): {
        "country": "Italy",
        "competition_type": "league",
        "official_reference_urls": ("https://en.legaseriea.it/serie-a/standings?app_v1=true",),
    },
    ("api_ninjas", "ligue1"): {
        "country": "France",
        "competition_type": "league",
        "official_reference_urls": ("https://ligue1.com/fr?seasonId=13C03A251F7A47EBB850BCAD920E9E51",),
    },
    ("api_ninjas", "bundesliga"): {
        "country": "Germany",
        "competition_type": "league",
        "official_reference_urls": ("https://www.bundesliga.com/en/bundesliga/table",),
    },
}

def _missing(row: Mapping[str, Any], fields: tuple[str, ...]) -> list[str]:
    return [field for field in fields if not str(row.get(field) or "").strip()]


def _date_value(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    text = str(value).strip()
    return text or None


# Official 2026/27 first/last matchday boundaries. These fill missing
# season dates in the read-only candidate view only; provider source rows
# and canonical season links remain unchanged.
OFFICIAL_2026_27_SEASON_DATE_EVIDENCE = {
    ("api_ninjas", "epl"): {
        "start_date": "2026-08-21", "end_date": "2027-05-30",
        "official_reference_urls": ("https://www.premierleague.com/en/news/4468487/dates-for-202627-premier-league-season-confirmed",),
    },
    ("highlightly", "33973"): {
        "start_date": "2026-08-21", "end_date": "2027-05-30",
        "official_reference_urls": ("https://www.premierleague.com/en/news/4468487/dates-for-202627-premier-league-season-confirmed",),
    },
    ("api_ninjas", "laliga"): {
        "start_date": "2026-08-14", "end_date": "2027-05-30",
        "official_reference_urls": (
            "https://www.laliga.com/noticias/ya-se-conoce-el-calendario-al-completo-de-laliga-easports-2026-27",
            "https://en.atleticodemadrid.com/noticias/our-2026-27-league-fixture-list-has-been-confirmed",
        ),
    },
    ("highlightly", "119924"): {
        "start_date": "2026-08-14", "end_date": "2027-05-30",
        "official_reference_urls": (
            "https://www.laliga.com/noticias/ya-se-conoce-el-calendario-al-completo-de-laliga-easports-2026-27",
            "https://en.atleticodemadrid.com/noticias/our-2026-27-league-fixture-list-has-been-confirmed",
        ),
    },
    ("api_ninjas", "seriea"): {
        "start_date": "2026-08-22", "end_date": "2027-05-30",
        "official_reference_urls": ("https://en.legaseriea.it/serie-a/news/looking-forward-to-the-2026-27-serie-a-fixture-list",),
    },
    ("highlightly", "115669"): {
        "start_date": "2026-08-22", "end_date": "2027-05-30",
        "official_reference_urls": ("https://en.legaseriea.it/serie-a/news/looking-forward-to-the-2026-27-serie-a-fixture-list",),
    },
    ("api_ninjas", "bundesliga"): {
        "start_date": "2026-08-28", "end_date": "2027-05-22",
        "official_reference_urls": ("https://www.bundesliga.com/en/bundesliga/news/calendar-for-2026-27-season-world-cup-34676",),
    },
    ("highlightly", "67162"): {
        "start_date": "2026-08-28", "end_date": "2027-05-22",
        "official_reference_urls": ("https://www.bundesliga.com/en/bundesliga/news/calendar-for-2026-27-season-world-cup-34676",),
    },
    ("api_ninjas", "ligue1"): {
        "start_date": "2026-08-21", "end_date": "2027-05-29",
        "official_reference_urls": ("https://ligue1.com/en/articles/l1_article_5292-the-2026-27-ligue-1-mc-donald-s-calendar-is-released",),
    },
    ("highlightly", "52695"): {
        "start_date": "2026-08-21", "end_date": "2027-05-29",
        "official_reference_urls": ("https://ligue1.com/en/articles/l1_article_5292-the-2026-27-ligue-1-mc-donald-s-calendar-is-released",),
    },
}


def _season_date_fields(
    row: Mapping[str, Any], provider: str, provider_parent_id: str, season_label: Any,
) -> dict[str, Any]:
    source_start = _date_value(row.get("start_date"))
    source_end = _date_value(row.get("end_date"))
    result = {"start_date": source_start, "end_date": source_end}
    label = str(season_label or "").strip()
    is_2026_27 = label in {"2026", "2026/27", "2026/2027", "2026-27"}
    evidence = (
        OFFICIAL_2026_27_SEASON_DATE_EVIDENCE.get((provider, provider_parent_id), {})
        if is_2026_27 else {}
    )
    if not evidence:
        result["season_date_range_status"] = (
            "complete" if source_start and source_end else "incomplete"
        )
        return result
    missing_source_dimensions = []
    if not source_start:
        result["start_date"] = evidence["start_date"]
        missing_source_dimensions.append("start_date")
    if not source_end:
        result["end_date"] = evidence["end_date"]
        missing_source_dimensions.append("end_date")
    result["season_date_range_status"] = (
        "complete" if result["start_date"] and result["end_date"] else "incomplete"
    )
    if missing_source_dimensions:
        result["season_date_evidence_source"] = "official_competition_calendar"
        result["season_date_evidence_season_label"] = "2026/27"
        result["season_date_source_missing_dimensions"] = missing_source_dimensions
        result["season_date_official_reference_urls"] = list(
            evidence["official_reference_urls"]
        )
    return result


# Target scope for the active 2026/27 Layer 12 review. These are
# provider-native parent competition IDs mapped to the already-reviewed
# competition names. This classification is diagnostic only; it does not
# approve parent links or season identities.
TARGET_2026_27_COMPETITION_PARENTS = {
    ("api_football", "39"): "Premier League",
    ("api_football", "140"): "La Liga",
    ("api_football", "135"): "Serie A",
    ("api_football", "61"): "Ligue 1",
    ("api_football", "78"): "Bundesliga",
    ("api_ninjas", "epl"): "Premier League",
    ("api_ninjas", "laliga"): "La Liga",
    ("api_ninjas", "seriea"): "Serie A",
    ("api_ninjas", "ligue1"): "Ligue 1",
    ("api_ninjas", "bundesliga"): "Bundesliga",
    ("highlightly", "33973"): "Premier League",
    ("highlightly", "119924"): "La Liga",
    ("highlightly", "115669"): "Serie A",
    ("highlightly", "52695"): "Ligue 1",
    ("highlightly", "67162"): "Bundesliga",
    ("sportmonks", "8"): "Premier League",
    ("sportmonks", "564"): "La Liga",
    ("sportmonks", "384"): "Serie A",
    ("sportmonks", "567"): "La Liga 2",
}
TARGET_2026_27_COMPETITION_NAMES = {
    "premier league", "la liga", "serie a", "ligue 1", "bundesliga"
}


def _target_season_review_fields(
    provider: str, provider_parent_id: str, season_label: Any,
) -> dict[str, Any]:
    """Classify whether a row belongs to the active season and target leagues."""
    label = str(season_label or "").strip()
    current_season = label in {"2026", "2026/27", "2026/2027", "2026-27"}
    competition_name = TARGET_2026_27_COMPETITION_PARENTS.get(
        (provider, provider_parent_id)
    )
    competition_in_scope = bool(
        competition_name
        and competition_name.casefold() in TARGET_2026_27_COMPETITION_NAMES
    )
    if not current_season:
        status = "held_outside_target_season"
    elif not competition_name:
        status = "held_unverified_target_competition"
    elif not competition_in_scope:
        status = "held_outside_target_competition"
    else:
        status = "eligible_for_exact_evidence_review"
    return {
        "target_season_label": "2026/27",
        "target_season_scope": "current_target_season" if current_season else "outside_target_season",
        "target_competition_name_candidate": competition_name,
        "target_competition_scope": (
            "in_target_competition" if competition_in_scope
            else "outside_or_unverified_target_competition"
        ),
        "target_season_review_status": status,
    }


def build_identity_candidate_report(
    rows: list[Mapping[str, Any]],
    approved_parent_links: Mapping[tuple[str, str], str] | None = None,
    approved_team_scope_corroborations: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create candidate keys using source and approved corroborated scope evidence."""
    competition_candidates = []
    seasons = []
    teams = []
    key_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    approved_parents = dict(approved_parent_links or {})
    approved_team_scope = dict(approved_team_scope_corroborations or {})

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
            effective_row = dict(row)
            source_missing = _missing(row, required)
            evidence = OFFICIAL_COMPETITION_IDENTITY_EVIDENCE.get((provider, provider_id), {})
            corroborated_dimensions = []
            if not str(effective_row.get("competition_type") or "").strip():
                value = str(evidence.get("competition_type") or "").strip()
                if value:
                    effective_row["competition_type"] = value
                    corroborated_dimensions.append("competition_type")
            if not str(effective_row.get("country") or "").strip():
                value = str(evidence.get("country") or "").strip()
                if value:
                    effective_row["country"] = value
                    corroborated_dimensions.append("country")
            identity_name = str(evidence.get("identity_name") or effective_row.get("name") or "").strip()
            if evidence.get("identity_name"):
                corroborated_dimensions.append("name_variant")
            missing = _missing(effective_row, required)
            evidence_fields = {
                "source_missing_dimensions": source_missing,
                "corroborated_dimensions": sorted(corroborated_dimensions),
                "identity_key_candidate": None,
            }
            if corroborated_dimensions:
                evidence_fields["scope_evidence_source"] = "official_competition_reference"
                evidence_fields["official_reference_urls"] = list(
                    evidence.get("official_reference_urls", ())
                )
                evidence_fields["identity_name_candidate"] = identity_name
            if missing:
                result = {**base, **evidence_fields,
                          "status": "held_missing_identity_dimensions",
                          "missing_dimensions": missing}
            else:
                key = canonical_competition_key(
                    identity_name, effective_row.get("country"),
                    effective_row.get("competition_type")
                )
                result = {**base, **evidence_fields,
                          "country": effective_row.get("country"),
                          "competition_type": effective_row.get("competition_type"),
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
            season_date_fields = _season_date_fields(
                row, provider, provider_parent_id, season_label
            )
            canonical_parent_id = approved_parents.get((provider, provider_parent_id))
            if not canonical_parent_id:
                result = {
                    **base,
                    "provider_parent_competition_id": provider_parent_id or None,
                    "season_label": season_label,
                    **season_date_fields,
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
                        "start_date": _date_value(row.get("start_date")),
                        "end_date": _date_value(row.get("end_date")),
                        "season_date_range_status": (
                            "complete" if row.get("start_date") and row.get("end_date")
                            else "incomplete"
                        ),
                        "status": "season_key_candidate_parent_approved_review_required",
                        "identity_key_candidate": season_key,
                        "reason": (
                            "Parent competition is approved; this deterministic season key is "
                            "only a candidate. Exact season evidence is still required before "
                            "any season provider link can be approved."
                        ),
                    }
            result.update(_target_season_review_fields(
                provider, provider_parent_id, season_label
            ))
            seasons.append(result)

        elif entity_type == "team":
            required = ("name", "country", "team_type", "gender_scope", "age_group", "squad_scope")
            effective_row = dict(row)
            source_missing = _missing(row, required)
            corroboration = approved_team_scope.get((provider, provider_id), {})
            corroborated_dimensions = []
            # Approved corroborations may fill only absent source dimensions.
            # They never overwrite provider-native values and cannot supply
            # age-group or squad scope, which remain independently required.
            for field in ("country", "team_type", "gender_scope"):
                if str(effective_row.get(field) or "").strip():
                    continue
                value = str(corroboration.get(field) or "").strip()
                if value:
                    effective_row[field] = value
                    corroborated_dimensions.append(field)
            missing = _missing(effective_row, required)
            evidence_fields = {
                "source_missing_dimensions": source_missing,
                "corroborated_dimensions": sorted(corroborated_dimensions),
                "identity_key_candidate": None,
            }
            if corroborated_dimensions:
                evidence_fields["scope_evidence_source"] = "provider_team_scope_corroborations"
            if missing:
                result = {
                    **base, **evidence_fields, "status": "held_missing_team_scope",
                    "missing_dimensions": missing,
                }
            else:
                try:
                    key = canonical_team_key(
                        effective_row.get("name"), effective_row.get("country"),
                        effective_row.get("team_type"), effective_row.get("gender_scope"),
                        effective_row.get("age_group"), effective_row.get("squad_scope"),
                    )
                except ValueError as exc:
                    result = {**base, **evidence_fields, "status": "held_invalid_team_scope",
                              "reason": str(exc)}
                else:
                    result = {**base, **evidence_fields, "status": "single_source_identity_candidate",
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
            "competitions_with_official_type_corroboration": sum(
                "competition_type" in row.get("corroborated_dimensions", [])
                for row in competition_candidates
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
            "seasons_current_target_season": sum(
                row.get("target_season_scope") == "current_target_season" for row in seasons
            ),
            "seasons_outside_target_season": sum(
                row.get("target_season_scope") == "outside_target_season" for row in seasons
            ),
            "seasons_in_target_competition_scope": sum(
                row.get("target_competition_scope") == "in_target_competition" for row in seasons
            ),
            "seasons_outside_or_unverified_target_competition": sum(
                row.get("target_competition_scope") == "outside_or_unverified_target_competition"
                for row in seasons
            ),
            "seasons_eligible_for_exact_evidence_review": sum(
                row.get("target_season_review_status") == "eligible_for_exact_evidence_review"
                for row in seasons
            ),
            "team_source_rows": len(teams),
            "teams_with_approved_scope_corroboration": sum(
                bool(row.get("corroborated_dimensions")) for row in teams
            ),
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
            cursor.execute(
                """SELECT provider, provider_entity_id, country_name, team_type,
                          gender_scope, evidence_snapshot
                   FROM provider_team_scope_corroborations
                   WHERE LENGTH(BTRIM(approval_reason)) >= 12
                   ORDER BY provider, provider_entity_id, corroborating_provider,
                            corroborating_entity_id, competition_provider_id"""
            )
            corroboration_rows = cursor.fetchall()
    corroboration_values: dict[tuple[str, str], set[tuple[str, str, str]]] = defaultdict(set)
    legacy_provisional_scope_corroborations_ignored = 0
    verified_scope_corroborations_read = 0
    for provider, provider_id, country_name, team_type, gender_scope, evidence_snapshot in corroboration_rows:
        if not is_verified_2026_27_snapshot(evidence_snapshot):
            legacy_provisional_scope_corroborations_ignored += 1
            continue
        verified_scope_corroborations_read += 1
        corroboration_values[(str(provider).casefold(), str(provider_id))].add(
            (str(country_name or "").strip(), str(team_type or "").strip(),
             str(gender_scope or "").strip())
        )
    approved_team_scope_corroborations = {
        key: {"country": values[0], "team_type": values[1], "gender_scope": values[2]}
        for key, records in corroboration_values.items()
        if len(records) == 1
        for values in [next(iter(records))]
        if all(values)
    }
    conflicting_team_scope_corroborations = [
        {"provider": key[0], "provider_entity_id": key[1], "record_count": len(records)}
        for key, records in corroboration_values.items() if len(records) > 1
    ]
    report = build_identity_candidate_report(
        rows, approved_parent_links, approved_team_scope_corroborations
    )
    report["approved_parent_competition_links_read"] = len(approved_parent_links)
    report["approved_team_scope_corroborations_read"] = verified_scope_corroborations_read
    report["legacy_provisional_scope_corroborations_ignored"] = (
        legacy_provisional_scope_corroborations_ignored
    )
    report["team_scope_corroboration_conflicts"] = conflicting_team_scope_corroborations
    report["database_read_only"] = True
    report["source_rows_read"] = len(rows)
    report["database_writes"] = False
    return report
