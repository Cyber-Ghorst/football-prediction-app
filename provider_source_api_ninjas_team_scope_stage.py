"""Stage current API Ninjas club-catalogue scope as provider source evidence only.

The provider documents country (ISO alpha-2), team_type (club/national), and
gender (men/women). Values are copied exactly; country codes are not silently
converted to country names, and missing age/squad scope is not inferred.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from api_ninjas import APINinjasClient
from provider_source_repository import store_provider_source_bundle

TARGETS = (
    {"league": "epl", "name": "Premier League"},
    {"league": "laliga", "name": "La Liga"},
    {"league": "bundesliga", "name": "Bundesliga"},
    {"league": "seriea", "name": "Serie A"},
    {"league": "ligue1", "name": "Ligue 1"},
)
REPORT = Path("provider-source-api-ninjas-team-scope-stage-report.json")
TEAM_TYPES = {"club", "national"}
GENDERS = {"men", "women"}


def build_source_entities(
    catalogues: list[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    held: list[dict[str, Any]] = []
    for catalogue in catalogues:
        league = str(catalogue.get("league") or "").strip().casefold()
        for team in catalogue.get("teams") or []:
            if not isinstance(team, Mapping):
                continue
            team_id = str(team.get("team_id") or "").strip()
            name = str(team.get("name") or "").strip()
            country_code = str(team.get("country") or "").strip().upper()
            team_type = str(team.get("team_type") or "").strip().casefold()
            gender = str(team.get("gender") or "").strip().casefold()
            active = team.get("active")
            missing = [
                field for field, value in (
                    ("team_id", team_id), ("name", name),
                    ("country_iso2", country_code), ("team_type", team_type),
                    ("gender", gender),
                ) if not value
            ]
            if missing:
                held.append({
                    "league": league, "provider_entity_id": team_id or None,
                    "name": name or None, "reason": "missing_explicit_provider_fields",
                    "missing_fields": missing,
                })
                continue
            if len(country_code) != 2 or not country_code.isalpha():
                held.append({
                    "league": league, "provider_entity_id": team_id,
                    "reason": "country_is_not_iso_alpha2",
                    "country_value": team.get("country"),
                })
                continue
            if team_type not in TEAM_TYPES or gender not in GENDERS:
                held.append({
                    "league": league, "provider_entity_id": team_id,
                    "reason": "unrecognized_provider_team_scope",
                    "team_type": team_type, "gender": gender,
                })
                continue
            if active is not True:
                held.append({
                    "league": league, "provider_entity_id": team_id,
                    "reason": "team_not_explicitly_active",
                    "active_value": active,
                })
                continue
            candidate = {
                "entity_type": "team",
                "provider_entity_id": team_id,
                "name": name,
                # API Ninjas documents this as ISO 3166-1 alpha-2. Keep it
                # exact rather than converting it to a potentially ambiguous
                # country/territory display label.
                "country": country_code,
                "team_type": team_type,
                "gender_scope": gender,
                "raw_payload": {
                    "source": "API Ninjas current soccerclubs catalogue",
                    "country_code_iso3166_alpha2": country_code,
                    "team_type_from_provider": team_type,
                    "gender_from_provider": gender,
                    "active_from_provider": active,
                    "domestic_league_codes": [league] if league else [],
                    "raw_team": dict(team),
                },
            }
            existing = by_id.get(team_id)
            if existing is None:
                by_id[team_id] = candidate
                continue
            comparable = ("name", "country", "team_type", "gender_scope")
            conflicts = {
                field: {"first": existing[field], "later": candidate[field]}
                for field in comparable if existing[field] != candidate[field]
            }
            if conflicts:
                by_id.pop(team_id, None)
                held.append({
                    "provider_entity_id": team_id,
                    "reason": "conflicting_duplicate_team_catalogue_records",
                    "conflicts": conflicts,
                })
                continue
            leagues = set(existing["raw_payload"]["domestic_league_codes"])
            leagues.update(candidate["raw_payload"]["domestic_league_codes"])
            existing["raw_payload"]["domestic_league_codes"] = sorted(leagues)
    return [by_id[key] for key in sorted(by_id)], held


def collect_catalogues(client_factory=APINinjasClient) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    client = client_factory()
    catalogues = []
    outcomes = []
    try:
        for target in TARGETS:
            try:
                teams = client.clubs(league=target["league"])
                catalogues.append({"league": target["league"], "teams": teams})
                outcomes.append({
                    "league": target["league"], "status": "collected",
                    "team_rows": len(teams), "rate_limit": dict(client.last_metadata),
                })
            except Exception as exc:
                outcomes.append({
                    "league": target["league"], "status": "provider_error",
                    "reason": str(exc)[:300], "rate_limit": dict(client.last_metadata),
                })
    finally:
        client.close()
    return catalogues, {"competition_outcomes": outcomes}


def stage_api_ninjas_team_scope(database_url: str, client_factory=APINinjasClient) -> dict[str, Any]:
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    catalogues, collection = collect_catalogues(client_factory)
    entities, held = build_source_entities(catalogues)
    counts = store_provider_source_bundle(
        database_url, "api_ninjas", entities=entities,
        write_scope="provider_source_evidence_only",
    ) if entities else {"entities": 0, "fixtures": 0, "statistics": 0}
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "provider": "api_ninjas",
        "write_scope": "provider_source_evidence_only",
        **collection,
        "team_rows_received": sum(len(row.get("teams") or []) for row in catalogues),
        "source_entities_written": counts["entities"],
        "team_rows_held": len(held),
        "held_samples": held[:30],
        "country_code_counts": dict(sorted(Counter(row["country"] for row in entities).items())),
        "team_type_counts": dict(sorted(Counter(row["team_type"] for row in entities).items())),
        "gender_counts": dict(sorted(Counter(row["gender_scope"] for row in entities).items())),
        "age_group_scope_written": False,
        "squad_scope_written": False,
        "country_code_normalization_performed": False,
        "canonical_entities_written": 0,
        "provider_links_written": 0,
        "fixtures_written": 0,
        "predictions_written": 0,
        "prediction_ledger_touched": False,
        "interpretation": (
            "Only active provider team records with explicit ID, name, ISO alpha-2 country, "
            "team_type and gender are staged. ISO country codes are retained exactly; no "
            "country display-name mapping, age-group, squad scope or cross-provider identity "
            "is inferred."
        ),
    }


def main() -> int:
    report = stage_api_ninjas_team_scope(
        os.getenv("PROVIDER_DATABASE_URL", "").strip()
    )
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\\n",
                      encoding="utf-8")
    print(json.dumps({
        key: report[key] for key in (
            "checked_at", "provider", "write_scope", "competition_outcomes",
            "team_rows_received", "source_entities_written", "team_rows_held",
            "country_code_counts", "team_type_counts", "gender_counts",
            "canonical_entities_written", "provider_links_written",
            "prediction_ledger_touched",
        )
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
