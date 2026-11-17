"""Create a read-only competition readiness report from the crosswalk audit."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from competition_readiness import build_competition_readiness_report


def build_candidate_readiness_records(crosswalk_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Translate review candidates without treating corroboration as approval."""
    catalogue = crosswalk_report.get("provider_independent_catalogue")
    if not isinstance(catalogue, Mapping):
        catalogue = {}
    candidates = catalogue.get("canonical_seed_review_candidates")
    if not isinstance(candidates, list):
        candidates = []

    records: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        sources = candidate.get("sources") if isinstance(candidate.get("sources"), list) else []
        supplied_types = {
            str(source.get("competition_type") or "").strip().casefold()
            for source in sources if isinstance(source, Mapping) and source.get("competition_type")
        }
        competition_type = next(iter(supplied_types)) if len(supplied_types) == 1 else None
        season_evidence = candidate.get("season_evidence")
        season_records = season_evidence.get("season_records", []) if isinstance(season_evidence, Mapping) else []
        season_names = sorted({
            str(row.get("season_name") or "").strip()
            for row in season_records if isinstance(row, Mapping) and row.get("season_name")
        })
        season_name = season_names[0] if len(season_names) == 1 else None
        records.append({
            "competition": {
                "name": candidate.get("competition_name"),
                "country": candidate.get("country"),
                "type": competition_type,
                # A multi-provider review candidate is not an approved canonical identity.
                "identity_verified": False,
            },
            "season": {
                "id": None,
                "name": season_name,
                "active": False,
                # A shared start year is corroboration, not verified season identity.
                "identity_verified": False,
            },
            "teams": {
                "participating_count": 0,
                "approved_mapping_count": 0,
                "history_by_team": {},
                "statistics_complete_by_team": {},
                "tactical_components_by_team": {},
            },
            "fixture": {"upcoming_valid": False, "source_freshness": "unknown"},
            "evidence_generated_at": crosswalk_report.get("generated_at_utc"),
            "candidate_providers": candidate.get("providers", []),
            "season_evidence_status": (
                season_evidence.get("status") if isinstance(season_evidence, Mapping) else None
            ),
            "competition_type_evidence_status": (
                candidate.get("competition_type_evidence", {}).get("status")
                if isinstance(candidate.get("competition_type_evidence"), Mapping) else None
            ),
        })
    return records


def build_readiness_audit(crosswalk_report: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    records = build_candidate_readiness_records(crosswalk_report)
    report = build_competition_readiness_report(records, now=now)
    report["source_audit_generated_at"] = crosswalk_report.get("generated_at_utc")
    report["source_candidate_count"] = len(records)
    report["report_scope"] = (
        "Crosswalk review candidates only. This report does not certify the full provider catalogue. "
        "Candidates remain not ready until canonical competition/season identity, approved teams, "
        "fixture, history, statistics, tactical evidence and freshness are supplied."
    )
    return report


def write_readiness_report(
    source_path: str = "reports/free_fixture_crosswalk_audit/latest.json",
    output_dir: str = "reports/competition_readiness",
) -> dict[str, Any]:
    source = Path(source_path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    report = build_readiness_audit(payload, now=now)
    destination = Path(output_dir)
    archive = destination / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    (destination / "latest.json").write_text(encoded, encoding="utf-8")
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    (archive / f"{stamp}.json").write_text(encoded, encoding="utf-8")

    lines = [
        "# Competition readiness audit",
        "",
        f"Generated: {report['generated_at_utc']}",
        f"Source crosswalk audit: {report['source_audit_generated_at']}",
        "",
        "| Status | Competition-seasons |",
        "|---|---:|",
    ]
    for status, count in report["summary"].items():
        if status != "total_competition_seasons":
            lines.append(f"| {status} | {count} |")
    lines.extend(["", "## Candidate blockers", ""])
    for row in report["competitions"]:
        lines.append(f"### {row.get('competition_name')} — {row.get('country')}")
        blockers = row["hard_blockers"] + row["improvement_blockers"]
        lines.extend([f"- {item}" for item in blockers] or ["- No blockers"])
        lines.append("")
    (destination / "latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    result = write_readiness_report()
    print(json.dumps(result["summary"], sort_keys=True))
