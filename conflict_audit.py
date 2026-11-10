"""Deterministic conflict triage and immutable audit-event construction.

A policy-selected value is not a human override: the event records the exact
configured-priority decision and retains every eligible source observation.
Missing or ambiguous selections remain explicitly unresolved.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def build_conflict_resolution_audit(
    matches: list[Mapping[str, Any]] | None,
    *,
    competition: str,
    season: int,
    recorded_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Create one auditable event per conflicted field without changing data."""
    captured = recorded_at or datetime.now(timezone.utc)
    if captured.tzinfo is None:
        captured = captured.replace(tzinfo=timezone.utc)
    captured = captured.astimezone(timezone.utc).isoformat()
    events: list[dict[str, Any]] = []
    for match in matches or []:
        if not isinstance(match, Mapping):
            continue
        reconciliation = match.get("reconciliation")
        if not isinstance(reconciliation, Mapping):
            continue
        home = match.get("home") if isinstance(match.get("home"), Mapping) else {}
        away = match.get("away") if isinstance(match.get("away"), Mapping) else {}
        identity = {
            "competition": str(competition or "").strip(),
            "season": int(season),
            "kickoff_utc": match.get("kickoff_utc"),
            "home_team": home.get("name"),
            "away_team": away.get("name"),
            "source_ids": match.get("source_ids") or {},
        }
        for field, decision in reconciliation.items():
            if not isinstance(decision, Mapping) or decision.get("status") != "conflict":
                continue
            observations = decision.get("observations")
            safe_observations = [
                dict(row) for row in observations
                if isinstance(row, Mapping)
            ] if isinstance(observations, list) else []
            selected_provider = decision.get("provider")
            selected_rows = [
                row for row in safe_observations
                if row.get("provider") == selected_provider
            ]
            selected_value = selected_rows[0].get("value") if len(selected_rows) == 1 else None
            resolved = selected_provider is not None and len(selected_rows) == 1
            events.append({
                "competition": identity["competition"],
                "season": identity["season"],
                "fixture_identity": identity,
                "field": str(field),
                "triage_status": "resolved_by_configured_priority" if resolved else "unresolved",
                "selected_provider": selected_provider if resolved else None,
                "selected_value": selected_value,
                "observations": safe_observations,
                "corroborating_providers": list(decision.get("corroborating_providers") or []),
                "conflicting_providers": list(decision.get("conflicting_providers") or []),
                "resolution_reason": (
                    str(decision.get("message") or "Configured domain priority selected the authoritative eligible observation; no values were averaged.")
                    if resolved else
                    "No unique eligible selected observation exists; the field remains unresolved and must not be guessed."
                ),
                "recorded_at": captured,
                "prediction_inputs_modified": False,
                "manual_override": False,
            })
    return events
