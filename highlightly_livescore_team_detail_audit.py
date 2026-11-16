"""Read-only provider-native detail audit for exact Highlightly/LiveScore club candidates.

This audit verifies each provider-local team ID against that provider's own
team/club detail endpoint and records 2026/27 competition evidence. It never
creates canonical identities, provider links, fixtures, or scope approvals.
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from highlightly import HighlightlyClient
from livescore_football import LiveScoreFootballClient
from provider_data_storage import _connect
from provider_entity_crosswalk import normalize_entity_name

REPORT = Path("highlightly-livescore-team-detail-audit.json")
SEASON_YEAR = "2026"
SEASON_LABEL = "2026/27"
TARGETS = (
    {"highlightly_competition_id": "67162", "livescore_competition_id": "ger.1",
     "livescore_name": "German Bundesliga", "country": "Germany"},
    {"highlightly_competition_id": "52695", "livescore_competition_id": "fra.1",
     "livescore_name": "French Ligue 1", "country": "France"},
)


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, Mapping) else {}
    return {}


def _highlightly_team_record(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, Mapping)]
    elif isinstance(payload, Mapping):
        data = payload.get("data")
        if isinstance(data, list):
            rows = [row for row in data if isinstance(row, Mapping)]
        elif isinstance(payload.get("team"), Mapping):
            rows = [payload["team"]]
        elif payload.get("id") is not None:
            rows = [payload]
        else:
            rows = []
    else:
        rows = []
    return dict(rows[0]) if len(rows) == 1 else None


def build_exact_candidates(
    highlightly_rows: list[Mapping[str, Any]],
    livescore_rows: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Join only unique exact normalized names within matching 2026/27 competitions."""
    output = []
    for target in TARGETS:
        h_by_name: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        l_by_name: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in highlightly_rows:
            raw = _mapping(row.get("raw_payload"))
            if target["highlightly_competition_id"] not in {
                str(x) for x in raw.get("competition_provider_ids", [])
            }:
                continue
            if str(raw.get("season_label") or "") != SEASON_LABEL:
                continue
            name_key = normalize_entity_name(row.get("name"))
            if name_key:
                h_by_name[name_key].append(row)
        for row in livescore_rows:
            if str(row.get("competition_provider_id") or "") != target["livescore_competition_id"]:
                continue
            if str(row.get("season_label") or "") != SEASON_LABEL:
                continue
            if row.get("evidence_complete") is not True:
                continue
            name_key = normalize_entity_name(row.get("team_name"))
            if name_key:
                l_by_name[name_key].append(row)
        for name_key in sorted(set(h_by_name) & set(l_by_name)):
            left, right = h_by_name[name_key], l_by_name[name_key]
            if len(left) != 1 or len(right) != 1:
                continue
            h, live = left[0], right[0]
            output.append({
                "competition": target["livescore_name"],
                "country_context": target["country"],
                "highlightly_competition_id": target["highlightly_competition_id"],
                "livescore_competition_id": target["livescore_competition_id"],
                "highlightly_team_id": str(h.get("provider_entity_id") or ""),
                "highlightly_team_name": str(h.get("name") or ""),
                "highlightly_season_label": SEASON_LABEL,
                "livescore_team_id": str(live.get("provider_team_id") or ""),
                "livescore_team_name": str(live.get("team_name") or ""),
                "livescore_season_label": str(live.get("season_label") or ""),
                "livescore_standings_evidence_complete": bool(live.get("evidence_complete")),
                "livescore_source_endpoint": live.get("source_endpoint"),
                "livescore_source_retrieved_at": str(live.get("source_retrieved_at") or ""),
                "name_match_basis": "unique_exact_normalized_name_within_same_2026_27_competition",
            })
    return output


