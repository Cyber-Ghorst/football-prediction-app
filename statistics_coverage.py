"""Coverage reporting for model-relevant match statistics."""
from __future__ import annotations

from collections import defaultdict
from typing import Any


# These are the eight metric inputs currently consumed by tactical_indicators.py.
# Shots on Goal and Shots on Target are aliases for one model input, not two metrics.
TACTICAL_EVIDENCE_STATISTICS = (
    "Counter Attacks",
    "Big Chances Created",
    "Successful Headers",
    "Accurate Crosses",
    "Successful Dribbles",
    "Key Passes",
    "Shots Insidebox",
)


CORE_STATISTICS = (
    ("Ball Possession", "Possession & distribution", ("Ball Possession",)),
    ("Passes %", "Possession & distribution", ("Passes %",)),
    ("Total Shots", "Attacking", ("Total Shots",)),
    ("Shots on Target / Goal", "Attacking", ("Shots on Target", "Shots on Goal")),
    ("Tackles", "Defending", ("Tackles",)),
    ("Interceptions", "Defending", ("Interceptions",)),
    ("Blocked Shots", "Defending", ("Blocked Shots",)),
    ("Corner Kicks", "Attacking", ("Corner Kicks",)),
)


def build_statistics_coverage(matches: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize observed, missing and unmapped statistics without imputing values."""
    recent = list(matches[:10])
    total_matches = len(recent)
    metric_rows = []
    for label, group, canonical_names in CORE_STATISTICS:
        available_fixtures = 0
        observations = 0
        for match in recent:
            stats = match.get("statistics") or {}
            if any(stats.get(name) is not None for name in canonical_names):
                available_fixtures += 1
            observations += sum(
                1 for row in (match.get("statistics_raw_diagnostics") or [])
                if row.get("canonical_name") in canonical_names
                and row.get("mapping_status") == "mapped"
            )
        metric_rows.append({
            "group": group,
            "statistic": label,
            "fixtures_available": available_fixtures,
            "fixtures_checked": total_matches,
            "coverage_pct": round(available_fixtures / total_matches * 100, 1) if total_matches else None,
            "raw_observations": observations,
            "status": (
                "available" if available_fixtures == total_matches and total_matches
                else "partial" if available_fixtures
                else "missing"
            ),
        })

    unmapped: dict[str, dict[str, Any]] = defaultdict(lambda: {"observations": 0, "fixture_ids": set()})
    raw_rows_seen = 0
    for match in recent:
        for row in (match.get("statistics_raw_diagnostics") or []):
            raw_rows_seen += 1
            if row.get("mapping_status") != "unmapped":
                continue
            name = str(row.get("statistic_name_raw") or "Unknown statistic").strip() or "Unknown statistic"
            unmapped[name]["observations"] += 1
            if match.get("fixture_id") is not None:
                unmapped[name]["fixture_ids"].add(match.get("fixture_id"))

    unmapped_rows = [
        {
            "provider_statistic": name,
            "observations": data["observations"],
            "fixtures_seen": len(data["fixture_ids"]),
        }
        for name, data in sorted(unmapped.items(), key=lambda item: (-item[1]["observations"], item[0].casefold()))
    ]
    available_count = sum(row["fixtures_available"] > 0 for row in metric_rows)
    complete_count = sum(row["fixtures_available"] == total_matches and total_matches > 0 for row in metric_rows)
    return {
        "fixtures_checked": total_matches,
        "core_metrics_with_any_data": available_count,
        "core_metrics_complete": complete_count,
        "core_metrics_total": len(CORE_STATISTICS),
        "raw_observations_seen": raw_rows_seen,
        "unmapped_observations": sum(row["observations"] for row in unmapped_rows),
        "mapping_visibility": "available" if raw_rows_seen else "not supplied by this data path",
        "metrics": metric_rows,
        "tactical_evidence_metrics": [
            {
                "statistic": name,
                "team_output_fixtures": sum(
                    (match.get("statistics") or {}).get(name) is not None
                    for match in recent
                ),
                "opponent_output_fixtures": sum(
                    (match.get("opponent_statistics") or {}).get(name) is not None
                    for match in recent
                ),
                "fixtures_checked": total_matches,
            }
            for name in TACTICAL_EVIDENCE_STATISTICS
        ],
        "unmapped_statistics": unmapped_rows,
    }


def build_counter_attack_source_diagnostics(matches: list[dict[str, Any]]) -> dict[str, Any]:
    """Audit archived provider statistic rows for Counter Attacks without imputing data."""
    recent = list(matches[:10])
    inventory: dict[tuple[str, str], dict[str, Any]] = {}
    matching_rows = []
    fixtures_with_counter_attacks = set()

    for match in recent:
        fixture_id = match.get("fixture_id")
        for row in (match.get("statistics_raw_diagnostics") or []):
            type_id = row.get("statistic_type_id")
            type_id_text = str(type_id).strip() if type_id is not None else ""
            raw_name = str(row.get("statistic_name_raw") or "").strip()
            key = (type_id_text, raw_name)
            item = inventory.setdefault(key, {
                "statistic_type_id": type_id,
                "statistic_name_raw": raw_name or None,
                "observations": 0,
            })
            item["observations"] += 1

            is_counter_attack = (
                type_id_text == "1527"
                or "counter attack" in raw_name.casefold()
                or "counter-attacks" in raw_name.casefold()
            )
            if is_counter_attack:
                if fixture_id is not None:
                    fixtures_with_counter_attacks.add(str(fixture_id))
                matching_rows.append({
                    "fixture_id": fixture_id,
                    "statistic_type_id": type_id,
                    "statistic_name_raw": raw_name or None,
                    "canonical_name": row.get("canonical_name"),
                    "raw_value": row.get("raw_value"),
                    "normalized_value": row.get("normalized_value"),
                    "mapping_status": row.get("mapping_status"),
                })

    inventory_rows = sorted(
        inventory.values(),
        key=lambda row: (
            str(row.get("statistic_type_id") or ""),
            str(row.get("statistic_name_raw") or "").casefold(),
        ),
    )
    if matching_rows:
        status = "counter_attack_rows_found_in_archived_provider_statistics"
    elif sum(len(match.get("statistics_raw_diagnostics") or []) for match in recent):
        status = "no_counter_attack_rows_found_in_archived_provider_statistics"
    else:
        status = "raw_provider_statistic_rows_not_available"

    return {
        "provider": "sportmonks",
        "source": "archived fixture statistic rows read from the central repository",
        "fixtures_checked": len(recent),
        "fixtures_with_counter_attack_rows": len(fixtures_with_counter_attacks),
        "counter_attack_rows_found": len(matching_rows),
        "counter_attack_rows": matching_rows,
        "statistic_type_inventory": inventory_rows,
        "status": status,
        "note": (
            "This audits the statistic rows archived by the collector. "
            "Zero matching rows means no Counter Attacks row was present in the archived "
            "sample; it does not establish whether the provider omitted it upstream or "
            "whether an earlier collection step failed to retain it."
        ),
    }
