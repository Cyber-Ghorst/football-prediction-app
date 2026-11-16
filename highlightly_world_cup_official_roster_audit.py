"""Read-only Highlightly/FIFA World Cup 2026 national-team roster audit."""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from highlightly import HighlightlyClient
from provider_entity_crosswalk import normalize_entity_name

REPORT = Path("highlightly-world-cup-2026-official-roster-audit.json")
HIGHLIGHTLY_COMPETITION_ID = "1635"
SEASON = "2026"
SOURCE_ROSTER_RUN_ID = "43760784223"
SOURCE_ROSTER_CHECKED_AT = "2026-11-15T20:55:52.827086+00:00"
SOURCE_MATCHES_EXAMINED = 104

HIGHLIGHTLY_PARTICIPANTS = (
    ("10145", "Panama"), ("10996", "Japan"), ("11847", "Senegal"),
    ("1278135", "Ivory Coast"), ("1280688", "Ghana"), ("1284092", "Congo DR"),
    ("1303665", "South Africa"), ("1304516", "Algeria"), ("1305367", "Cape Verde"),
    ("1318132", "Jordan"), ("1334301", "Iraq"), ("1335152", "Uzbekistan"),
    ("1336003", "Qatar"), ("13549", "Switzerland"), ("14400", "Mexico"),
    ("15251", "South Korea"), ("1635", "Belgium"), ("17804", "Australia"),
    ("19506", "Iran"), ("2026164", "Paraguay"), ("2027866", "Ecuador"),
    ("2029568", "USA"), ("2031270", "Haiti"), ("20357", "Saudi Arabia"),
    ("22059", "Germany"), ("22910", "Argentina"), ("23761", "Portugal"),
    ("24612", "Tunisia"), ("2486", "France"), ("27165", "Morocco"),
    ("28016", "Egypt"), ("3337", "Croatia"), ("3977507", "New Zealand"),
    ("4705963", "Canada"), ("4706814", "Curaçao"), ("5039", "Sweden"),
    ("5890", "Brazil"), ("656054", "Czech Republic"), ("660309", "Austria"),
    ("662011", "Turkey"), ("6741", "Uruguay"), ("7592", "Colombia"),
    ("8443", "Spain"), ("928374", "Norway"), ("9294", "England"),
    ("943692", "Scotland"), ("947947", "Bosnia & Herzegovina"),
    ("952202", "Netherlands"),
)

FIFA_OFFICIAL_TEAMS = (
    "Canada", "Mexico", "USA", "Australia", "Iraq", "IR Iran", "Japan",
    "Jordan", "Korea Republic", "Qatar", "Saudi Arabia", "Uzbekistan",
    "Algeria", "Cabo Verde", "Congo DR", "Côte d'Ivoire", "Egypt", "Ghana",
    "Morocco", "Senegal", "South Africa", "Tunisia", "Curaçao", "Haiti",
    "Panama", "Argentina", "Brazil", "Colombia", "Ecuador", "Paraguay",
    "Uruguay", "New Zealand", "Austria", "Belgium", "Bosnia and Herzegovina",
    "Croatia", "Czechia", "England", "France", "Germany", "Netherlands",
    "Norway", "Portugal", "Scotland", "Spain", "Sweden", "Switzerland",
    "Türkiye",
)

OFFICIAL_NAME_ALIASES = {
    "Ivory Coast": "Côte d'Ivoire",
    "Cape Verde": "Cabo Verde",
    "South Korea": "Korea Republic",
    "Iran": "IR Iran",
    "Czech Republic": "Czechia",
    "Turkey": "Türkiye",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
}
FIFA_REFERENCE_URL = (
    "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/"
    "articles/fifa-world-cup-2026-hosts-cities-dates-usa-mexico-canada"
)


def _team_record(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, Mapping)]
    elif isinstance(payload, Mapping):
        data = payload.get("data")
        if isinstance(data, list):
            rows = [row for row in data if isinstance(row, Mapping)]
        elif payload.get("id") is not None:
            rows = [payload]
        else:
            rows = []
    else:
        rows = []
    return dict(rows[0]) if len(rows) == 1 else None


def build_official_matches() -> list[dict[str, Any]]:
    official_by_normalized = {
        normalize_entity_name(name): name for name in FIFA_OFFICIAL_TEAMS
    }
    rows = []
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    for provider_id, provider_name in HIGHLIGHTLY_PARTICIPANTS:
        if provider_id in seen_ids or normalize_entity_name(provider_name) in seen_names:
            raise ValueError("Duplicate Highlightly World Cup provider ID or team name.")
        seen_ids.add(provider_id)
        seen_names.add(normalize_entity_name(provider_name))
        official_name = OFFICIAL_NAME_ALIASES.get(provider_name, provider_name)
        matched_official = official_by_normalized.get(normalize_entity_name(official_name))
        rows.append({
            "highlightly_team_id": provider_id,
            "highlightly_team_name": provider_name,
            "fifa_official_team_name": matched_official,
            "name_match_method": (
                "explicit_official_name_alias" if provider_name in OFFICIAL_NAME_ALIASES
                else "exact_normalized_official_name"
            ),
            "official_roster_match": matched_official is not None,
        })
    return rows