def _verify_highlightly_detail(
    expected_id: str, expected_name: str, payload: Any,
) -> dict[str, Any]:
    record = _highlightly_team_record(payload)
    if record is None:
        return {"status": "held_missing_or_ambiguous_detail_record"}
    returned_id = str(record.get("id") or "")
    returned_name = str(record.get("name") or "")
    returned_type = str(record.get("type") or "").strip().casefold()
    checks = {
        "provider_id_matches": returned_id == expected_id,
        "provider_name_matches": normalize_entity_name(returned_name) == normalize_entity_name(expected_name),
        "provider_type_is_club": returned_type == "club",
    }
    return {
        "status": "provider_detail_confirmed" if all(checks.values()) else "held_detail_mismatch",
        "returned_id": returned_id,
        "returned_name": returned_name,
        "returned_type": returned_type or None,
        "checks": checks,
        "country_field_available": bool(record.get("country")),
        "country_value": record.get("country"),
        "raw_detail": dict(record),
    }


def _verify_livescore_detail(
    expected_id: str, expected_name: str, payload: Any,
) -> dict[str, Any]:
    club = _mapping(payload).get("club")
    if not isinstance(club, Mapping):
        return {"status": "held_missing_or_ambiguous_detail_record"}
    returned_id = str(club.get("id") or club.get("clubId") or "")
    returned_name = str(club.get("displayName") or club.get("name") or "")
    checks = {
        "provider_id_matches": returned_id == expected_id,
        "provider_name_matches": normalize_entity_name(returned_name) == normalize_entity_name(expected_name),
    }
    return {
        "status": "provider_detail_confirmed" if all(checks.values()) else "held_detail_mismatch",
        "returned_id": returned_id,
        "returned_name": returned_name,
        "country_value": club.get("country"),
        "city_value": club.get("city"),
        "catalog_source": club.get("catalogSource"),
        "checks": checks,
        "raw_detail": dict(club),
    }


