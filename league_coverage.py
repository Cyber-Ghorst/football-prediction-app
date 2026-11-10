"""Evidence-based competition coverage classification for the Layer 3 dashboard.

Coverage is descriptive: discovery and adapter availability never establish
prediction readiness. Only an explicit upstream readiness flag can do that.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping


def build_league_coverage_dashboard(
    discovered_records: Iterable[Mapping[str, Any]] | None,
    provider_status: Iterable[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Classify provider competition-season rows without inferring readiness."""
    provider_index: dict[str, dict[str, Any]] = {}
    for item in provider_status or []:
        if not isinstance(item, Mapping):
            continue
        provider_id = str(item.get("provider_id") or "").strip().casefold()
        if provider_id:
            provider_index[provider_id] = dict(item)

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in discovered_records or []:
        if not isinstance(source, Mapping):
            continue
        row = dict(source)
        identity = str(row.get("identity_key") or "").strip()
        if not identity or identity in seen:
            continue
        seen.add(identity)
        provider_id = str(row.get("provider") or "").strip().casefold()
        provider = provider_index.get(provider_id, {})
        adapter_implemented = str(provider.get("adapter") or "").casefold() == "implemented"
        credential_configured = provider.get("credential_configured") is True
        supported = bool(adapter_implemented and credential_configured)
        prediction_ready = row.get("prediction_ready") is True
        incomplete = bool(supported and not prediction_ready)
        if prediction_ready:
            status = "prediction_ready"
        elif incomplete:
            status = "incomplete"
        elif adapter_implemented:
            status = "discovered_credential_unconfirmed"
        else:
            status = "discovered_only"
        reason = str(row.get("readiness_reason") or "").strip()
        if not supported and not prediction_ready:
            reason = (
                "Provider adapter or credentials are not confirmed; competition discovery alone "
                "does not establish account support."
            )
        elif prediction_ready:
            reason = reason or "Upstream validation explicitly marked this competition-season prediction-ready."
        else:
            reason = reason or "Prediction readiness has not been explicitly established."
        row.update({
            "supported": supported,
            "incomplete": incomplete,
            "prediction_ready": prediction_ready,
            "coverage_status": status,
            "readiness_reason": reason,
            "adapter_implemented": adapter_implemented,
            "credential_configured": credential_configured,
        })
        rows.append(row)

    summary = {
        "discovered": len(rows),
        "supported": sum(bool(row["supported"]) for row in rows),
        "incomplete": sum(bool(row["incomplete"]) for row in rows),
        "prediction_ready": sum(bool(row["prediction_ready"]) for row in rows),
        "discovered_only": sum(row["coverage_status"] == "discovered_only" for row in rows),
        "discovered_credential_unconfirmed": sum(
            row["coverage_status"] == "discovered_credential_unconfirmed" for row in rows
        ),
    }
    return {
        "summary": summary,
        "competitions": sorted(
            rows,
            key=lambda row: (
                str(row.get("country") or "").casefold(),
                str(row.get("competition_name") or "").casefold(),
                str(row.get("season_name") or "").casefold(),
                str(row.get("identity_key") or ""),
            ),
        ),
        "readiness_policy": (
            "Only an explicit upstream prediction_ready=true is counted as prediction-ready. "
            "Discovery, adapter availability and credentials are not substitutes for data-quality validation."
        ),
    }