def verify_provider_detail(expected_id: str, expected_name: str, payload: Any) -> dict[str, Any]:
    record = _team_record(payload)
    if record is None:
        return {"status": "held_missing_or_ambiguous_provider_detail"}
    returned_id = str(record.get("id") or "")
    returned_name = str(record.get("name") or "")
    returned_type = str(record.get("type") or "").strip().casefold()
    checks = {
        "provider_id_matches": returned_id == expected_id,
        "provider_name_matches": normalize_entity_name(returned_name) == normalize_entity_name(expected_name),
        "provider_type_is_national": returned_type == "national",
    }
    return {
        "status": "provider_detail_confirmed" if all(checks.values()) else "held_provider_detail_mismatch",
        "returned_id": returned_id,
        "returned_name": returned_name,
        "returned_type": returned_type or None,
        "country_field_available": bool(record.get("country")),
        "country_value": record.get("country"),
        "checks": checks,
        "raw_detail": record,
    }


def audit_world_cup_roster(client_factory=HighlightlyClient) -> dict[str, Any]:
    matches = build_official_matches()
    results = []
    with client_factory() as client:
        for row in matches:
            item = dict(row)
            try:
                payload = client._get(f"teams/{row['highlightly_team_id']}")
                item["provider_detail"] = verify_provider_detail(
                    row["highlightly_team_id"], row["highlightly_team_name"], payload
                )
            except Exception as exc:
                item["provider_detail"] = {
                    "status": "provider_request_failed",
                    "error_type": type(exc).__name__,
                }
            official_match = item["official_roster_match"]
            provider_detail_ok = item["provider_detail"].get("status") == "provider_detail_confirmed"
            item["scope_candidate"] = (
                {
                    "team_type": "national",
                    "gender_scope": "male",
                    "age_group": "senior",
                    "squad_scope": "national_team",
                } if official_match and provider_detail_ok else None
            )
            item["promotion_allowed"] = False
            item["cross_provider_identity_status"] = "not_assessed_no_independent_provider_catalogue"
            results.append(item)
    return {
        "operation": "highlightly_world_cup_2026_official_roster_audit",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "database_touched": False,
        "canonical_ids_assigned": 0,
        "provider_links_created": 0,
        "fixtures_imported": 0,
        "prediction_ledger_touched": False,
        "prediction_model_modified": False,
        "competition": {
            "highlightly_competition_id": HIGHLIGHTLY_COMPETITION_ID,
            "highlightly_competition_name": "World Cup",
            "season": SEASON,
            "official_competition_name": "FIFA World Cup 2026",
            "official_reference_url": FIFA_REFERENCE_URL,
            "official_team_count": len(FIFA_OFFICIAL_TEAMS),
            "provider_source_roster_run_id": SOURCE_ROSTER_RUN_ID,
            "provider_source_roster_checked_at": SOURCE_ROSTER_CHECKED_AT,
            "provider_matches_examined": SOURCE_MATCHES_EXAMINED,
            "provider_roster_method": "season_match_participants",
        },
        "provider_participant_count": len(HIGHLIGHTLY_PARTICIPANTS),
        "unique_provider_team_ids": len({row["highlightly_team_id"] for row in results}),
        "official_roster_matches": sum(row["official_roster_match"] for row in results),
        "official_roster_unmatched": [
            row for row in results if not row["official_roster_match"]
        ],
        "provider_detail_status_counts": dict(Counter(
            row["provider_detail"]["status"] for row in results
        )),
        "official_name_alias_count": sum(
            row["name_match_method"] == "explicit_official_name_alias" for row in results
        ),
        "scope_candidate_count": sum(row["scope_candidate"] is not None for row in results),
        "scope_basis": (
            "FIFA identifies the competition as the senior men's FIFA World Cup and lists "
            "all 48 participating national teams; Highlightly's own team detail must also "
            "confirm type=national before a national-team scope candidate is emitted."
        ),
        "limitations": [
            "LiveScoreFootball's audited competition catalogue contains no World Cup competition; no independent provider team IDs are available for cross-provider identity matching.",
            "FIFA roster matching confirms the official team set, not that provider IDs are interchangeable with another provider's IDs.",
            "No country is inferred from the team name; missing country fields remain missing.",
        ],
        "results": results,
    }


def main() -> int:
    report = audit_world_cup_roster()
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
                      encoding="utf-8")
    print(json.dumps({
        "checked_at_utc": report["checked_at_utc"],
        "read_only": report["read_only"],
        "provider_participant_count": report["provider_participant_count"],
        "official_roster_matches": report["official_roster_matches"],
        "provider_detail_status_counts": report["provider_detail_status_counts"],
        "scope_candidate_count": report["scope_candidate_count"],
        "canonical_ids_assigned": 0,
        "provider_links_created": 0,
        "report": str(REPORT),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