def audit_team_details(database_url: str, highlightly_factory=HighlightlyClient,
                       livescore_factory=LiveScoreFootballClient) -> dict[str, Any]:
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(
                """SELECT provider_entity_id, name, raw_payload
                   FROM provider_source_entities
                   WHERE provider = 'highlightly' AND entity_type = 'team'
                   ORDER BY provider_entity_id"""
            )
            highlightly_rows = [
                {"provider_entity_id": values[0], "name": values[1], "raw_payload": values[2]}
                for values in cursor.fetchall()
            ]
            cursor.execute(
                """SELECT competition_provider_id, provider_team_id, team_name,
                          season_label, evidence_complete, source_endpoint,
                          source_retrieved_at, evidence_method,
                          requested_season_parameter
                   FROM provider_source_team_evidence_observations
                   WHERE provider = 'livescore_football'
                   ORDER BY competition_provider_id, provider_team_id"""
            )
            livescore_rows = [
                dict(zip(
                    ("competition_provider_id", "provider_team_id", "team_name",
                     "season_label", "evidence_complete", "source_endpoint",
                     "source_retrieved_at", "evidence_method",
                     "requested_season_parameter"), values
                ))
                for values in cursor.fetchall()
            ]
    all_livescore_evidence_rows = livescore_rows
    livescore_rows = [
        row for row in all_livescore_evidence_rows
        if row.get("evidence_method") == "season_standings"
        and str(row.get("requested_season_parameter") or "") == SEASON_YEAR
        and str(row.get("season_label") or "") == SEASON_LABEL
        and row.get("evidence_complete") is True
    ]
    candidates = build_exact_candidates(highlightly_rows, livescore_rows)
    results = []
    with highlightly_factory() as highlightly, livescore_factory() as livescore:
        for candidate in candidates:
            item = dict(candidate)
            try:
                payload = highlightly._get(f"teams/{candidate['highlightly_team_id']}")
                item["highlightly_detail"] = _verify_highlightly_detail(
                    candidate["highlightly_team_id"], candidate["highlightly_team_name"], payload
                )
            except Exception as exc:
                item["highlightly_detail"] = {
                    "status": "provider_request_failed", "error_type": type(exc).__name__,
                }
            try:
                payload = livescore.club(
                    candidate["livescore_competition_id"], candidate["livescore_team_id"]
                )
                item["livescore_detail"] = _verify_livescore_detail(
                    candidate["livescore_team_id"], candidate["livescore_team_name"], payload
                )
            except Exception as exc:
                item["livescore_detail"] = {
                    "status": "provider_request_failed", "error_type": type(exc).__name__,
                }
            confirmed = (
                item["highlightly_detail"].get("status") == "provider_detail_confirmed"
                and item["livescore_detail"].get("status") == "provider_detail_confirmed"
            )
            item["provider_native_details_confirmed"] = confirmed
            item["cross_provider_mapping_status"] = "candidate_only_not_approved"
            item["promotion_allowed"] = False
            results.append(item)
    counts = Counter(
        "provider_native_details_confirmed" if row["provider_native_details_confirmed"]
        else "held_detail_or_request_mismatch"
        for row in results
    )
    return {
        "operation": "highlightly_livescore_team_detail_audit",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "season": SEASON_LABEL,
        "read_only": True,
        "database_read_only": True,
        "database_writes": False,
        "candidate_pairs": len(candidates),
        "expected_candidate_pairs": 25,
        "highlightly_source_rows_read": len(highlightly_rows),
        "highlightly_rows_with_2026_27_label": sum(
            str(_mapping(row.get("raw_payload")).get("season_label") or "") == SEASON_LABEL
            for row in highlightly_rows
        ),
        "highlightly_competition_id_counts": dict(Counter(
            str(cid) for row in highlightly_rows
            for cid in _mapping(row.get("raw_payload")).get("competition_provider_ids", [])
        )),
        "livescore_evidence_rows_read": len(all_livescore_evidence_rows),
        "livescore_filtered_standings_rows": len(livescore_rows),
        "livescore_raw_method_counts": dict(Counter(
            str(row.get("evidence_method") or "") for row in all_livescore_evidence_rows
        )),
        "livescore_raw_season_labels": dict(Counter(
            str(row.get("season_label") or "") for row in all_livescore_evidence_rows
        )),
        "livescore_raw_requested_seasons": dict(Counter(
            str(row.get("requested_season_parameter") or "") for row in all_livescore_evidence_rows
        )),
        "candidate_counts_by_competition": dict(Counter(
            row["competition"] for row in candidates
        )),
        "detail_status_counts": dict(counts),
        "country_context_source": "competition/season provenance; not inferred from missing team country fields",
        "highlightly_documented_detail_fields": ["id", "name", "type", "logo"],
        "limitations": [
            "Highlightly team detail does not document a country field; the audit records country only if the live response supplies it.",
            "LiveScore club detail may omit country; missing country is retained as missing, not inferred from the competition.",
            "Provider-local ID/name/type verification plus exact competition-season overlap remains candidate evidence, not cross-provider identity approval.",
            "No gender, age-group, senior/reserve or first-team claim is inferred from a club endpoint alone.",
        ],
        "results": results,
        "canonical_ids_assigned": 0,
        "provider_links_created": 0,
        "provider_scope_fields_updated": 0,
        "fixtures_ingested": 0,
        "prediction_model_modified": False,
        "prediction_ledger_touched": False,
    }


def main() -> int:
    report = audit_team_details(os.getenv("PROVIDER_DATABASE_URL", "").strip())
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
                      encoding="utf-8")
    print(json.dumps({
        "checked_at_utc": report["checked_at_utc"],
        "read_only": report["read_only"],
        "candidate_pairs": report["candidate_pairs"],
        "candidate_counts_by_competition": report["candidate_counts_by_competition"],
        "detail_status_counts": report["detail_status_counts"],
        "canonical_ids_assigned": 0,
        "provider_links_created": 0,
        "report": str(REPORT),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
